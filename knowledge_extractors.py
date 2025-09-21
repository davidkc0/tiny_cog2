# knowledge_extractors.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import re
import json

class KnowledgeExtractor(ABC):
    """Base class for knowledge extraction strategies"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def extract(self, user_input: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract knowledge items from user input"""
        pass

class LLMKnowledgeExtractor(KnowledgeExtractor):
    """Uses LLM to extract structured knowledge"""
    
    def __init__(self, llm_caller):
        self.llm_caller = llm_caller
    
    @property
    def name(self) -> str:
        return "llm_extractor"
    
    def extract(self, user_input: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract knowledge using LLM"""
        if not user_input.strip():
            return []
        
        prompt = f"""Extract structured knowledge from this user message. Return ONLY a JSON array.
Each item should have: entity, type, relation, target (defaults to "user"), and optionally "replaces" if this updates previous knowledge.
Types: location, color, profession, person, hobby, food, etc.
Relations: lives_in, likes, works_as, owns, friend_of, etc.

For knowledge updates/changes (like "my favorite color is now X" or "I moved to Y"), include "replaces": true.

User message: "{user_input}"

JSON array:"""
        
        try:
            response = self.llm_caller(prompt, mode="answer")
            return self._parse_json_response(response, user_input)
        except Exception as e:
            print(f"LLM knowledge extraction error: {e}")
            return []
    
    def _parse_json_response(self, response: str, fallback_input: str) -> List[Dict[str, Any]]:
        """Parse JSON response with fallback"""
        try:
            # Strategy 1: Look for complete JSON array
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                
                try:
                    knowledge_items = json.loads(json_str)
                    return knowledge_items if isinstance(knowledge_items, list) else []
                except json.JSONDecodeError:
                    # Try to fix common JSON issues
                    fixed_json = re.sub(r',\s*]', ']', json_str)
                    fixed_json = re.sub(r',\s*}', '}', fixed_json)
                    knowledge_items = json.loads(fixed_json)
                    return knowledge_items if isinstance(knowledge_items, list) else []
        except Exception:
            pass
        
        return []

class PatternKnowledgeExtractor(KnowledgeExtractor):
    """Uses regex patterns to extract knowledge"""
    
    def __init__(self):
        self.patterns = [
            # Specific patterns first (more specific than generic)
            {
                "name": "favorite_color",
                "pattern": r'favorite color is (?:now )?(\w+)',
                "entity_group": 1,
                "type": "color",
                "relation": "likes",
                "target": "user",
                "replaces_indicator": "now"
            },
            {
                "name": "favorite_food",
                "pattern": r'favorite food is (?:now )?(\w+(?:\s+\w+)*)',
                "entity_group": 1,
                "type": "food",
                "relation": "likes",
                "target": "user",
                "replaces_indicator": "now"
            },
            {
                "name": "favorite_hobby",
                "pattern": r'favorite hobby is (?:now )?(\w+(?:\s+\w+)*)',
                "entity_group": 1,
                "type": "hobby",
                "relation": "likes",
                "target": "user",
                "replaces_indicator": "now"
            },
            {
                "name": "favorite_movie",
                "pattern": r'favorite movie is (?:now )?(\w+(?:\s+\w+)*)',
                "entity_group": 1,
                "type": "movie",
                "relation": "likes",
                "target": "user",
                "replaces_indicator": "now"
            },
            # Location patterns
            {
                "name": "location",
                "pattern": r'(?:live|moved) (?:in|to) (\w+(?:\s+\w+)*)',
                "entity_group": 1,
                "type": "location",
                "relation": "lives_in",
                "target": "user",
                "replaces_indicator": "moved"
            },
            # Profession patterns
            {
                "name": "profession",
                "pattern": r'(?:work as|job is|am a) (\w+(?:\s+\w+)*)',
                "entity_group": 1,
                "type": "profession",
                "relation": "works_as",
                "target": "user"
            },
            # Hobby patterns
            {
                "name": "hobby",
                "pattern": r'(?:hobby is|hobbies include|enjoy) (\w+(?:\s+\w+)*)',
                "entity_group": 1,
                "type": "hobby",
                "relation": "likes",
                "target": "user"
            },
            # Generic favorite patterns (catch-all)
            {
                "name": "favorite_generic",
                "pattern": r'favorite (.+?) is (?:now )?(\w+(?:\s+\w+)*)',
                "entity_group": 2,
                "type": "preference",
                "relation": "likes",
                "target": "user",
                "replaces_indicator": "now"
            },
            # Generic likes patterns (catch-all)
            {
                "name": "likes_generic",
                "pattern": r'(?:like|love|enjoy) (\w+(?:\s+\w+)*)',
                "entity_group": 1,
                "type": "preference",
                "relation": "likes",
                "target": "user"
            },
            # Food patterns (more specific than generic likes)
            {
                "name": "likes_food",
                "pattern": r'(?:like|love) (?:eating )?(\w+(?:\s+\w+)*)',
                "entity_group": 1,
                "type": "food",
                "relation": "likes",
                "target": "user"
            }
        ]
    
    @property
    def name(self) -> str:
        return "pattern_extractor"
    
    def extract(self, user_input: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract knowledge using regex patterns"""
        user_lower = user_input.lower()
        knowledge_items = []
        seen_entities = set()  # Track seen entity+type combinations to avoid duplicates
        
        for pattern_config in self.patterns:
            match = re.search(pattern_config["pattern"], user_lower)
            if match:
                entity = match.group(pattern_config["entity_group"]).strip()
                entity_type = pattern_config["type"]
                
                # Create a unique key to avoid duplicates
                entity_key = (entity.lower(), entity_type)
                if entity_key in seen_entities:
                    continue
                
                item = {
                    "entity": entity,
                    "type": entity_type,
                    "relation": pattern_config["relation"],
                    "target": pattern_config["target"]
                }
                
                # Check if this replaces existing knowledge
                if "replaces_indicator" in pattern_config:
                    if pattern_config["replaces_indicator"] in user_lower:
                        item["replaces"] = True
                
                knowledge_items.append(item)
                seen_entities.add(entity_key)
                
                # For specific patterns, don't continue to generic ones
                if pattern_config["name"] in ["favorite_color", "favorite_food", "favorite_hobby", "favorite_movie", "location", "profession", "hobby"]:
                    break
                
                # For generic patterns, also break to avoid duplicates
                if pattern_config["name"] in ["likes_generic", "favorite_generic"]:
                    break
        
        return knowledge_items
    
    def add_pattern(self, name: str, pattern: str, entity_group: int, 
                   type_: str, relation: str, target: str = "user", 
                   replaces_indicator: Optional[str] = None):
        """Add a new extraction pattern"""
        pattern_config = {
            "name": name,
            "pattern": pattern,
            "entity_group": entity_group,
            "type": type_,
            "relation": relation,
            "target": target
        }
        
        if replaces_indicator:
            pattern_config["replaces_indicator"] = replaces_indicator
        
        self.patterns.append(pattern_config)

class CompositeKnowledgeExtractor(KnowledgeExtractor):
    """Combines multiple extraction strategies"""
    
    def __init__(self):
        self.extractors: List[KnowledgeExtractor] = []
    
    @property
    def name(self) -> str:
        return "composite_extractor"
    
    def add_extractor(self, extractor: KnowledgeExtractor):
        """Add an extraction strategy"""
        self.extractors.append(extractor)
    
    def remove_extractor(self, extractor_name: str):
        """Remove an extraction strategy"""
        self.extractors = [e for e in self.extractors if e.name != extractor_name]
    
    def extract(self, user_input: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run all extractors and combine results"""
        all_items = []
        
        for extractor in self.extractors:
            try:
                items = extractor.extract(user_input, context)
                if items:
                    all_items.extend(items)
            except Exception as e:
                print(f"Error in {extractor.name}: {e}")
        
        # Remove duplicates based on entity + relation + target
        seen = set()
        unique_items = []
        
        for item in all_items:
            key = (item.get("entity", ""), item.get("relation", ""), item.get("target", ""))
            if key not in seen:
                seen.add(key)
                unique_items.append(item)
        
        return unique_items

# Example custom extractor
class PersonExtractor(KnowledgeExtractor):
    """Extracts information about people/relationships"""
    
    @property
    def name(self) -> str:
        return "person_extractor"
    
    def extract(self, user_input: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        user_lower = user_input.lower()
        items = []
        
        # Friend patterns
        friend_match = re.search(r'my friend (\w+)', user_lower)
        if friend_match:
            friend_name = friend_match.group(1).title()
            items.append({
                "entity": friend_name,
                "type": "person",
                "relation": "friend_of",
                "target": "user"
            })
        
        # Family patterns
        family_patterns = [
            (r'my (?:mom|mother) is (\w+)', "mother_of"),
            (r'my (?:dad|father) is (\w+)', "father_of"),
            (r'my (?:brother) is (\w+)', "brother_of"),
            (r'my (?:sister) is (\w+)', "sister_of")
        ]
        
        for pattern, relation in family_patterns:
            match = re.search(pattern, user_lower)
            if match:
                name = match.group(1).title()
                items.append({
                    "entity": name,
                    "type": "person",
                    "relation": relation,
                    "target": "user"
                })
        
        return items
