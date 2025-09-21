# processing_pipeline.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import time
import json
import re
from memory_extractors import MemoryEnhancer

@dataclass
class ProcessingContext:
    """Context object passed through the pipeline"""
    user_input: str
    raw_context: Dict[str, Any] = None
    formatted_context: str = ""
    selected_tool: Optional[str] = None
    tool_result: Optional[Dict[str, Any]] = None
    response: str = ""
    extracted_knowledge: List[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.raw_context is None:
            self.raw_context = {}
        if self.extracted_knowledge is None:
            self.extracted_knowledge = []
        if self.metadata is None:
            self.metadata = {}

class ProcessingStep(ABC):
    """Base class for processing steps"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Process the context and return modified context"""
        pass
    
    def can_skip(self, context: ProcessingContext) -> bool:
        """Check if this step can be skipped"""
        return False

class ContextBuildingStep(ProcessingStep):
    """Step that builds context from memory"""
    
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
    
    @property
    def name(self) -> str:
        return "context_building"
    
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Build context from memory systems"""
        try:
            raw_context = {"kg": context.raw_context.get("kg")}
            formatted_context = self.memory_manager.get_context(
                context.user_input, raw_context
            )
            context.formatted_context = formatted_context
            context.metadata["context_built_at"] = time.time()
        except Exception as e:
            print(f"Context building error: {e}")
            context.formatted_context = "Basic context available."
        
        return context

class PlanningStep(ProcessingStep):
    """Step that plans what action to take"""
    
    def __init__(self, llm_caller, tool_registry):
        self.llm_caller = llm_caller
        self.tool_registry = tool_registry
    
    @property
    def name(self) -> str:
        return "planning"
    
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Plan the next action"""
        try:
            available_tools = self.tool_registry.get_tool_descriptions()
            prompt = f"""Available tools:
{available_tools}

CONTEXT:
{context.formatted_context}

USER: {context.user_input}

Choose the best tool or respond directly. 
- Use "knowledge_graph" for questions about personal information, preferences, or stored knowledge
- Use "calculator" for mathematical calculations
- Use "web_search" for current information, recent events, real-time data, or when stored context is insufficient
- Use "respond" for general conversation

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
            
        except Exception as e:
            print(f"Planning error: {e}")
            context.selected_tool = None
        
        return context

class ToolExecutionStep(ProcessingStep):
    """Step that executes selected tools"""
    
    def __init__(self, tool_registry):
        self.tool_registry = tool_registry
    
    @property
    def name(self) -> str:
        return "tool_execution"
    
    def can_skip(self, context: ProcessingContext) -> bool:
        """Skip if no tool selected"""
        return context.selected_tool is None
    
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Execute the selected tool"""
        if context.selected_tool:
            try:
                tool = self.tool_registry.get_tool(context.selected_tool)
                if tool:
                    result = tool.execute(context.user_input, context.raw_context)
                    context.tool_result = result
                    context.metadata["tool_executed_at"] = time.time()
            except Exception as e:
                print(f"Tool execution error: {e}")
                context.tool_result = {"success": False, "error": str(e)}
        
        return context

class ResponseGenerationStep(ProcessingStep):
    """Step that generates the final response"""
    
    def __init__(self, llm_caller):
        self.llm_caller = llm_caller
    
    @property
    def name(self) -> str:
        return "response_generation"
    
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Generate the final response"""
        try:
            if context.tool_result:
                # Handle tool results
                if context.tool_result.get("success"):
                    if context.selected_tool == "calculator":
                        # For calculator, return clean result
                        context.response = str(context.tool_result.get("result", ""))
                    elif context.selected_tool == "knowledge_graph":
                        # Special handling for knowledge graph results
                        context.response = self._interpret_knowledge_graph_result(context.tool_result, context.user_input)
                    elif context.selected_tool == "web_search":
                        # Special handling for web search results
                        context.response = self._interpret_web_search_result(context.tool_result, context.user_input)
                    else:
                        # For other tools, generate contextual response
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
            print(f"Response generation error: {e}")
            context.response = "I encountered an error generating a response. Please try again."
        
        return context
    
    def _interpret_knowledge_graph_result(self, tool_result, user_input):
        """Interpret knowledge graph results intelligently and generically"""
        entities = tool_result.get("entities", [])
        if not entities:
            return "I don't have any information about that in my knowledge base."
        
        user_lower = user_input.lower()
        
        # Extract question type and subject from user input
        question_type, subject = self._analyze_question(user_lower)
        
        # Find relevant information based on question type
        if question_type == "personal_preference":
            return self._handle_personal_preference_question(entities, subject, user_lower)
        elif question_type == "general_knowledge":
            return self._handle_general_knowledge_question(entities, subject, user_lower)
        elif question_type == "specific_entity":
            return self._handle_specific_entity_question(entities, subject, user_lower)
        else:
            # Default response - use the tool's message
            return tool_result.get("message", "I found some information but I'm not sure how to interpret it for your question.")
    
    def _analyze_question(self, user_lower):
        """Analyze the user's question to determine type and subject"""
        # Personal preference questions
        preference_patterns = [
            r"what is my favorite (.+)",
            r"what's my favorite (.+)",
            r"my favorite (.+) is",
            r"do i like (.+)",
            r"do you know what i like",
            r"what do i like",
            r"tell me about my preferences"
        ]
        
        for pattern in preference_patterns:
            match = re.search(pattern, user_lower)
            if match:
                subject = match.group(1).strip() if match.groups() else "preferences"
                return "personal_preference", subject
        
        # General knowledge questions
        if any(phrase in user_lower for phrase in ["what do you know", "tell me about", "what information"]):
            return "general_knowledge", "everything"
        
        # Specific entity questions
        if any(phrase in user_lower for phrase in ["who is", "what is", "where is", "when is"]):
            # Extract the subject after the question word
            words = user_lower.split()
            if len(words) > 2:
                subject = " ".join(words[2:])
                return "specific_entity", subject
        
        return "general", "unknown"
    
    def _handle_personal_preference_question(self, entities, subject, user_lower):
        """Handle questions about personal preferences"""
        preferences = []
        
        # Look for user entity and their likes (outgoing relations)
        user_entity = None
        for entity in entities:
            if entity.get("name") == "user":
                user_entity = entity
                break
        
        if user_entity:
            relations = user_entity.get("relations", [])
            for rel in relations:
                if rel.get("relation") == "likes":
                    target = rel.get("target", "")
                    if target and target != "user":  # Avoid self-references
                        preferences.append(target)
        
        # Also look for entities that like the user (incoming relations)
        for entity in entities:
            if entity.get("name") != "user":
                relations = entity.get("relations", [])
                for rel in relations:
                    if rel.get("relation") in ["liked_by", "likes"] and rel.get("target") == "user":
                        entity_name = entity.get("name", "")
                        if entity_name and entity_name not in preferences:
                            preferences.append(entity_name)
        
        if not preferences:
            return "I don't have information about your preferences."
        
        # Format response based on subject
        if "favorite" in user_lower and subject != "preferences":
            # Look for specific type of preference
            for pref in preferences:
                if subject.lower() in pref.lower() or pref.lower() in subject.lower():
                    return f"Your favorite {subject} is {pref}!"
            
            # If no specific match, return what we have
            if len(preferences) == 1:
                return f"Based on what I know, you like {preferences[0]}."
            else:
                return f"Based on what I know, you like: {', '.join(preferences)}."
        elif "hobby" in user_lower or "hobbies" in user_lower:
            # Filter for hobby-related preferences
            hobby_prefs = [p for p in preferences if any(word in p.lower() for word in ['guitar', 'playing', 'music', 'reading', 'writing', 'drawing', 'painting', 'sports', 'hiking', 'running', 'swimming'])]
            if hobby_prefs:
                if len(hobby_prefs) == 1:
                    return f"Based on what I know, your hobby is {hobby_prefs[0]}."
                else:
                    return f"Based on what I know, your hobbies include: {', '.join(hobby_prefs)}."
            else:
                return f"Based on what I know, you like: {', '.join(preferences)}."
        elif "hobby" in subject.lower() or "hobbies" in subject.lower():
            # Filter for hobby-related preferences when subject mentions hobbies
            hobby_prefs = [p for p in preferences if any(word in p.lower() for word in ['guitar', 'playing', 'music', 'reading', 'writing', 'drawing', 'painting', 'sports', 'hiking', 'running', 'swimming'])]
            if hobby_prefs:
                if len(hobby_prefs) == 1:
                    return f"Based on what I know, your hobby is {hobby_prefs[0]}."
                else:
                    return f"Based on what I know, your hobbies include: {', '.join(hobby_prefs)}."
            else:
                return f"Based on what I know, you like: {', '.join(preferences)}."
        elif "food" in user_lower or "eat" in user_lower:
            # Filter for food-related preferences
            food_prefs = [p for p in preferences if any(word in p.lower() for word in ['sushi', 'pizza', 'pasta', 'burger', 'chicken', 'beef', 'fish', 'vegetable', 'fruit', 'cake', 'cookie', 'ice cream'])]
            if food_prefs:
                if len(food_prefs) == 1:
                    return f"Based on what I know, your favorite food is {food_prefs[0]}."
                else:
                    return f"Based on what I know, your favorite foods include: {', '.join(food_prefs)}."
            else:
                return f"Based on what I know, you like: {', '.join(preferences)}."
        else:
            # General preferences question
            if len(preferences) == 1:
                return f"Based on what I know, you like {preferences[0]}."
            else:
                return f"Based on what I know, you like: {', '.join(preferences)}."
    
    def _handle_general_knowledge_question(self, entities, subject, user_lower):
        """Handle general knowledge questions"""
        response_parts = []
        
        for entity in entities:
            name = entity.get("name", "")
            entity_type = entity.get("type", "")
            relations = entity.get("relations", [])
            
            if relations:
                rel_text = []
                for rel in relations:
                    rel_text.append(f"{rel['relation']} {rel['target']}")
                response_parts.append(f"{name} ({entity_type}): {', '.join(rel_text)}")
            else:
                response_parts.append(f"{name} ({entity_type})")
        
        if response_parts:
            return f"Here's what I know: {'; '.join(response_parts)}"
        else:
            return "I don't have much information stored about that topic."
    
    def _handle_specific_entity_question(self, entities, subject, user_lower):
        """Handle questions about specific entities"""
        # Look for entities that match the subject
        matching_entities = []
        for entity in entities:
            name = entity.get("name", "").lower()
            if subject.lower() in name or name in subject.lower():
                matching_entities.append(entity)
        
        if not matching_entities:
            return f"I don't have specific information about {subject}."
        
        # Return information about the matching entities
        response_parts = []
        for entity in matching_entities:
            name = entity.get("name", "")
            entity_type = entity.get("type", "")
            relations = entity.get("relations", [])
            
            if relations:
                rel_text = []
                for rel in relations:
                    rel_text.append(f"{rel['relation']} {rel['target']}")
                response_parts.append(f"{name} ({entity_type}): {', '.join(rel_text)}")
            else:
                response_parts.append(f"{name} ({entity_type})")
        
        return f"Here's what I know about {subject}: {'; '.join(response_parts)}"
    
    def _interpret_web_search_result(self, tool_result, user_input):
        """Interpret web search results and generate a natural response"""
        results = tool_result.get("results", [])
        summary = tool_result.get("summary", "")
        query = tool_result.get("query", user_input)
        
        if not results:
            return f"I searched for '{query}' but didn't find any relevant results. Could you try rephrasing your question?"
        
        # Check if this is a weather query and results aren't weather-related
        if 'weather' in user_input.lower() and not any('weather' in str(result).lower() for result in results):
            return f"""I searched for current weather information for you, but I wasn't able to find real-time weather data through my search. 

For the most accurate and up-to-date weather information, I recommend checking:
- Weather.com or Weather Channel
- AccuWeather
- Your local weather app
- National Weather Service (weather.gov)

These sources provide current conditions, forecasts, and weather alerts that are updated regularly."""
        
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
                primary_source = results[0].url if hasattr(results[0], 'url') else results[0].get('url', '')
                if primary_source:
                    response += f"\n\n(Source: {primary_source})"
            
            return response
        except Exception as e:
            print(f"Error generating web search response: {e}")
            return f"Based on my search for '{query}': {summary}"

class KnowledgeExtractionStep(ProcessingStep):
    """Step that extracts knowledge from user input"""
    
    def __init__(self, knowledge_extractor):
        self.knowledge_extractor = knowledge_extractor
    
    @property
    def name(self) -> str:
        return "knowledge_extraction"
    
    def can_skip(self, context: ProcessingContext) -> bool:
        """Skip for calculator queries"""
        return context.selected_tool == "calculator"
    
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Extract knowledge from user input"""
        try:
            knowledge_items = self.knowledge_extractor.extract(
                context.user_input, context.raw_context
            )
            context.extracted_knowledge = knowledge_items
            context.metadata["knowledge_extracted_at"] = time.time()
        except Exception as e:
            print(f"Knowledge extraction error: {e}")
            context.extracted_knowledge = []
        
        return context

class MemoryStorageStep(ProcessingStep):
    """Enhanced step that stores conversation and knowledge in memory"""
    
    def __init__(self, storage_module, embeddings_module):
        self.storage = storage_module
        self.embeddings = embeddings_module
        self.memory_enhancer = MemoryEnhancer(storage_module, embeddings_module)
    
    @property
    def name(self) -> str:
        return "memory_storage"
    
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Store conversation and extracted knowledge with enhanced memory extraction"""
        try:
            # Store episodic memory
            user_id = self.storage.insert_episodic("user", context.user_input)
            user_emb = self.embeddings.embed_text(context.user_input)
            self.storage.upsert_vector("episodic", user_id, user_emb)
            
            agent_id = self.storage.insert_episodic("assistant", context.response)
            agent_emb = self.embeddings.embed_text(context.response)
            self.storage.upsert_vector("episodic", agent_id, agent_emb)
            
            # Enhanced memory extraction for semantic facts and skills
            memory_results = self.memory_enhancer.process_conversation(
                context.user_input, context.response
            )
            
            # Store successful calculations as semantic facts (legacy)
            if (context.selected_tool == "calculator" and 
                context.tool_result and context.tool_result.get("success")):
                expr = context.tool_result.get("expression", "")
                result = context.tool_result.get("result", "")
                fact_id = self.storage.insert_semantic(f"calculation_{expr}", str(result), "calculator")
                fact_emb = self.embeddings.embed_text(f"calculation {expr} equals {result}")
                self.storage.upsert_vector("semantic", fact_id, fact_emb)
            
            # Update knowledge graph
            kg = context.raw_context.get("kg")
            if kg and context.extracted_knowledge:
                for item in context.extracted_knowledge:
                    entity = item.get("entity", "")
                    etype = item.get("type", "entity")
                    relation = item.get("relation", "related_to")
                    target = item.get("target", "user")
                    replaces = item.get("replaces", False)
                    
                    if entity and relation:
                        kg.upsert_entity(entity, etype)
                        kg.upsert_entity(target, "person")
                        
                        if replaces:
                            kg.update_relation(target, relation, entity)
                        else:
                            kg.upsert_relation(target, relation, entity)
            
            # Store memory extraction results in metadata
            context.metadata["memory_extraction_results"] = memory_results
            context.metadata["memory_stored_at"] = time.time()
            
            # Log memory extraction results
            if memory_results["stored_facts"] > 0 or memory_results["stored_skills"] > 0:
                print(f"Memory extracted: {memory_results['stored_facts']} facts, {memory_results['stored_skills']} skills")
            
        except Exception as e:
            print(f"Memory storage error: {e}")
        
        return context

class ReflectionStep(ProcessingStep):
    """Step that performs periodic reflection"""
    
    def __init__(self, storage_module, embeddings_module, reflection_interval=5):
        self.storage = storage_module
        self.embeddings = embeddings_module
        self.reflection_interval = reflection_interval
        self.turn_counter = 0
    
    @property
    def name(self) -> str:
        return "reflection"
    
    def can_skip(self, context: ProcessingContext) -> bool:
        """Skip unless it's time for reflection"""
        self.turn_counter += 1
        return self.turn_counter % self.reflection_interval != 0
    
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Perform reflection on recent interactions"""
        try:
            # Get recent context for reflection
            recent_context = context.metadata.get("recent_interactions", "")
            if recent_context:
                summary = f"Session reflection: user engaged with topics involving {context.user_input[:50]}..."
                skill_id = self.storage.insert_skill(summary, {"type": "reflection", "turn": self.turn_counter})
                skill_emb = self.embeddings.embed_text(summary)
                self.storage.upsert_vector("skills", skill_id, skill_emb)
                
                context.metadata["reflected_at"] = time.time()
        except Exception as e:
            print(f"Reflection error: {e}")
        
        return context

class ProcessingPipeline:
    """Configurable processing pipeline"""
    
    def __init__(self):
        self.steps: List[ProcessingStep] = []
        self.middleware: List[Callable] = []
    
    def add_step(self, step: ProcessingStep, position: Optional[int] = None):
        """Add a processing step"""
        if position is None:
            self.steps.append(step)
        else:
            self.steps.insert(position, step)
    
    def remove_step(self, step_name: str):
        """Remove a processing step"""
        self.steps = [step for step in self.steps if step.name != step_name]
    
    def add_middleware(self, middleware_func: Callable):
        """Add middleware function that runs before each step"""
        self.middleware.append(middleware_func)
    
    def process(self, user_input: str, raw_context: Dict[str, Any] = None) -> str:
        """Process user input through the pipeline"""
        context = ProcessingContext(user_input=user_input, raw_context=raw_context or {})
        
        for step in self.steps:
            try:
                # Run middleware
                for middleware in self.middleware:
                    middleware(context, step)
                
                # Skip step if conditions are met
                if step.can_skip(context):
                    continue
                
                # Process the step
                context = step.process(context)
                
            except Exception as e:
                print(f"Error in step {step.name}: {e}")
                continue
        
        return context.response

# Example pipeline factory
class PipelineFactory:
    """Factory for creating common pipeline configurations"""
    
    @staticmethod
    def create_default_pipeline(llm_caller, tool_registry, memory_manager, 
                               knowledge_extractor, storage_module, embeddings_module):
        """Create the default processing pipeline"""
        pipeline = ProcessingPipeline()
        
        # Add steps in order
        pipeline.add_step(ContextBuildingStep(memory_manager))
        pipeline.add_step(PlanningStep(llm_caller, tool_registry))
        pipeline.add_step(ToolExecutionStep(tool_registry))
        pipeline.add_step(ResponseGenerationStep(llm_caller))
        pipeline.add_step(KnowledgeExtractionStep(knowledge_extractor))
        pipeline.add_step(MemoryStorageStep(storage_module, embeddings_module))
        pipeline.add_step(ReflectionStep(storage_module, embeddings_module))
        
        return pipeline
    
    @staticmethod
    def create_simple_pipeline(llm_caller, tool_registry):
        """Create a simple pipeline without memory/knowledge features"""
        pipeline = ProcessingPipeline()
        
        pipeline.add_step(PlanningStep(llm_caller, tool_registry))
        pipeline.add_step(ToolExecutionStep(tool_registry))
        pipeline.add_step(ResponseGenerationStep(llm_caller))
        
        return pipeline
    
    @staticmethod
    def create_memory_focused_pipeline(llm_caller, memory_manager, 
                                     storage_module, embeddings_module):
        """Create a pipeline focused on memory without tools"""
        pipeline = ProcessingPipeline()
        
        pipeline.add_step(ContextBuildingStep(memory_manager))
        pipeline.add_step(ResponseGenerationStep(llm_caller))
        pipeline.add_step(MemoryStorageStep(storage_module, embeddings_module))
        pipeline.add_step(ReflectionStep(storage_module, embeddings_module))
        
        return pipeline