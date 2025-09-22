# refactored_cognitive_agent.py
import re
import json
import time
import math
from collections import deque
from typing import List, Dict, Any, Optional
import ollama
from dotenv import load_dotenv

# Import the modular components
import storage
import embeddings
from kgraph import KnowledgeGraph
from tool_system import ToolRegistry, CalculatorTool
from web_search_tool import WebSearchTool
from intelligent_knowledge_tool import IntelligentKnowledgeTool
from knowledge_extractors import CompositeKnowledgeExtractor, LLMKnowledgeExtractor, PatternKnowledgeExtractor, PersonExtractor
from memory_strategies import MemoryManager
from processing_pipeline import ProcessingPipeline, PipelineFactory


load_dotenv()

def get_ollama_client():
    """Test if Ollama is available"""
    try:
        ollama.list()
        return True
    except Exception:
        return False

def call_ollama_model(prompt: str, mode: str = "answer", model: str = "llama3.1") -> str:
    """Call Ollama with mode support"""
    if not get_ollama_client():
        return fallback_model(prompt, mode)
    
    try:
        # Add mode-specific instructions to prompt
        if mode == "plan":
            system_msg = (
                "You are a planning assistant. You must respond with EXACTLY ONE LINE:\n"
                "ACTION: <tool_name>\n"
                "ACTION: respond\n"
                "Choose the appropriate tool based on available tools, or respond for general conversation."
            )
            full_prompt = f"{system_msg}\n\n{prompt}"
        else:
            full_prompt = prompt
            
        response = ollama.chat(model=model, messages=[
            {'role': 'user', 'content': full_prompt}
        ])
        return response['message']['content'].strip()
    except Exception as e:
        print(f"Ollama error: {e}")
        return fallback_model(prompt, mode)

def fallback_model(prompt: str, mode: str) -> str:
    """Fallback when Ollama unavailable"""
    if mode == "plan":
        if re.search(r'\d+[\+\-\*/\^\(\)]\d+|\d+\s*[\+\-\*/\^]\s*\d+', prompt):
            return "ACTION: calculator"
        elif "what do you know" in prompt.lower() or "my favorite" in prompt.lower():
            return "ACTION: knowledge_graph"
        elif any(word in prompt.lower() for word in ["search", "latest", "current", "news", "price", "weather"]):
            return "ACTION: web_search"  # Add this line
        else:
            return "ACTION: respond"
    return "I'm using a fallback response. Install and run Ollama for better results."

