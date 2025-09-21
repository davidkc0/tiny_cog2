
import requests
import json
import re
from typing import Dict, Any, List, Optional
from tool_system import Tool
from dataclasses import dataclass
from datetime import datetime

@dataclass
class SearchResult:
    """Structured search result"""
    title: str
    url: str
    snippet: str
    relevance_score: float = 0.0
    timestamp: Optional[str] = None

class WebSearchTool(Tool):
    """Enhanced web search tool with multiple providers and result processing"""
    
    def __init__(self, search_provider="duckduckgo", max_results=5):
        self.search_provider = search_provider
        self.max_results = max_results
        
        # Configure search providers
        self.providers = {
            "brave": self._brave_search,
            "duckduckgo": self._duckduckgo_search,
            "serper": self._serper_search  # Google search via Serper API
        }
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return "Searches the web for current information and real-time data"
    
    def can_handle(self, user_input: str, context: Dict[str, Any]) -> bool:
        """Check if input requires web search"""
        search_indicators = [
            # Explicit search requests
            "search for", "look up", "find information about", "search the web",
            "google", "find online", "search online",
            
            # Current/recent information requests
            "latest", "recent", "current", "today", "this week", "this month",
            "what's happening", "news about", "updates on",
            
            # Time-sensitive queries
            "price of", "stock price", "weather", "forecast", "schedule",
            "when is", "what time", "how much does", "cost of",
            
            # Real-time data requests
            "trending", "popular", "viral", "breaking news",
            
            # Information likely not in stored knowledge
            "reviews of", "compare", "vs", "versus", "best", "top",
            "how to", "tutorial", "guide", "instructions"
        ]
        
        user_lower = user_input.lower()
        
        # Check for explicit indicators
        if any(indicator in user_lower for indicator in search_indicators):
            return True
        
        # Check for question patterns that typically need fresh data
        question_patterns = [
            r"what (?:is|are) the (?:latest|current|recent)",
            r"who (?:won|is|are) (?:the|this|last)",
            r"when (?:is|was|will) (?:the|this|next)",
            r"how much (?:does|is|are|costs?)",
            r"where (?:is|can i|to)",
        ]
        
        for pattern in question_patterns:
            if re.search(pattern, user_lower):
                return True
        
        return False
    
    def execute(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute web search and return processed results"""
        try:
            # Extract search query from user input
            search_query = self._extract_search_query(user_input)
            # Perform search
            search_provider_func = self.providers.get(self.search_provider)
            if not search_provider_func:
                return {"success": False, "error": f"Unknown search provider: {self.search_provider}"}
            
            raw_results = search_provider_func(search_query)
            
            if not raw_results:
                return {
                    "success": True,
                    "query": search_query,
                    "results": [],
                    "message": f"No search results found for: {search_query}"
                }
            
            # Process and rank results
            processed_results = self._process_results(raw_results, user_input)
            
            # Generate summary
            summary = self._generate_summary(processed_results, user_input)
            
            return {
                "success": True,
                "query": search_query,
                "results": processed_results,
                "summary": summary,
                "message": f"Found {len(processed_results)} results for: {search_query}"
            }
            
        except Exception as e:
            print(f"Debug: Web search error: {e}")
            return {"success": False, "error": str(e)}
    
    def _extract_search_query(self, user_input: str) -> str:
        """Extract clean search query from user input"""
        # Remove common search prefixes
        query = user_input
        prefixes_to_remove = [
            "search for", "look up", "find information about", "search the web for",
            "google", "find", "search", "tell me about", "what is", "what are",
            "how much", "when is", "where is", "who is"
        ]
        
        query_lower = query.lower()
        for prefix in prefixes_to_remove:
            if query_lower.startswith(prefix):
                query = query[len(prefix):].strip()
                break
        
        # Clean up the query
        query = re.sub(r'^(the|a|an)\s+', '', query, flags=re.IGNORECASE)
        query = query.strip('?.,!').strip()
        
        # Fix common contractions and improve weather queries
        query = re.sub(r'\bwhats\b', 'what is', query, flags=re.IGNORECASE)
        query = re.sub(r'\bwheres\b', 'where is', query, flags=re.IGNORECASE)
        query = re.sub(r'\bwhos\b', 'who is', query, flags=re.IGNORECASE)
        query = re.sub(r'\bwhens\b', 'when is', query, flags=re.IGNORECASE)
        
        # For weather queries, make them more specific and add location context
        if 'weather' in query.lower():
            if 'new york' in query.lower() or 'nyc' in query.lower():
                query = "New York City weather forecast today"
            else:
                query = f"current weather forecast {query}"
        
        # For news queries, make them more specific and recent
        if 'news' in query.lower() or 'summarize' in query.lower() or 'summerize' in query.lower():
            # Extract the main subject from the query and make it more searchable
            # Remove common words that don't help with search
            stop_words = {'news', 'about', 'summarize', 'summerize', 'what', 'you', 'see', 'search', 'for', 'latest', 'recent', 'today'}
            words = [word for word in query.lower().split() if word not in stop_words]
            
            if words:
                # Reconstruct query with key terms and add recency indicators
                main_subject = ' '.join(words)
                query = f"{main_subject} news today"
            else:
                # Fallback for very generic queries
                query = "latest news today"
        
        # For current/recent information queries, add recency indicators
        elif any(word in query.lower() for word in ['current', 'latest', 'recent', 'today', 'now', 'this week', 'this month']):
            # Add recency indicators to make search more effective
            if not any(word in query.lower() for word in ['news', 'weather']):
                query = f"{query} today"
        
        return query if query else user_input
    
    def _process_results(self, raw_results: List[Dict], user_input: str) -> List[SearchResult]:
        """Process and rank search results"""
        processed = []
        
        for result in raw_results[:self.max_results]:
            search_result = SearchResult(
                title=result.get("title", ""),
                url=result.get("href", ""),  # DuckDuckGo uses 'href' not 'url'
                snippet=result.get("body", ""),  # DuckDuckGo uses 'body' not 'snippet'
                relevance_score=self._calculate_relevance(result, user_input),
                timestamp=result.get("timestamp")
            )
            processed.append(search_result)
        
        # Sort by relevance score
        processed.sort(key=lambda x: x.relevance_score, reverse=True)
        return processed
    
    def _calculate_relevance(self, result: Dict, user_input: str) -> float:
        """Calculate relevance score for a search result"""
        score = 0.0
        user_words = set(user_input.lower().split())
        
        # Title relevance
        title_words = set(result.get("title", "").lower().split())
        title_overlap = len(user_words.intersection(title_words))
        score += title_overlap * 0.4
        
        # Snippet relevance (DuckDuckGo uses 'body' not 'snippet')
        snippet_words = set(result.get("body", "").lower().split())
        snippet_overlap = len(user_words.intersection(snippet_words))
        score += snippet_overlap * 0.3
        
        # Domain authority (simple heuristic)
        url = result.get("href", "")  # DuckDuckGo uses 'href' not 'url'
        authoritative_domains = [
            "wikipedia.org", "edu", "gov", "reuters.com", "bbc.com",
            "npr.org", "cnn.com", "nytimes.com", "wsj.com"
        ]
        if any(domain in url for domain in authoritative_domains):
            score += 0.3
        
        return score
    
    def _generate_summary(self, results: List[SearchResult], user_input: str) -> str:
        """Generate a summary of search results"""
        if not results:
            return "No relevant results found."
        
        # Get top 3 results for summary
        top_results = results[:3]
        
        summary_parts = []
        for i, result in enumerate(top_results, 1):
            summary_parts.append(f"{i}. {result.title}: {result.snippet}")
        
        return "\n\n".join(summary_parts)
    
    def _brave_search(self, query: str) -> List[Dict]:
        """Search using Brave Search API"""
        # Placeholder - would need actual Brave Search API key
        # For demo purposes, returning mock data
        return [
            {
                "title": f"Mock result 1 for: {query}",
                "url": "https://example.com/1",
                "snippet": f"This is a mock search result for the query '{query}'. In a real implementation, this would connect to Brave Search API."
            },
            {
                "title": f"Mock result 2 for: {query}",
                "url": "https://example.com/2", 
                "snippet": f"Another mock result about '{query}' with relevant information."
            }
        ]
    
    def _duckduckgo_search(self, query: str) -> List[Dict]:
        """Search using DuckDuckGo (via ddgs library)"""
        try:
            from ddgs import DDGS
            ddgs = DDGS()
            results = ddgs.text(query, max_results=self.max_results)
            return results
        except Exception as e:
            print(f"DuckDuckGo search error: {e}")
            return []
    
    def _serper_search(self, query: str) -> List[Dict]:
        """Search using Serper API (Google search)"""
        try:
            # Would need Serper API key
            # api_key = os.getenv("SERPER_API_KEY")
            # headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
            # payload = {"q": query, "num": self.max_results}
            # response = requests.post("https://google.serper.dev/search", 
            #                         headers=headers, json=payload)
            # return response.json().get("organic", [])
            
            # Mock implementation
            return [
                {
                    "title": f"Google result via Serper: {query}",
                    "url": "https://google.com",
                    "snippet": f"Google search result for '{query}' via Serper API"
                }
            ]
        except Exception as e:
            print(f"Serper search error: {e}")
            return []

class WebSearchKnowledgeExtractor:
    """Extract knowledge from web search results"""
    
    def __init__(self, llm_caller):
        self.llm_caller = llm_caller
    
    def extract_facts_from_results(self, search_results: List[SearchResult], user_query: str) -> List[Dict[str, Any]]:
        """Extract structured facts from search results"""
        if not search_results:
            return []
        
        # Combine top results into context
        context = "\n".join([
            f"Title: {result.title}\nContent: {result.snippet}\nSource: {result.url}"
            for result in search_results[:3]
        ])
        
        prompt = f"""Extract factual information from these search results. Return ONLY a JSON array.
Each fact should have: entity, type, relation, target, and source_url.

User query: "{user_query}"

Search results:
{context}

Extract facts that directly answer the user's question. Focus on:
- Current data (prices, dates, statistics)
- Factual information (definitions, locations, people)
- Recent events or updates

JSON array:"""
        
        try:
            response = self.llm_caller(prompt, mode="answer")
            return self._parse_json_response(response)
        except Exception as e:
            print(f"Web search knowledge extraction error: {e}")
            return []
    
    def _parse_json_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse JSON response with fallback"""
        try:
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                facts = json.loads(json_str)
                return facts if isinstance(facts, list) else []
        except Exception:
            pass
        return []