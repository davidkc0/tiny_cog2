"""
Integration components for web search in the cognitive agent
"""

from processing_pipeline import ProcessingStep, ProcessingContext
from enhanced_web_search_tool import WebSearchTool, WebSearchKnowledgeExtractor
import time

class WebSearchPlanningStep(ProcessingStep):
    """Enhanced planning step that considers web search"""
    
    def __init__(self, llm_caller, tool_registry):
        self.llm_caller = llm_caller
        self.tool_registry = tool_registry
    
    @property
    def name(self) -> str:
        return "web_search_planning"
    
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Enhanced planning that considers web search needs"""
        try:
            available_tools = self.tool_registry.get_tool_descriptions()
            
            # Check if we have sufficient context for the query
            context_quality = self._assess_context_quality(context)
            
            prompt = f"""Available tools:
{available_tools}

CONTEXT QUALITY: {context_quality}
CONTEXT:
{context.formatted_context}

USER: {context.user_input}

Choose the best approach:
- Use "web_search" for current information, recent events, real-time data, or when stored context is insufficient
- Use "knowledge_graph" for personal information or stored preferences
- Use "calculator" for mathematical calculations  
- Use "respond" for general conversation with sufficient context

Priority: If the query needs current/recent information or context is insufficient, prefer web_search.

Output EXACTLY one line:
ACTION: <tool_name>
ACTION: respond"""
            
            plan_output = self.llm_caller(prompt, mode="plan")
            
            # Parse the action
            if "ACTION:" in plan_output:
                action = plan_output.split("ACTION:")[-1].strip()
                if action in self.tool_registry.tools:
                    context.selected_tool = action
                else:
                    context.selected_tool = None
            else:
                context.selected_tool = None
            
            context.metadata["planned_at"] = time.time()
            context.metadata["context_quality"] = context_quality
            
        except Exception as e:
            print(f"Web search planning error: {e}")
            context.selected_tool = None
        
        return context
    
    def _assess_context_quality(self, context: ProcessingContext) -> str:
        """Assess whether current context is sufficient for the query"""
        user_input_lower = context.user_input.lower()
        context_text = context.formatted_context.lower()
        
        # Check for time-sensitive indicators
        time_sensitive_words = [
            "current", "latest", "recent", "today", "now", "this week",
            "trending", "breaking", "update", "news", "price", "cost"
        ]
        
        if any(word in user_input_lower for word in time_sensitive_words):
            return "INSUFFICIENT - needs current information"
        
        # Check if context mentions relevant entities from query
        query_words = set(user_input_lower.split())
        context_words = set(context_text.split())
        overlap = len(query_words.intersection(context_words))
        
        if overlap < 2 and len(context.formatted_context.strip()) < 100:
            return "INSUFFICIENT - limited relevant context"
        elif overlap >= 3:
            return "SUFFICIENT - good context available"
        else:
            return "MODERATE - some context available"

class WebSearchResponseStep(ProcessingStep):
    """Enhanced response generation that handles web search results"""
    
    def __init__(self, llm_caller):
        self.llm_caller = llm_caller
    
    @property
    def name(self) -> str:
        return "web_search_response"
    
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Generate response with web search result integration"""
        try:
            if context.tool_result and context.selected_tool == "web_search":
                # Handle web search results
                if context.tool_result.get("success"):
                    context.response = self._generate_web_search_response(
                        context.tool_result, context.user_input
                    )
                else:
                    context.response = f"I couldn't search the web: {context.tool_result.get('error', 'Unknown error')}"
            elif context.tool_result:
                # Handle other tool results (existing logic)
                if context.tool_result.get("success"):
                    if context.selected_tool == "calculator":
                        context.response = str(context.tool_result.get("result", ""))
                    elif context.selected_tool == "knowledge_graph":
                        context.response = self._interpret_knowledge_graph_result(context.tool_result, context.user_input)
                    else:
                        prompt = f"The {context.selected_tool} tool returned: {context.tool_result}\n\nProvide a clear, concise response to the user."
                        context.response = self.llm_caller(prompt, mode="answer")
                else:
                    context.response = f"I encountered an error: {context.tool_result.get('error', 'Unknown error')}"
            else:
                # Generate regular response
                response_prompt = (
                    f"You are a helpful AI assistant. Use the context when relevant but don't mention it explicitly.\n"
                    f"CONTEXT:\n{context.formatted_context}\n\n"
                    f"USER: {context.user_input}\n\n"
                    f"Provide a helpful, concise response:"
                )
                context.response = self.llm_caller(response_prompt, mode="answer")
            
            context.metadata["response_generated_at"] = time.time()
            
        except Exception as e:
            print(f"Web search response generation error: {e}")
            context.response = "I encountered an error generating a response. Please try again."
        
        return context
    
    def _generate_web_search_response(self, tool_result: dict, user_input: str) -> str:
        """Generate response from web search results"""
        results = tool_result.get("results", [])
        summary = tool_result.get("summary", "")
        query = tool_result.get("query", user_input)
        
        if not results:
            return f"I searched for '{query}' but didn't find any relevant results. Could you try rephrasing your question?"
        
        # Use LLM to generate a natural response from search results
        prompt = f"""Based on these web search results, provide a helpful answer to the user's question.

User question: "{user_input}"
Search query used: "{query}"

Search results:
{summary}

Instructions:
- Answer the user's question directly and naturally
- Synthesize information from the search results
- Be concise but informative
- If the results don't fully answer the question, say so
- Don't mention "search results" or technical details

Response:"""
        
        try:
            response = self.llm_caller(prompt, mode="answer")
            
            # Add source attribution
            if len(results) > 0:
                primary_source = results[0].url
                response += f"\n\n(Source: {primary_source})"
            
            return response
        except Exception as e:
            print(f"Error generating web search response: {e}")
            return f"Based on my search for '{query}': {summary}"
    
    def _interpret_knowledge_graph_result(self, tool_result, user_input):
        """Interpret knowledge graph results (existing method)"""
        # This would be the same as in the original processing_pipeline.py
        entities = tool_result.get("entities", [])
        if not entities:
            return "I don't have any information about that in my knowledge base."
        
        # Simplified version - you'd use the full implementation from the original
        return tool_result.get("message", "I found some information in my knowledge base.")

