# memory_strategies.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple
import storage
import embeddings

class MemoryStrategy(ABC):
    """Base class for memory retrieval strategies"""
    
    @abstractmethod
    def retrieve_context(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Retrieve relevant context lines"""
        pass

class DefaultMemoryStrategy(MemoryStrategy):
    """Default memory retrieval strategy"""
    
    def __init__(self, episodic_k=3, semantic_k=2, skills_k=2, kg_entities=3):
        self.episodic_k = episodic_k
        self.semantic_k = semantic_k
        self.skills_k = skills_k
        self.kg_entities = kg_entities
    
    def retrieve_context(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Retrieve context using embeddings and KG"""
        context_lines = []
        kg = context.get('kg')
        
        try:
            # Get query embedding
            query_emb = embeddings.embed_text(query)
            
            # Retrieve from episodic memory
            episodic_ids = storage.nearest("episodic", query_emb, k=self.episodic_k)
            if episodic_ids:
                episodic_items = storage.get_episodic_by_ids(episodic_ids)
                for role, text, ts in episodic_items:
                    context_lines.append(f"Memory ({role}): {text[:100]}...")
            
            # Retrieve from semantic memory  
            semantic_ids = storage.nearest("semantic", query_emb, k=self.semantic_k)
            if semantic_ids:
                semantic_items = storage.get_semantic_by_ids(semantic_ids)
                for key, value, source, ts in semantic_items:
                    context_lines.append(f"Knowledge: {key} = {value}")
            
            # Retrieve from skills
            skill_ids = storage.nearest("skills", query_emb, k=self.skills_k)
            if skill_ids:
                skill_items = storage.get_skills_by_ids(skill_ids)
                for note, meta, ts in skill_items:
                    context_lines.append(f"Learning: {note}")
            
            # Add KG context
            if kg:
                entities = kg.search_entities(query, limit=self.kg_entities)
                for entity in entities:
                    info = kg.get_entity_info(entity)
                    if info:
                        context_lines.append(f"Entity: {entity} ({info['type']})")
                        related = kg.get_related_concepts(entity, max_out=2)
                        for rel_entity, relation in related:
                            context_lines.append(f"  {entity} {relation} {rel_entity}")
                        
        except Exception as e:
            print(f"Context building error: {e}")
            context_lines.append("Recent conversation context available.")
        
        return context_lines

class AdaptiveMemoryStrategy(MemoryStrategy):
    """Adaptive memory strategy that adjusts based on query type"""
    
    def __init__(self):
        self.query_profiles = {
            "personal": {"episodic_k": 5, "semantic_k": 4, "skills_k": 1, "kg_entities": 5},
            "factual": {"episodic_k": 1, "semantic_k": 5, "skills_k": 3, "kg_entities": 2},
            "conversational": {"episodic_k": 4, "semantic_k": 1, "skills_k": 1, "kg_entities": 1},
            "default": {"episodic_k": 3, "semantic_k": 2, "skills_k": 2, "kg_entities": 3}
        }
    
    def _classify_query(self, query: str) -> str:
        """Classify query type to determine memory strategy"""
        query_lower = query.lower()
        
        # Personal queries
        personal_indicators = ["my", "me", "i am", "i like", "my favorite"]
        if any(indicator in query_lower for indicator in personal_indicators):
            return "personal"
        
        # Factual queries
        factual_indicators = ["what is", "how to", "explain", "define"]
        if any(indicator in query_lower for indicator in factual_indicators):
            return "factual"
        
        # Conversational queries
        conversational_indicators = ["hello", "hi", "how are you", "thanks", "bye"]
        if any(indicator in query_lower for indicator in conversational_indicators):
            return "conversational"
        
        return "default"
    
    def retrieve_context(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Retrieve context using adaptive strategy"""
        query_type = self._classify_query(query)
        profile = self.query_profiles[query_type]
        
        # Use DefaultMemoryStrategy with adaptive parameters
        strategy = DefaultMemoryStrategy(
            episodic_k=profile["episodic_k"],
            semantic_k=profile["semantic_k"],
            skills_k=profile["skills_k"],
            kg_entities=profile["kg_entities"]
        )
        
        return strategy.retrieve_context(query, context)

class RecentMemoryStrategy(MemoryStrategy):
    """Strategy that prioritizes recent memories"""
    
    def __init__(self, max_items=10):
        self.max_items = max_items
    
    def retrieve_context(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Retrieve only the most recent memories"""
        context_lines = []
        
        try:
            # Get recent episodic memories
            with storage.get_db() as conn:
                recent_episodes = conn.execute(
                    "SELECT role, text, ts FROM episodic ORDER BY ts DESC LIMIT ?",
                    (self.max_items,)
                ).fetchall()
            
            for role, text, ts in recent_episodes:
                context_lines.append(f"Recent ({role}): {text[:80]}...")
            
            # Add some KG context if available
            kg = context.get('kg')
            if kg:
                entities = kg.search_entities(query, limit=2)
                for entity in entities:
                    info = kg.get_entity_info(entity)
                    if info:
                        context_lines.append(f"Known: {entity} ({info['type']})")
        
        except Exception as e:
            print(f"Recent memory error: {e}")
        
        return context_lines

class PrioritizedMemoryStrategy(MemoryStrategy):
    """Strategy that weights different memory types"""
    
    def __init__(self, weights=None):
        self.weights = weights or {
            "episodic": 0.3,
            "semantic": 0.4,
            "skills": 0.2,
            "kg": 0.1
        }
    
    def retrieve_context(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Retrieve context with weighted importance"""
        context_lines = []
        
        try:
            query_emb = embeddings.embed_text(query)
            
            # Calculate k values based on weights
            total_items = 10
            episodic_k = max(1, int(total_items * self.weights["episodic"]))
            semantic_k = max(1, int(total_items * self.weights["semantic"]))
            skills_k = max(1, int(total_items * self.weights["skills"]))
            kg_k = max(1, int(total_items * self.weights["kg"]))
            
            # Retrieve with calculated weights
            strategy = DefaultMemoryStrategy(episodic_k, semantic_k, skills_k, kg_k)
            context_lines = strategy.retrieve_context(query, context)
            
        except Exception as e:
            print(f"Prioritized memory error: {e}")
        
        return context_lines

class EnhancedMemoryStrategy(MemoryStrategy):
    """Enhanced strategy that better utilizes semantic and skills memory"""
    
    def __init__(self, weights=None):
        self.weights = weights or {
            "episodic": 0.2,
            "semantic": 0.5,
            "skills": 0.3,
            "kg": 0.0
        }
    
    def retrieve_context(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Retrieve context with enhanced semantic and skills utilization"""
        context_lines = []
        
        try:
            query_emb = embeddings.embed_text(query)
            
            # Calculate k values based on weights
            total_items = 12  # Increased for better coverage
            episodic_k = max(1, int(total_items * self.weights["episodic"]))
            semantic_k = max(1, int(total_items * self.weights["semantic"]))
            skills_k = max(1, int(total_items * self.weights["skills"]))
            kg_k = max(1, int(total_items * self.weights["kg"]))
            
            # Retrieve episodic memories
            if episodic_k > 0:
                episodic_ids = storage.nearest("episodic", query_emb, k=episodic_k)
                if episodic_ids:
                    episodic_items = storage.get_episodic_by_ids(episodic_ids)
                    for role, text, ts in episodic_items:
                        context_lines.append(f"Memory ({role}): {text[:80]}...")
            
            # Enhanced semantic memory retrieval
            if semantic_k > 0:
                semantic_ids = storage.nearest("semantic", query_emb, k=semantic_k)
                if semantic_ids:
                    semantic_items = storage.get_semantic_by_ids(semantic_ids)
                    for key, value, source, ts in semantic_items:
                        # Format semantic facts more clearly
                        fact_type = self._extract_fact_type(key)
                        context_lines.append(f"Fact ({fact_type}): {key} = {value}")
            
            # Enhanced skills memory retrieval
            if skills_k > 0:
                skill_ids = storage.nearest("skills", query_emb, k=skills_k)
                if skill_ids:
                    skill_items = storage.get_skills_by_ids(skill_ids)
                    for note, meta, ts in skill_items:
                        skill_type = meta.get("type", "general") if isinstance(meta, dict) else "general"
                        context_lines.append(f"Learning ({skill_type}): {note}")
            
            # Knowledge graph retrieval
            if kg_k > 0:
                kg = context.get("kg")
                if kg:
                    entities = kg.search_entities(query, max_results=kg_k)
                    for entity in entities:
                        info = kg.get_entity_info(entity)
                        if info:
                            related = kg.get_related_concepts(entity, max_out=3)
                            rel_text = ", ".join([f"{rel} {target}" for target, rel in related[:3]])
                            context_lines.append(f"Knowledge: {entity} ({info.get('type', 'entity')}) - {rel_text}")
            
        except Exception as e:
            print(f"Enhanced memory error: {e}")
        
        return context_lines
    
    def _extract_fact_type(self, key: str) -> str:
        """Extract fact type from key for better formatting"""
        if "personal_info" in key:
            return "personal"
        elif "preferences" in key:
            return "preference"
        elif "capabilities" in key:
            return "skill"
        elif "relationships" in key:
            return "relationship"
        elif "world_facts" in key:
            return "fact"
        elif "calculation" in key:
            return "calculation"
        else:
            return "general"

class MemoryManager:
    """Manages different memory strategies"""
    
    def __init__(self):
        self.strategies = {
            "default": DefaultMemoryStrategy(),
            "adaptive": AdaptiveMemoryStrategy(),
            "recent": RecentMemoryStrategy(),
            "prioritized": PrioritizedMemoryStrategy(),
            "enhanced": EnhancedMemoryStrategy()
        }
        self.current_strategy = "enhanced"  # Use enhanced by default
    
    def set_strategy(self, strategy_name: str):
        """Set the active memory strategy"""
        if strategy_name in self.strategies:
            self.current_strategy = strategy_name
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")
    
    def add_strategy(self, name: str, strategy: MemoryStrategy):
        """Add a custom memory strategy"""
        self.strategies[name] = strategy
    
    def get_context(self, query: str, context: Dict[str, Any]) -> str:
        """Get context using the current strategy"""
        strategy = self.strategies[self.current_strategy]
        context_lines = strategy.retrieve_context(query, context)
        return "\n".join(context_lines) if context_lines else "No relevant context found."
    
    def list_strategies(self) -> List[str]:
        """List available strategies"""
        return list(self.strategies.keys())