class CognitiveAgent:
    """Refactored cognitive agent with configurable components"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize with optional configuration"""
        self.config = config or {}
        self.turn = 0
        
        # Initialize core components
        storage.ensure_schema()
        self.kg = KnowledgeGraph()
        
        # Setup configurable components
        self._setup_tools()
        self._setup_knowledge_extractors()
        self._setup_memory_manager()
        self._setup_pipeline()
        
        # Ensure embedding consistency
        self._ensure_embeddings()
    
    def _setup_tools(self):
        """Setup tool registry with default tools"""
        self.tool_registry = ToolRegistry()
        
        # Register default tools
        self.tool_registry.register(CalculatorTool(), priority=10)
        self.tool_registry.register(WebSearchTool(), priority=8)  # High priority for web search
        self.tool_registry.register(IntelligentKnowledgeTool(self.kg, call_ollama_model), priority=5)
        
        # Register additional tools from config
        additional_tools = self.config.get("additional_tools", [])
        for tool_config in additional_tools:
            if tool_config["name"] == "web_search":
                self.tool_registry.register(WebSearchTool(), priority=tool_config.get("priority", 0))
    
    @staticmethod
    def web_search_config():
        """Agent optimized with web search capabilities"""
        return {
            "pipeline_type": "web_search",  # New pipeline type
            "knowledge_extractors": ["llm", "pattern"],
            "memory_strategy": "enhanced",
            "search_provider": "brave",  # or "duckduckgo", "serper"
            "max_search_results": 5
        }


    def _setup_knowledge_extractors(self):
        """Setup knowledge extraction system"""
        self.knowledge_extractor = CompositeKnowledgeExtractor()
        
        # Add default extractors
        extractor_config = self.config.get("knowledge_extractors", ["llm", "pattern", "person"])
        
        if "llm" in extractor_config:
            self.knowledge_extractor.add_extractor(LLMKnowledgeExtractor(call_ollama_model))
        
        if "pattern" in extractor_config:
            pattern_extractor = PatternKnowledgeExtractor()
            # Add custom patterns from config
            custom_patterns = self.config.get("custom_patterns", [])
            for pattern in custom_patterns:
                pattern_extractor.add_pattern(**pattern)
            self.knowledge_extractor.add_extractor(pattern_extractor)
        
        if "person" in extractor_config:
            self.knowledge_extractor.add_extractor(PersonExtractor())
    
    def _setup_memory_manager(self):
        """Setup memory management system"""
        self.memory_manager = MemoryManager()
        
        # Set memory strategy from config
        memory_strategy = self.config.get("memory_strategy", "default")
        self.memory_manager.set_strategy(memory_strategy)
    
    def _setup_pipeline(self):
        """Setup processing pipeline"""
        pipeline_type = self.config.get("pipeline_type", "default")
        
        if pipeline_type == "default":
            self.pipeline = PipelineFactory.create_default_pipeline(
                call_ollama_model, self.tool_registry, self.memory_manager,
                self.knowledge_extractor, storage, embeddings, self.kg
            )
        elif pipeline_type == "simple":
            self.pipeline = PipelineFactory.create_simple_pipeline(
                call_ollama_model, self.tool_registry
            )
        elif pipeline_type == "memory_focused":
            self.pipeline = PipelineFactory.create_memory_focused_pipeline(
                call_ollama_model, self.memory_manager, storage, embeddings, self.kg
            )
        else:
            # Custom pipeline configuration
            self.pipeline = self._create_custom_pipeline()
    
    def _create_custom_pipeline(self):
        """Create custom pipeline from config"""
        # This would be implemented based on specific custom pipeline needs
        return PipelineFactory.create_default_pipeline(
            call_ollama_model, self.tool_registry, self.memory_manager,
            self.knowledge_extractor, storage, embeddings, self.kg
        )
    
    def _ensure_embeddings(self):
        """Ensure embedding system is working and dimensions are consistent"""
        test_emb = embeddings.embed_text("test")
        current_dim = len(test_emb)
        stored_dim = storage.get_meta("embedding_dimension")
        
        # Check for dimension inconsistencies in stored vectors
        consistent, dim_info = storage.check_vector_dimensions()
        if not consistent:
            print(f"Vector dimension inconsistency detected: {dim_info}")
            print("Clearing all vectors to ensure consistency...")
            storage.clear_vectors()
            storage.set_meta("embedding_dimension", str(current_dim))
        elif stored_dim is None:
            storage.set_meta("embedding_dimension", str(current_dim))
        elif int(stored_dim) != current_dim:
            print(f"Embedding dimension changed from {stored_dim} to {current_dim}, clearing vectors...")
            storage.clear_vectors()
            storage.set_meta("embedding_dimension", str(current_dim))
    
    def act(self, user_msg: str) -> str:
        """Main agent action using the configured pipeline"""
        try:
            # Prepare context for pipeline
            raw_context = {"kg": self.kg}
            
            # Process through pipeline
            response = self.pipeline.process(user_msg, raw_context)
            
            self.turn += 1
            return response
            
        except Exception as e:
            print(f"Agent error: {e}")
            return "I encountered an error processing your request. Please try again."
    
    # Configuration methods
    def add_tool(self, tool, priority: int = 0):
        """Add a new tool to the agent"""
        self.tool_registry.register(tool, priority)
    
    def remove_tool(self, tool_name: str):
        """Remove a tool from the agent"""
        self.tool_registry.unregister(tool_name)
    
    def set_memory_strategy(self, strategy_name: str):
        """Change the memory strategy"""
        self.memory_manager.set_strategy(strategy_name)
    
    def add_knowledge_extractor(self, extractor):
        """Add a knowledge extractor"""
        self.knowledge_extractor.add_extractor(extractor)
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status information"""
        return {
            "turn": self.turn,
            "tools": self.tool_registry.list_tools(),
            "memory_strategy": self.memory_manager.current_strategy,
            "memory_strategies": self.memory_manager.list_strategies(),
            "kg_entities": len(self.kg.G.nodes),
            "kg_relations": len(self.kg.G.edges),
            "pipeline_steps": [step.name for step in self.pipeline.steps]
        }

# Example configurations
class AgentConfigurations:
    """Predefined agent configurations"""
    
    @staticmethod
    def minimal_config():
        """Minimal agent with just basic conversation"""
        return {
            "pipeline_type": "simple",
            "knowledge_extractors": [],
            "memory_strategy": "recent"
        }
    
    @staticmethod
    def math_focused_config():
        """Agent optimized for mathematical tasks"""
        return {
            "pipeline_type": "simple",
            "knowledge_extractors": [],
            "memory_strategy": "recent",
            "additional_tools": []
        }
    
    @staticmethod
    def personal_assistant_config():
        """Agent optimized as personal assistant"""
        return {
            "pipeline_type": "default",
            "knowledge_extractors": ["llm", "pattern", "person"],
            "memory_strategy": "adaptive",
            "custom_patterns": [
                {
                    "name": "pet_name",
                    "pattern": r"my (?:dog|cat|pet) (?:is )?(\w+)",
                    "entity_group": 1,
                    "type": "pet",
                    "relation": "owns",
                    "target": "user"
                }
            ]
        }
    
    @staticmethod
    def research_assistant_config():
        """Agent optimized for research tasks"""
        return {
            "pipeline_type": "default",
            "knowledge_extractors": ["llm", "pattern"],
            "memory_strategy": "prioritized",
            "additional_tools": [
                {"name": "web_search", "priority": 8}
            ]
        }

def main():
    """Main demo function with configuration options"""
    print("🧠 Refactored Cognitive Agent Starting...")
    
    # Check Ollama
    if get_ollama_client():
        print("✅ Ollama connected")
    else:
        print("⚠️ Ollama not available - using fallback mode")
    
    # Choose configuration
    print("\nChoose agent configuration:")
    print("1. Default (full features)")
    print("2. Minimal (basic conversation)")
    print("3. Math-focused")
    print("4. Personal assistant")
    print("5. Research assistant")
    
    try:
        choice = input("Enter choice (1-5, default=1): ").strip() or "1"
        
        configs = {
            "1": {},
            "2": AgentConfigurations.minimal_config(),
            "3": AgentConfigurations.math_focused_config(),
            "4": AgentConfigurations.personal_assistant_config(),
            "5": AgentConfigurations.research_assistant_config()
        }
        
        config = configs.get(choice, {})
        agent = CognitiveAgent(config)
        
        # Show agent status
        status = agent.get_status()
        print(f"\n📊 Agent Status:")
        print(f"   Tools: {[tool['name'] for tool in status['tools']]}")
        print(f"   Memory Strategy: {status['memory_strategy']}")
        print(f"   Pipeline: {' → '.join(status['pipeline_steps'])}")
        print(f"   Knowledge: {status['kg_entities']} entities, {status['kg_relations']} relations")
        
        print("\nReady! Type 'quit' to exit, 'status' for agent info.\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    break
                elif user_input.lower() == 'status':
                    status = agent.get_status()
                    print(f"Agent Status: {json.dumps(status, indent=2)}")
                    continue
                
                if user_input:
                    response = agent.act(user_input)
                    print(f"Agent: {response}\n")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
    
    except Exception as e:
        print(f"Startup error: {e}")
    
    print("Goodbye!")

if __name__ == "__main__":
    main()