class WebSearchKnowledgeStorageStep(ProcessingStep):
    """Store valuable information from web searches"""
    
    def __init__(self, storage_module, embeddings_module, llm_caller):
        self.storage = storage_module
        self.embeddings = embeddings_module
        self.knowledge_extractor = WebSearchKnowledgeExtractor(llm_caller)
    
    @property
    def name(self) -> str:
        return "web_search_knowledge_storage"
    
    def can_skip(self, context: ProcessingContext) -> bool:
        """Only process web search results"""
        return context.selected_tool != "web_search" or not context.tool_result
    
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Extract and store knowledge from web search results"""
        try:
            if context.tool_result and context.tool_result.get("success"):
                results = context.tool_result.get("results", [])
                
                if results:
                    # Extract facts from search results
                    extracted_facts = self.knowledge_extractor.extract_facts_from_results(
                        results, context.user_input
                    )
                    
                    stored_count = 0
                    for fact in extracted_facts:
                        # Store as semantic fact with web source
                        key = f"web_{fact.get('entity', 'unknown')}"
                        value = fact.get('value', '')
                        source = f"web_search:{fact.get('source_url', 'unknown')}"
                        
                        if key and value:
                            fact_id = self.storage.insert_semantic(key, value, source)
                            fact_emb = self.embeddings.embed_text(f"{key} = {value}")
                            self.storage.upsert_vector("semantic", fact_id, fact_emb)
                            stored_count += 1
                    
                    # Store search query and top result for future reference
                    query = context.tool_result.get("query", "")
                    if query and results:
                        search_summary = f"Search '{query}': {results[0].title}"
                        search_id = self.storage.insert_semantic(
                            f"search_{query}", 
                            search_summary, 
                            "web_search"
                        )
                        search_emb = self.embeddings.embed_text(search_summary)
                        self.storage.upsert_vector("semantic", search_id, search_emb)
                        stored_count += 1
                    
                    context.metadata["web_facts_stored"] = stored_count
                    if stored_count > 0:
                        print(f"Stored {stored_count} facts from web search")
            
            context.metadata["web_knowledge_stored_at"] = time.time()
            
        except Exception as e:
            print(f"Web search knowledge storage error: {e}")
        
        return context

# Factory method to create web-search enabled pipeline
def create_web_search_pipeline(llm_caller, tool_registry, memory_manager, 
                              knowledge_extractor, storage_module, embeddings_module):
    """Create a pipeline with web search capabilities"""
    from processing_pipeline import ProcessingPipeline, ContextBuildingStep, ToolExecutionStep, KnowledgeExtractionStep, MemoryStorageStep, ReflectionStep
    
    pipeline = ProcessingPipeline()
    
    # Add steps in order
    pipeline.add_step(ContextBuildingStep(memory_manager))
    pipeline.add_step(WebSearchPlanningStep(llm_caller, tool_registry))  # Enhanced planning
    pipeline.add_step(ToolExecutionStep(tool_registry))
    pipeline.add_step(WebSearchResponseStep(llm_caller))  # Enhanced response generation
    pipeline.add_step(WebSearchKnowledgeStorageStep(storage_module, embeddings_module, llm_caller))  # Web knowledge storage
    pipeline.add_step(KnowledgeExtractionStep(knowledge_extractor))
    pipeline.add_step(MemoryStorageStep(storage_module, embeddings_module))
    pipeline.add_step(ReflectionStep(storage_module, embeddings_module))
    
    return pipeline