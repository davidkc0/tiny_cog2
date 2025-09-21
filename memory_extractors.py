#!/usr/bin/env python3
"""
Enhanced Memory Extractors for Semantic and Skills Memory
Extracts structured facts and learning patterns from conversations
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

class SemanticFactExtractor:
    """Extracts semantic facts from conversations"""
    
    def __init__(self):
        # Patterns for different types of facts
        self.fact_patterns = {
            # Personal information
            "personal_info": [
                r"i (?:am|live in|work at|study at|have|own|drive|use) (.+)",
                r"my (?:name is|age is|job is|hobby is|favorite|preference|location|address) (.+)",
                r"i (?:like|love|enjoy|prefer|hate|dislike) (.+)",
                r"i (?:can|know how to|am good at|am bad at) (.+)",
            ],
            # Facts about the world
            "world_facts": [
                r"(?:the|a|an) (.+) (?:is|are|was|were) (.+)",
                r"(.+) (?:means|refers to|is defined as) (.+)",
                r"in (.+), (.+)",
                r"(.+) (?:happened|occurred|took place) (.+)",
            ],
            # Preferences and opinions
            "preferences": [
                r"i (?:prefer|like|love|enjoy) (.+) (?:over|to|rather than) (.+)",
                r"my (?:favorite|least favorite) (.+) (?:is|are) (.+)",
                r"i (?:think|believe|feel) (.+) (?:is|are) (.+)",
            ],
            # Skills and abilities
            "capabilities": [
                r"i (?:can|know how to|am able to|am skilled at) (.+)",
                r"i (?:have|possess) (?:the ability|skills) (?:to|in) (.+)",
                r"i (?:am|am not) (?:good|bad|skilled|experienced) (?:at|with) (.+)",
            ],
            # Relationships
            "relationships": [
                r"my (?:friend|colleague|boss|teacher|family|partner) (.+)",
                r"i (?:know|work with|live with|study with) (.+)",
                r"(.+) (?:is|are) my (.+)",
            ]
        }
    
    def extract_facts(self, text: str, speaker: str = "user") -> List[Dict[str, Any]]:
        """Extract semantic facts from text"""
        facts = []
        text_lower = text.lower()
        
        for fact_type, patterns in self.fact_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    fact = self._create_fact(match, fact_type, speaker, text)
                    if fact:
                        facts.append(fact)
        
        return facts
    
    def _create_fact(self, match, fact_type: str, speaker: str, original_text: str) -> Optional[Dict[str, Any]]:
        """Create a structured fact from a regex match"""
        groups = match.groups()
        if len(groups) < 2:
            return None
        
        # Extract key-value pairs
        key = groups[0].strip()
        value = groups[1].strip() if len(groups) > 1 else ""
        
        # Clean up the fact
        key = self._clean_fact_key(key)
        value = self._clean_fact_value(value)
        
        if not key or not value:
            return None
        
        return {
            "key": f"{speaker}_{fact_type}_{key}",
            "value": value,
            "fact_type": fact_type,
            "speaker": speaker,
            "confidence": self._calculate_confidence(match, fact_type),
            "source_text": original_text[:100] + "..." if len(original_text) > 100 else original_text
        }
    
    def _clean_fact_key(self, key: str) -> str:
        """Clean and normalize fact keys"""
        # Remove common prefixes
        key = re.sub(r'^(i|my|the|a|an)\s+', '', key)
        # Normalize spaces and special chars
        key = re.sub(r'\s+', '_', key)
        key = re.sub(r'[^\w_]', '', key)
        return key.lower()
    
    def _clean_fact_value(self, value: str) -> str:
        """Clean and normalize fact values"""
        # Remove trailing punctuation
        value = re.sub(r'[.,!?;]+$', '', value)
        # Normalize spaces
        value = re.sub(r'\s+', ' ', value)
        return value.strip()
    
    def _calculate_confidence(self, match, fact_type: str) -> float:
        """Calculate confidence score for extracted fact"""
        base_confidence = 0.7
        
        # Higher confidence for more specific patterns
        if fact_type in ["personal_info", "capabilities"]:
            base_confidence = 0.9
        elif fact_type in ["preferences", "relationships"]:
            base_confidence = 0.8
        elif fact_type == "world_facts":
            base_confidence = 0.6
        
        # Adjust based on match quality
        match_length = len(match.group())
        if match_length > 20:
            base_confidence += 0.1
        elif match_length < 10:
            base_confidence -= 0.1
        
        return min(1.0, max(0.1, base_confidence))

class SkillsExtractor:
    """Extracts learning patterns and skills from conversations"""
    
    def __init__(self):
        self.skill_patterns = {
            # Learning indicators
            "learning": [
                r"i (?:learned|discovered|found out|realized) (.+)",
                r"i (?:now|now) (?:understand|know|get) (.+)",
                r"that (?:makes sense|is helpful|is useful) (.+)",
                r"i (?:will|should|need to) (?:remember|keep in mind|note) (.+)",
            ],
            # Problem-solving patterns
            "problem_solving": [
                r"i (?:solved|fixed|resolved|figured out) (.+)",
                r"the (?:solution|answer|way) (?:is|was) (.+)",
                r"i (?:tried|attempted|used) (.+) (?:and|to) (.+)",
                r"when (?:i|you) (.+), (?:i|you) (.+)",
            ],
            # Teaching/helping patterns
            "teaching": [
                r"i (?:can|will|should) (?:teach|show|explain|help) (.+)",
                r"let me (?:show|explain|demonstrate) (.+)",
                r"the (?:way|method|approach) (?:to|for) (.+) (?:is|involves) (.+)",
            ],
            # Interest and engagement
            "engagement": [
                r"i (?:am|am really) (?:interested in|curious about|fascinated by) (.+)",
                r"i (?:want|would like) (?:to learn|to know|to understand) (.+)",
                r"that (?:sounds|seems) (?:interesting|fascinating|cool|amazing) (.+)",
            ],
            # Challenges and difficulties
            "challenges": [
                r"i (?:struggle|have trouble|find it difficult) (?:with|to) (.+)",
                r"i (?:don't|can't) (?:understand|get|know) (.+)",
                r"(.+) (?:is|are) (?:confusing|difficult|hard|challenging) (.+)",
            ]
        }
    
    def extract_skills(self, text: str, speaker: str = "user") -> List[Dict[str, Any]]:
        """Extract learning patterns and skills from text"""
        skills = []
        text_lower = text.lower()
        
        for skill_type, patterns in self.skill_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    skill = self._create_skill(match, skill_type, speaker, text)
                    if skill:
                        skills.append(skill)
        
        return skills
    
    def _create_skill(self, match, skill_type: str, speaker: str, original_text: str) -> Optional[Dict[str, Any]]:
        """Create a structured skill from a regex match"""
        groups = match.groups()
        if not groups:
            return None
        
        # Extract the main content
        content = groups[0].strip()
        if len(groups) > 1:
            content += f" - {groups[1].strip()}"
        
        # Clean up the skill
        content = self._clean_skill_content(content)
        
        if not content:
            return None
        
        return {
            "note": f"{skill_type}: {content}",
            "skill_type": skill_type,
            "speaker": speaker,
            "confidence": self._calculate_skill_confidence(match, skill_type),
            "source_text": original_text[:100] + "..." if len(original_text) > 100 else original_text,
            "meta": {
                "type": skill_type,
                "speaker": speaker,
                "timestamp": datetime.now().isoformat(),
                "content_length": len(content)
            }
        }
    
    def _clean_skill_content(self, content: str) -> str:
        """Clean and normalize skill content"""
        # Remove common prefixes
        content = re.sub(r'^(i|that|the|when|if)\s+', '', content)
        # Normalize spaces
        content = re.sub(r'\s+', ' ', content)
        # Remove trailing punctuation
        content = re.sub(r'[.,!?;]+$', '', content)
        return content.strip()
    
    def _calculate_skill_confidence(self, match, skill_type: str) -> float:
        """Calculate confidence score for extracted skill"""
        base_confidence = 0.7
        
        # Higher confidence for more specific patterns
        if skill_type in ["learning", "problem_solving"]:
            base_confidence = 0.9
        elif skill_type in ["teaching", "engagement"]:
            base_confidence = 0.8
        elif skill_type == "challenges":
            base_confidence = 0.6
        
        # Adjust based on match quality
        match_length = len(match.group())
        if match_length > 15:
            base_confidence += 0.1
        elif match_length < 8:
            base_confidence -= 0.1
        
        return min(1.0, max(0.1, base_confidence))

class MemoryEnhancer:
    """Main class that coordinates memory extraction and storage"""
    
    def __init__(self, storage_module, embeddings_module):
        self.storage = storage_module
        self.embeddings = embeddings_module
        self.semantic_extractor = SemanticFactExtractor()
        self.skills_extractor = SkillsExtractor()
    
    def process_conversation(self, user_input: str, agent_response: str) -> Dict[str, Any]:
        """Process a conversation turn and extract memories"""
        results = {
            "semantic_facts": [],
            "skills": [],
            "stored_facts": 0,
            "stored_skills": 0
        }
        
        # Extract from user input
        user_facts = self.semantic_extractor.extract_facts(user_input, "user")
        user_skills = self.skills_extractor.extract_skills(user_input, "user")
        
        # Extract from agent response
        agent_facts = self.semantic_extractor.extract_facts(agent_response, "assistant")
        agent_skills = self.skills_extractor.extract_skills(agent_response, "assistant")
        
        # Store semantic facts
        for fact in user_facts + agent_facts:
            if fact["confidence"] > 0.6:  # Only store high-confidence facts
                fact_id = self.storage.insert_semantic(
                    fact["key"], 
                    fact["value"], 
                    f"extracted_{fact['speaker']}"
                )
                fact_emb = self.embeddings.embed_text(f"{fact['key']} = {fact['value']}")
                self.storage.upsert_vector("semantic", fact_id, fact_emb)
                results["stored_facts"] += 1
                results["semantic_facts"].append(fact)
        
        # Store skills
        for skill in user_skills + agent_skills:
            if skill["confidence"] > 0.6:  # Only store high-confidence skills
                skill_id = self.storage.insert_skill(skill["note"], skill["meta"])
                skill_emb = self.embeddings.embed_text(skill["note"])
                self.storage.upsert_vector("skills", skill_id, skill_emb)
                results["stored_skills"] += 1
                results["skills"].append(skill)
        
        return results
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get summary of stored memories"""
        with self.storage.get_db() as conn:
            # Count semantic facts
            semantic_count = conn.execute("SELECT COUNT(*) FROM semantic").fetchone()[0]
            
            # Count skills
            skills_count = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
            
            # Get recent facts
            recent_facts = conn.execute("""
                SELECT key, value, source, ts FROM semantic 
                ORDER BY ts DESC LIMIT 5
            """).fetchall()
            
            # Get recent skills
            recent_skills = conn.execute("""
                SELECT note, meta, ts FROM skills 
                ORDER BY ts DESC LIMIT 5
            """).fetchall()
            
            return {
                "semantic_facts_count": semantic_count,
                "skills_count": skills_count,
                "recent_facts": recent_facts,
                "recent_skills": recent_skills
            }
