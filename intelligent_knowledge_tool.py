# intelligent_knowledge_tool.py
from typing import Dict, Any
from tool_system import Tool

class IntelligentKnowledgeTool(Tool):
    """Intelligent knowledge search tool using LLM for natural language understanding"""
    
    def __init__(self, kg, llm_caller):
        self.kg = kg
        self.llm_caller = llm_caller
    
    @property
    def name(self) -> str:
        return "intelligent_knowledge"
    
    @property
    def description(self) -> str:
        return "Intelligently searches and interprets stored knowledge using natural language understanding"
    
    def can_handle(self, user_input: str, context: Dict[str, Any]) -> bool:
        """Check if input is asking about stored knowledge"""
        query_indicators = [
            "what do you know", "tell me about", "my favorite", 
            "what is my", "who is", "where do i", "do i like",
            "what do i like", "what are my", "do you remember",
            "what do you remember", "tell me what", "what information",
            "what do you know about", "tell me what you know"
        ]
        user_lower = user_input.lower()
        return any(indicator in user_lower for indicator in query_indicators)
    
    def execute(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Intelligently search and interpret knowledge using LLM"""
        try:
            # Get all knowledge from the database
            all_knowledge = self._get_all_knowledge()
            
            if not all_knowledge:
                return {
                    "success": True, 
                    "message": "I don't have any information stored in my knowledge base yet."
                }
            
            # Use LLM to intelligently search and interpret
            prompt = f"""You are an AI assistant with access to a knowledge database. Answer the user's question based on the information available.

KNOWLEDGE DATABASE:
{all_knowledge}

USER QUESTION: {user_input}

Instructions:
- Search through the knowledge database to find relevant information
- Answer the user's question directly and naturally
- If you find relevant information, provide a helpful answer
- If you don't find relevant information, say "I don't have that information in my knowledge base"
- Be conversational and helpful
- Don't mention database structure or technical details

ANSWER:"""

            response = self.llm_caller(prompt, mode="answer")
            
            return {
                "success": True,
                "message": response
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_all_knowledge(self):
        """Get all knowledge from the knowledge graph in a natural format"""
        knowledge_items = []
        
        # Get all entities and their relationships
        for entity_name in self.kg.G.nodes():
            info = self.kg.get_entity_info(entity_name)
            if info:
                related = self.kg.get_related_concepts(entity_name, max_out=10)
                
                # Format relationships in natural language
                if related:
                    for target, relation in related:
                        if relation == "likes":
                            knowledge_items.append(f"The user likes {entity_name}")
                        elif relation == "liked_by":
                            knowledge_items.append(f"{entity_name} is liked by the user")
                        elif relation == "lives_in":
                            knowledge_items.append(f"The user lives in {entity_name}")
                        elif relation == "works_as":
                            knowledge_items.append(f"The user works as {entity_name}")
                        elif relation == "owns":
                            knowledge_items.append(f"The user owns {entity_name}")
                        elif relation == "favorite":
                            knowledge_items.append(f"The user's favorite is {entity_name}")
                        else:
                            knowledge_items.append(f"{entity_name} {relation} {target}")
                else:
                    knowledge_items.append(f"Entity: {entity_name} ({info.get('type', 'entity')})")
        
        return "\n".join(knowledge_items)
