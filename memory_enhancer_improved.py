"""
Improved MemoryEnhancer that properly integrates with KG and coordinates extraction
"""
from typing import Dict, Any, List
from memory_extractors import SemanticFactExtractor, SkillsExtractor

class ImprovedMemoryEnhancer:
    """Enhanced memory enhancer that coordinates all extraction and storage"""
    
    def __init__(self, storage_module, embeddings_module, kg=None):
        self.storage = storage_module
        self.embeddings = embeddings_module
        self.kg = kg
        self.semantic_extractor = SemanticFactExtractor()
        self.skills_extractor = SkillsExtractor()
        
        # Track what's been processed to avoid duplicates
        self.processed_facts = set()
        self.processed_skills = set()
    
    def process_conversation(self, user_input: str, agent_response: str) -> Dict[str, Any]:
        """Process a conversation turn and extract memories with KG integration"""
        results = {
            "semantic_facts": [],
            "kg_relations": [],
            "skills": [],
            "stored_facts": 0,
            "stored_relations": 0,
            "stored_skills": 0
        }
        
        # Extract from user input
        user_facts = self.semantic_extractor.extract_facts(user_input, "user")
        user_skills = self.skills_extractor.extract_skills(user_input, "user")
        
        # Extract from agent response
        agent_facts = self.semantic_extractor.extract_facts(agent_response, "assistant")
        agent_skills = self.skills_extractor.extract_skills(agent_response, "assistant")
        
        # Process facts with intelligent routing
        for fact in user_facts + agent_facts:
            if fact["confidence"] > 0.6:
                stored = self._route_and_store_fact(fact, results)
                if stored:
                    results["stored_facts"] += 1
        
        # Process skills
        for skill in user_skills + agent_skills:
            if skill["confidence"] > 0.6:
                stored = self._store_skill(skill, results)
                if stored:
                    results["stored_skills"] += 1
        
        # Extract implicit relationships from conversation patterns
        implicit_relations = self._extract_implicit_relations(user_input, agent_response)
        for relation in implicit_relations:
            if self._store_relation(relation, results):
                results["stored_relations"] += 1
        
        return results
    
    def _route_and_store_fact(self, fact: Dict[str, Any], results: Dict) -> bool:
        """Route fact to appropriate storage (KG relation vs semantic fact)"""
        fact_key = fact["key"].lower()
        fact_hash = f"{fact_key}:{fact['value']}"
        
        # Check if already processed
        if fact_hash in self.processed_facts:
            return False
        
        # Determine if this should be a KG relation
        if self._is_relational_fact(fact):
            # Convert to relation and store in KG
            relation = self._fact_to_relation(fact)
            if relation and self.kg:
                self.kg.upsert_entity(relation["subject"], "person")
                self.kg.upsert_entity(relation["object"], relation.get("object_type", "entity"))
                self.kg.upsert_relation(
                    relation["subject"],
                    relation["predicate"],
                    relation["object"],
                    weight=fact.get("confidence", 1.0)
                )
                results["kg_relations"].append(relation)
                self.processed_facts.add(fact_hash)
                return True
        
        # Store as semantic fact
        fact_id = self.storage.insert_semantic(
            fact["key"],
            fact["value"],
            fact.get("source", "extracted")
        )
        fact_emb = self.embeddings.embed_text(f"{fact['key']}: {fact['value']}")
        self.storage.upsert_vector("semantic", fact_id, fact_emb)
        results["semantic_facts"].append(fact)
        self.processed_facts.add(fact_hash)
        return True
    
    def _is_relational_fact(self, fact: Dict) -> bool:
        """Determine if a fact represents a relationship"""
        relational_patterns = [
            ("favorite", "likes"),
            ("likes", "likes"),
            ("loves", "likes"),
            ("prefers", "prefers"),
            ("lives_in", "lives_in"),
            ("works_at", "works_at"),
            ("works_as", "works_as"),
            ("owns", "owns"),
            ("has", "has"),
            ("friend", "friend_of"),
            ("knows", "knows")
        ]
        
        fact_key_lower = fact["key"].lower()
        for pattern, _ in relational_patterns:
            if pattern in fact_key_lower:
                return True
        return False
    
    def _fact_to_relation(self, fact: Dict) -> Dict:
        """Convert a fact to a KG relation"""
        fact_key = fact["key"].lower()
        
        # Parse subject from fact key
        if "user_" in fact_key:
            subject = "user"
        elif "assistant_" in fact_key:
            subject = "assistant"
        else:
            subject = fact.get("speaker", "user")
        
        # Determine predicate and object type
        relational_mappings = {
            "favorite_color": ("likes", "color"),
            "favorite_food": ("likes", "food"),
            "favorite": ("likes", "preference"),
            "lives": ("lives_in", "location"),
            "works": ("works_at", "organization"),
            "profession": ("works_as", "profession"),
            "friend": ("friend_of", "person"),
            "owns": ("owns", "possession"),
            "has": ("has", "attribute")
        }
        
        predicate = "related_to"
        object_type = "entity"
        
        for key_pattern, (pred, obj_type) in relational_mappings.items():
            if key_pattern in fact_key:
                predicate = pred
                object_type = obj_type
                break
        
        return {
            "subject": subject,
            "predicate": predicate,
            "object": fact["value"],
            "object_type": object_type
        }
    
    def _store_skill(self, skill: Dict, results: Dict) -> bool:
        """Store a skill/learning with deduplication"""
        skill_hash = skill["note"][:100]
        
        if skill_hash in self.processed_skills:
            return False
        
        skill_id = self.storage.insert_skill(skill["note"], skill.get("meta", {}))
        skill_emb = self.embeddings.embed_text(skill["note"])
        self.storage.upsert_vector("skills", skill_id, skill_emb)
        results["skills"].append(skill)
        self.processed_skills.add(skill_hash)
        return True
    
    def _store_relation(self, relation: Dict, results: Dict) -> bool:
        """Store a relation in the KG"""
        if not self.kg:
            return False
        
        self.kg.upsert_entity(relation["subject"], relation.get("subject_type", "entity"))
        self.kg.upsert_entity(relation["object"], relation.get("object_type", "entity"))
        self.kg.upsert_relation(
            relation["subject"],
            relation["predicate"],
            relation["object"],
            weight=relation.get("confidence", 1.0)
        )
        results["kg_relations"].append(relation)
        return True
    
    def _extract_implicit_relations(self, user_input: str, agent_response: str) -> List[Dict]:
        """Extract implicit relationships from conversation patterns"""
        relations = []
        
        # Pattern: User asks about something and agent confirms -> user interested_in topic
        if "?" in user_input and any(word in agent_response.lower() for word in ["yes", "correct", "right"]):
            # Extract main topic from question
            import re
            topic_match = re.search(r'about (\w+)', user_input.lower())
            if topic_match:
                relations.append({
                    "subject": "user",
                    "predicate": "interested_in",
                    "object": topic_match.group(1),
                    "object_type": "topic",
                    "confidence": 0.7
                })
        
        # Pattern: User thanks agent -> positive interaction
        if any(word in user_input.lower() for word in ["thanks", "thank you", "helpful"]):
            relations.append({
                "subject": "user",
                "predicate": "satisfied_with",
                "object": "interaction",
                "object_type": "event",
                "confidence": 0.9
            })
        
        return relations
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get summary of extracted memories"""
        with self.storage.get_db() as conn:
            semantic_count = conn.execute("SELECT COUNT(*) FROM semantic").fetchone()[0]
            skills_count = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
            
            recent_facts = conn.execute("""
                SELECT key, value, source, ts FROM semantic 
                WHERE source NOT LIKE '%superseded%'
                ORDER BY ts DESC LIMIT 5
            """).fetchall()
            
            recent_skills = conn.execute("""
                SELECT note, meta, ts FROM skills 
                ORDER BY ts DESC LIMIT 5
            """).fetchall()
        
        kg_stats = {}
        if self.kg:
            kg_stats = {
                "entities": len(self.kg.G.nodes()),
                "relations": len(self.kg.G.edges())
            }
        
        return {
            "semantic_facts_count": semantic_count,
            "skills_count": skills_count,
            "kg_stats": kg_stats,
            "recent_facts": [{"key": k, "value": v, "source": s} for k, v, s, _ in recent_facts],
            "recent_skills": [{"note": n, "meta": m} for n, m, _ in recent_skills],
            "processed_facts": len(self.processed_facts),
            "processed_skills": len(self.processed_skills)
        }
    
    def clear_cache(self):
        """Clear processed items cache (call periodically to allow re-processing)"""
        # Keep only recent items to prevent unbounded growth
        if len(self.processed_facts) > 1000:
            self.processed_facts = set(list(self.processed_facts)[-500:])
        if len(self.processed_skills) > 500:
            self.processed_skills = set(list(self.processed_skills)[-250:])
