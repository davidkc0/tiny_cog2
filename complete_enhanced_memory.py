"""
Complete enhanced memory storage with improved MemoryEnhancer integration
Builds on your implementation with additional improvements
"""
from processing_pipeline import ProcessingStep, ProcessingContext
from memory_enhancer_improved import ImprovedMemoryEnhancer
from memory_extractors import SemanticFactExtractor, SkillsExtractor
import time
import json
import re

class CompleteEnhancedMemoryStorageStep(ProcessingStep):
    """Complete enhanced memory storage with all improvements integrated"""
    
    def __init__(self, storage_module, embeddings_module, kg=None, llm_caller=None):
        self.storage = storage_module
        self.embeddings = embeddings_module
        self.kg = kg
        self.llm_caller = llm_caller  # For intelligent reflection generation
        
        # Use improved memory enhancer
        self.memory_enhancer = ImprovedMemoryEnhancer(storage_module, embeddings_module, kg)
        
        # Additional extractors for direct use
        self.semantic_extractor = SemanticFactExtractor()
        self.skills_extractor = SkillsExtractor()
        
        # Reflection management
        self.conversation_buffer = []
        self.reflection_counter = 0
        
        # Enhanced statistics
        self.stats = {
            "total_facts_extracted": 0,
            "total_skills_extracted": 0,
            "total_kg_updates": 0,
            "total_tool_results_stored": 0,
            "total_reflections": 0,
            "memory_effectiveness": 0.0
        }
    
    @property
    def name(self) -> str:
        return "complete_enhanced_memory_storage"
    
    def process(self, context: ProcessingContext) -> ProcessingContext:
        """Process with complete memory system integration"""
        try:
            # 1. Store episodic memory
            user_id = self._store_episodic("user", context.user_input)
            agent_id = self._store_episodic("assistant", context.response)
            
            # 2. Use improved MemoryEnhancer for coordinated extraction
            memory_results = self.memory_enhancer.process_conversation(
                context.user_input,
                context.response
            )
            
            # 3. Process knowledge extractor results (from pipeline)
            kg_updates = self._process_extracted_knowledge(context)
            
            # 4. Store and enrich tool results
            tool_results = self._process_tool_results(context)
            
            # 5. Generate intelligent reflections
            reflection = self._generate_intelligent_reflection(context)
            
            # 6. Calculate memory effectiveness
            effectiveness = self._calculate_memory_effectiveness(context, memory_results)
            
            # Update statistics
            self.stats["total_facts_extracted"] += memory_results["stored_facts"]
            self.stats["total_skills_extracted"] += memory_results["stored_skills"]
            self.stats["total_kg_updates"] += kg_updates + memory_results["stored_relations"]
            self.stats["total_tool_results_stored"] += tool_results
            if reflection:
                self.stats["total_reflections"] += 1
            self.stats["memory_effectiveness"] = effectiveness
            
            # Store comprehensive metadata
            context.metadata["memory_extraction_complete"] = {
                "facts_stored": memory_results["stored_facts"],
                "relations_stored": memory_results["stored_relations"],
                "skills_stored": memory_results["stored_skills"],
                "kg_updates": kg_updates,
                "tool_results": tool_results,
                "reflection_generated": bool(reflection),
                "effectiveness_score": effectiveness,
                "episodic_ids": [user_id, agent_id],
                "timestamp": time.time()
            }
            
            # Log significant extractions
            total_stored = (memory_results["stored_facts"] + 
                          memory_results["stored_relations"] + 
                          memory_results["stored_skills"])
            if total_stored > 0:
                print(f"Memory extracted: {memory_results['stored_facts']} facts, {memory_results['stored_skills']} skills")
            
            # Periodic cache clearing
            if self.reflection_counter % 50 == 0:
                self.memory_enhancer.clear_cache()
            
        except Exception as e:
            print(f"Complete memory storage error: {e}")
            import traceback
            traceback.print_exc()
        
        return context
    
    def _store_episodic(self, role: str, text: str) -> int:
        """Store episodic memory with embedding"""
        memory_id = self.storage.insert_episodic(role, text)
        embedding = self.embeddings.embed_text(text)
        self.storage.upsert_vector("episodic", memory_id, embedding)
        
        # Add to conversation buffer for reflection
        self.conversation_buffer.append({
            "role": role,
            "text": text,
            "timestamp": time.time()
        })
        
        # Trim buffer if too large
        if len(self.conversation_buffer) > 50:
            self.conversation_buffer = self.conversation_buffer[-30:]
        
        return memory_id
    
    def _process_extracted_knowledge(self, context: ProcessingContext) -> int:
        """Process knowledge from knowledge extraction step"""
        updates = 0
        
        if not context.extracted_knowledge or not self.kg:
            return 0
        
        for item in context.extracted_knowledge:
            entity = item.get("entity", "").strip()
            etype = item.get("type", "entity")
            relation = item.get("relation", "related_to")
            target = item.get("target", "user")
            replaces = item.get("replaces", False)
            
            if entity and relation:
                # Enhanced entity creation with attributes
                entity_attrs = self._extract_entity_attributes(entity, etype)
                self.kg.upsert_entity(entity, etype, **entity_attrs)
                
                target_attrs = {"type": "person"} if target == "user" else {}
                self.kg.upsert_entity(target, "person", **target_attrs)
                
                # Handle replacement intelligently
                if replaces:
                    # Remove old relations of this type
                    self.kg.update_relation(target, relation, entity)
                    print(f"   Updated: {target} {relation} {entity}")
                else:
                    # Add new relation with confidence
                    confidence = item.get("confidence", 1.0)
                    self.kg.upsert_relation(target, relation, entity, weight=confidence)
                
                updates += 1
                
                # Also store as searchable fact
                self._store_relation_as_fact(target, relation, entity)
        
        return updates
    
    def _extract_entity_attributes(self, entity: str, etype: str) -> dict:
        """Extract additional attributes for an entity"""
        attributes = {}
        
        # Add type-specific attributes
        if etype == "location":
            attributes["entity_class"] = "geographical"
        elif etype == "person":
            attributes["entity_class"] = "individual"
        elif etype in ["food", "color", "hobby"]:
            attributes["entity_class"] = "preference"
        
        # Add extraction metadata
        attributes["extracted_at"] = time.time()
        
        return attributes
    
    def _store_relation_as_fact(self, subject: str, relation: str, obj: str):
        """Store relation as searchable fact for redundancy"""
        fact_key = f"relation_{subject}_{relation}_{obj}".lower().replace(" ", "_")
        fact_value = f"{subject} {relation} {obj}"
        
        # Check if already exists
        existing = self._check_existing_fact(fact_key)
        if not existing:
            fact_id = self.storage.insert_semantic(fact_key, fact_value, "kg_relation")
            fact_emb = self.embeddings.embed_text(fact_value)
            self.storage.upsert_vector("semantic", fact_id, fact_emb)
    
    def _process_tool_results(self, context: ProcessingContext) -> int:
        """Process and enrich tool results"""
        if not context.tool_result or not context.tool_result.get("success"):
            return 0
        
        results_stored = 0
        
        if context.selected_tool == "calculator":
            results_stored += self._store_calculation_with_context(context)
            
        elif context.selected_tool == "web_search":
            results_stored += self._store_search_results_intelligently(context)
            
        elif context.selected_tool == "intelligent_knowledge":
            # Track knowledge graph query patterns
            self._track_kg_query_pattern(context)
        
        return results_stored
    
    def _store_calculation_with_context(self, context: ProcessingContext) -> int:
        """Store calculation with additional context"""
        if "expression" not in context.tool_result or "result" not in context.tool_result:
            return 0
        
        expr = context.tool_result["expression"]
        result = context.tool_result["result"]
        
        # Store basic calculation
        fact_key = f"calculation_{expr.replace(' ', '_')}"
        fact_id = self.storage.insert_semantic(fact_key, str(result), "calculator")
        
        # Store with natural language description
        description = f"calculation: {expr} equals {result}"
        fact_emb = self.embeddings.embed_text(description)
        self.storage.upsert_vector("semantic", fact_id, fact_emb)
        
        # Extract calculation pattern as skill
        if any(op in expr for op in ['+', '-', '*', '/']):
            skill_note = f"User performed arithmetic calculation: {expr}"
            skill_id = self.storage.insert_skill(skill_note, {
                "type": "calculation_pattern",
                "expression": expr,
                "result": result
            })
            skill_emb = self.embeddings.embed_text(skill_note)
            self.storage.upsert_vector("skills", skill_id, skill_emb)
            return 2
        
        return 1
    
    def _store_search_results_intelligently(self, context: ProcessingContext) -> int:
        """Store web search results with intelligent extraction"""
        results_stored = 0
        
        if "message" in context.tool_result:
            message = context.tool_result["message"]
            query = context.user_input
            
            # Extract different types of information
            extracted_data = {
                "prices": re.findall(r'\$[\d,]+\.?\d*', message),
                "percentages": re.findall(r'\d+\.?\d*%', message),
                "years": re.findall(r'\b(19|20)\d{2}\b', message),
                "quantities": re.findall(r'\b\d+[\w\s]+(?:million|billion|thousand)\b', message),
                "names": self._extract_proper_nouns(message)
            }
            
            # Store extracted information with context
            for data_type, values in extracted_data.items():
                for value in values[:3]:  # Limit to top 3 per type
                    fact_key = f"search_{data_type}_{query[:30].replace(' ', '_')}_{value[:20]}"
                    fact_id = self.storage.insert_semantic(
                        fact_key,
                        value,
                        f"web_search_{data_type}"
                    )
                    fact_emb = self.embeddings.embed_text(f"{query}: {value}")
                    self.storage.upsert_vector("semantic", fact_id, fact_emb)
                    results_stored += 1
            
            # Store search summary as skill/observation
            if results_stored > 0:
                skill_note = f"Web search for '{query[:50]}' found relevant information"
                skill_id = self.storage.insert_skill(skill_note, {
                    "type": "search_success",
                    "query": query,
                    "data_found": list(extracted_data.keys())
                })
                skill_emb = self.embeddings.embed_text(skill_note)
                self.storage.upsert_vector("skills", skill_id, skill_emb)
        
        return results_stored
    
    def _extract_proper_nouns(self, text: str) -> list:
        """Extract likely proper nouns (names, places, organizations)"""
        # Simple heuristic: capitalized words not at sentence start
        words = text.split()
        proper_nouns = []
        
        for i, word in enumerate(words):
            if i > 0 and word[0].isupper() and word.isalpha():
                # Not after period, question mark, or exclamation
                if words[i-1][-1] not in '.?!':
                    proper_nouns.append(word)
        
        return list(set(proper_nouns))[:5]
    
    def _track_kg_query_pattern(self, context: ProcessingContext):
        """Track how user queries knowledge graph"""
        query = context.user_input.lower()
        
        # Identify query type
        query_types = {
            "preference": ["favorite", "like", "prefer"],
            "information": ["what", "tell", "know"],
            "relationship": ["who", "friend", "family"],
            "location": ["where", "live", "from"]
        }
        
        identified_type = "general"
        for qtype, indicators in query_types.items():
            if any(ind in query for ind in indicators):
                identified_type = qtype
                break
        
        # Store query pattern
        skill_note = f"User queried knowledge graph for {identified_type} information"
        skill_id = self.storage.insert_skill(skill_note, {
            "type": "query_pattern",
            "query_type": identified_type,
            "query": query[:100]
        })
        skill_emb = self.embeddings.embed_text(skill_note)
        self.storage.upsert_vector("skills", skill_id, skill_emb)
    
    def _generate_intelligent_reflection(self, context: ProcessingContext) -> str:
        """Generate intelligent reflection using LLM or patterns"""
        self.reflection_counter += 1
        
        # Only reflect every N turns
        if self.reflection_counter % 10 != 0:
            return None
        
        if self.llm_caller and len(self.conversation_buffer) >= 5:
            # Use LLM for intelligent reflection
            recent_convs = self.conversation_buffer[-10:]
            conv_text = "\n".join([f"{c['role']}: {c['text'][:100]}" for c in recent_convs])
            
            prompt = f"""Analyze these recent conversations and generate ONE insightful observation.
Focus on: patterns, preferences, topics, communication style, or learning progress.

Conversations:
{conv_text}

Generate a concise insight (one sentence, max 100 chars):"""
            
            try:
                reflection = self.llm_caller(prompt, mode="answer").strip()[:100]
            except:
                reflection = self._generate_pattern_reflection()
        else:
            reflection = self._generate_pattern_reflection()
        
        if reflection:
            # Store reflection
            skill_id = self.storage.insert_skill(reflection, {
                "type": "reflection",
                "turn": self.reflection_counter,
                "conversations_analyzed": len(self.conversation_buffer)
            })
            skill_emb = self.embeddings.embed_text(reflection)
            self.storage.upsert_vector("skills", skill_id, skill_emb)
        
        return reflection
    
    def _generate_pattern_reflection(self) -> str:
        """Generate reflection based on patterns"""
        if not self.conversation_buffer:
            return None
        
        # Analyze patterns
        topics = []
        questions = 0
        tools_used = set()
        
        for conv in self.conversation_buffer[-10:]:
            text = conv["text"].lower()
            # Extract topics (words > 5 chars)
            topics.extend([w for w in text.split() if len(w) > 5 and w.isalpha()])
            if "?" in text:
                questions += 1
        
        # Generate reflection
        if topics:
            common_topic = max(set(topics), key=topics.count)
            return f"Frequent topic of interest: {common_topic}"
        elif questions > 5:
            return "User asks many questions, showing curiosity"
        else:
            return "Conversation patterns show engaged interaction"
    
    def _calculate_memory_effectiveness(self, context: ProcessingContext, 
                                       memory_results: dict) -> float:
        """Calculate how effectively memories are being used"""
        effectiveness = 0.0
        
        # Check if memories influenced response
        if context.metadata.get("memory_context_size", 0) > 0:
            effectiveness += 0.3
        
        # Check if extraction was successful
        total_extracted = (memory_results.get("stored_facts", 0) +
                         memory_results.get("stored_relations", 0) +
                         memory_results.get("stored_skills", 0))
        if total_extracted > 0:
            effectiveness += min(0.3, total_extracted * 0.1)
        
        # Check if tool results were stored
        if context.tool_result and context.tool_result.get("success"):
            effectiveness += 0.2
        
        # Check if knowledge graph was updated
        if context.metadata.get("memory_extraction_complete", {}).get("kg_updates", 0) > 0:
            effectiveness += 0.2
        
        return min(1.0, effectiveness)
    
    def _check_existing_fact(self, fact_key: str) -> dict:
        """Check if a fact already exists"""
        with self.storage.get_db() as conn:
            row = conn.execute(
                "SELECT key, value FROM semantic WHERE key = ? ORDER BY ts DESC LIMIT 1",
                (fact_key,)
            ).fetchone()
            
            if row:
                return {"key": row[0], "value": row[1]}
            return None
    
    def get_statistics(self) -> dict:
        """Get comprehensive statistics"""
        memory_summary = self.memory_enhancer.get_memory_summary()
        
        return {
            **self.stats,
            "memory_summary": memory_summary,
            "conversation_buffer_size": len(self.conversation_buffer),
            "reflection_count": self.reflection_counter
        }
    
    def reset_statistics(self):
        """Reset statistics (useful for testing)"""
        self.stats = {
            "total_facts_extracted": 0,
            "total_skills_extracted": 0,
            "total_kg_updates": 0,
            "total_tool_results_stored": 0,
            "total_reflections": 0,
            "memory_effectiveness": 0.0
        }
