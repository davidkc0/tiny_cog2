# llm_driven_personality.py
import json
import time
import random
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import storage
from personality_system import PersonalityTrait, PersonalityState

class LLMPersonalityEvolution:
    """LLM-driven personality evolution system"""
    
    def __init__(self, llm_caller):
        self.llm_caller = llm_caller
        self.adaptation_rate = 0.05  # How strongly to apply LLM suggestions
        self.evolution_thresholds = {
            1: 10,   # interactions needed for level 2
            2: 25,   # interactions needed for level 3
            3: 50,   # interactions needed for level 4
            4: 100,  # interactions needed for level 5
            5: 200   # max level
        }
    
    def analyze_interaction(self, user_input: str, agent_response: str, 
                          current_personality: PersonalityState,
                          user_feedback: Optional[str] = None) -> Dict[str, float]:
        """Use LLM to analyze interaction and suggest personality adjustments"""
        
        # Get current trait values for context
        trait_summary = {
            "enthusiasm": current_personality.enthusiasm,
            "formality": current_personality.formality,
            "curiosity": current_personality.curiosity,
            "supportiveness": current_personality.supportiveness,
            "playfulness": current_personality.playfulness,
            "directness": current_personality.directness,
            "protectiveness": current_personality.protectiveness,
            "independence": current_personality.independence
        }
        
        prompt = f"""You are analyzing an AI personality's interaction with a user to determine how the AI should evolve.

Current AI Personality Traits (0.0 = low, 1.0 = high):
{json.dumps(trait_summary, indent=2)}

Recent Interaction:
User: "{user_input}"
AI Response: "{agent_response}"
{f'User Feedback: "{user_feedback}"' if user_feedback else ''}

Evolution Level: {current_personality.evolution_level}/5
Trust Level: {current_personality.trust_level}
Total Interactions: {current_personality.interaction_count}

Analyze this interaction and determine how the AI's personality should adapt. Consider:
1. User's communication style (formal/casual, enthusiastic/calm, etc.)
2. Whether the user seemed satisfied with the response
3. If the user wants more/less detail, formality, enthusiasm, etc.
4. How the AI can better serve this specific user
5. Building appropriate trust and rapport

Return ONLY a JSON object with:
- trait adjustments (-0.1 to +0.1 for each trait that should change)
- trust_adjustment (-0.05 to +0.05)
- reasoning (brief explanation)

Example format:
{{
    "enthusiasm": 0.02,
    "formality": -0.03,
    "trust_adjustment": 0.01,
    "reasoning": "User used casual language and positive feedback, suggesting they prefer a more casual, enthusiastic approach"
}}

JSON:"""

        try:
            response = self.llm_caller(prompt, mode="answer")
            return self._parse_llm_adjustments(response)
        except Exception as e:
            print(f"LLM personality analysis error: {e}")
            # Fallback to basic hardcoded rules
            return self._fallback_analysis(user_input, agent_response)
    
    def _parse_llm_adjustments(self, response: str) -> Dict[str, Any]:
        """Parse LLM response for personality adjustments"""
        try:
            # Find JSON in response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                
                # Clean up common JSON issues
                json_str = json_str.replace('\n', ' ').replace('\r', ' ')
                json_str = json_str.replace('"', '"').replace('"', '"')  # Fix smart quotes
                # Fix + signs in numbers (e.g., +0.1 -> 0.1)
                import re
                json_str = re.sub(r'\+(\d+\.?\d*)', r'\1', json_str)
                
                adjustments = json.loads(json_str)
                
                # Validate and clamp adjustments
                valid_traits = [
                    'enthusiasm', 'formality', 'curiosity', 'supportiveness',
                    'playfulness', 'directness', 'protectiveness', 'independence'
                ]
                
                cleaned_adjustments = {}
                for trait in valid_traits:
                    if trait in adjustments:
                        # Clamp to reasonable range
                        value = max(-0.1, min(0.1, float(adjustments[trait])))
                        if abs(value) > 0.001:  # Only include meaningful adjustments
                            cleaned_adjustments[trait] = value
                
                # Handle trust adjustment
                if 'trust_adjustment' in adjustments:
                    trust_adj = max(-0.05, min(0.05, float(adjustments['trust_adjustment'])))
                    if abs(trust_adj) > 0.001:
                        cleaned_adjustments['trust_level'] = trust_adj
                
                # Store reasoning for debugging
                if 'reasoning' in adjustments:
                    cleaned_adjustments['_reasoning'] = adjustments['reasoning']
                
                return cleaned_adjustments
                
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            print(f"Failed to parse LLM adjustments: {e}")
            print(f"Raw response: {response[:200]}...")
            print(f"JSON string: {json_str if 'json_str' in locals() else 'Not found'}")
        
        return {}
    
    def _fallback_analysis(self, user_input: str, agent_response: str) -> Dict[str, float]:
        """Fallback analysis when LLM fails"""
        adjustments = {}
        user_lower = user_input.lower()
        
        # Basic hardcoded rules as fallback
        if any(word in user_lower for word in ['thanks', 'thank you', 'helpful', 'great']):
            adjustments['supportiveness'] = 0.01
            adjustments['trust_level'] = 0.01
        
        if any(word in user_lower for word in ['hey', 'yo', 'sup']):
            adjustments['formality'] = -0.02
            adjustments['playfulness'] = 0.01
        
        return adjustments
    
    def apply_adjustments(self, personality: PersonalityState, 
                         adjustments: Dict[str, float]) -> PersonalityState:
        """Apply LLM-suggested adjustments with adaptation rate"""
        reasoning = adjustments.pop('_reasoning', None)
        
        for trait, adjustment in adjustments.items():
            if hasattr(personality, trait):
                current_value = getattr(personality, trait)
                # Apply adjustment with adaptation rate
                adjusted_change = adjustment * self.adaptation_rate
                new_value = max(0.0, min(1.0, current_value + adjusted_change))
                setattr(personality, trait, new_value)
        
        # Update metadata
        personality.interaction_count += 1
        personality.last_updated = time.time()
        
        # Check for evolution level increase
        old_level = personality.evolution_level
        for level, threshold in self.evolution_thresholds.items():
            if (personality.interaction_count >= threshold and 
                personality.evolution_level < level):
                personality.evolution_level = level
                break
        
        # Log personality changes for debugging
        if reasoning and (len(adjustments) > 0):
            print(f"🧠 Personality evolved: {reasoning}")
            changes = [f"{k}:{v:+.3f}" for k, v in adjustments.items() if k != '_reasoning']
            if changes:
                print(f"   Changes: {', '.join(changes)}")
        
        return personality

class LLMPersonalityManager:
    """Enhanced personality manager with LLM-driven evolution"""
    
    def __init__(self, storage_module, llm_caller):
        self.storage = storage_module
        self.llm_caller = llm_caller
        self.evolution = LLMPersonalityEvolution(llm_caller)
        self.personality = self._load_personality()
        
        # Configuration options
        self.use_llm_evolution = True  # Can be toggled
        self.evolution_verbosity = 1   # 0=silent, 1=minimal, 2=verbose
        
        # Response templates (still used for quick modifications)
        self.response_modifiers = {
            'enthusiasm': {
                'high': ['!', ' That\'s exciting!', ' I love that!'],
                'low': ['.', '', ' I see.']
            },
            'formality': {
                'high': ['Please', 'Thank you', 'I would suggest', 'May I'],
                'low': ['Hey', 'Cool', 'Sure thing', 'Got it']
            },
            'playfulness': {
                'high': [' 😊', ' Haha', ' Fun!', ' Nice!'],
                'low': ['', '', '', '']
            }
        }
    
    def _load_personality(self) -> PersonalityState:
        """Load personality from storage or create default"""
        personality_data = storage.get_meta("personality_state")
        if personality_data:
            try:
                data = json.loads(personality_data)
                return PersonalityState(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        
        return PersonalityState()
    
    def _save_personality(self):
        """Save personality to storage"""
        personality_dict = asdict(self.personality)
        storage.set_meta("personality_state", json.dumps(personality_dict))
    
    def process_interaction(self, user_input: str, agent_response: str, 
                          user_feedback: Optional[str] = None):
        """Process interaction with LLM-driven or manual evolution"""
        if self.use_llm_evolution:
            # Use LLM to analyze and evolve personality
            adjustments = self.evolution.analyze_interaction(
                user_input, agent_response, self.personality, user_feedback
            )
        else:
            # Fall back to basic hardcoded rules
            adjustments = self.evolution._fallback_analysis(user_input, agent_response)
        
        # Apply adjustments
        old_level = self.personality.evolution_level
        self.personality = self.evolution.apply_adjustments(self.personality, adjustments)
        
        # Save updated personality
        self._save_personality()
        
        # Check if personality evolved
        evolution_result = {"evolved": False}
        if self.personality.evolution_level > old_level:
            evolution_result = {
                "evolved": True,
                "new_level": self.personality.evolution_level,
                "message": self._get_evolution_message()
            }
        
        return evolution_result
    
    def _get_evolution_message(self) -> str:
        """Generate evolution message using LLM"""
        if not self.use_llm_evolution:
            # Fallback to hardcoded messages
            level = self.personality.evolution_level
            messages = {
                2: "I feel like I'm getting to know you better!",
                3: "Our conversations are helping me understand your preferences.",
                4: "I've learned a lot about your communication style.",
                5: "I feel like we've developed a great working relationship!"
            }
            return messages.get(level, "I continue to learn and adapt!")
        
        try:
            prompt = f"""The AI assistant has just evolved to level {self.personality.evolution_level}/5.

Current personality traits:
- Enthusiasm: {self.personality.enthusiasm:.2f}
- Formality: {self.personality.formality:.2f}
- Curiosity: {self.personality.curiosity:.2f}
- Supportiveness: {self.personality.supportiveness:.2f}
- Playfulness: {self.personality.playfulness:.2f}
- Directness: {self.personality.directness:.2f}
- Protectiveness: {self.personality.protectiveness:.2f}
- Independence: {self.personality.independence:.2f}

Total interactions: {self.personality.interaction_count}
Trust level: {self.personality.trust_level:.2f}

Generate a brief, natural message (1-2 sentences) that the AI would say to acknowledge this evolution. The message should:
- Reflect the AI's current personality traits
- Sound genuine and not overly dramatic
- Acknowledge the growing relationship with the user
- Be appropriate for evolution level {self.personality.evolution_level}

Message:"""
            
            return self.llm_caller(prompt, mode="answer").strip()
        except Exception as e:
            print(f"Error generating evolution message: {e}")
            return f"I've evolved to level {self.personality.evolution_level}! I'm learning more about how to help you."
    
    def modify_response(self, base_response: str, context: Dict[str, Any] = None) -> str:
        """Modify response based on personality with LLM assistance"""
        if not self.use_llm_evolution:
            # Use original hardcoded modifications
            return self._apply_hardcoded_modifications(base_response, context)
        
        try:
            # Use LLM to apply personality-appropriate modifications
            prompt = f"""Modify this response to match the AI's personality traits:

Original Response: "{base_response}"

AI Personality (0.0 = low, 1.0 = high):
- Enthusiasm: {self.personality.enthusiasm:.2f}
- Formality: {self.personality.formality:.2f}  
- Playfulness: {self.personality.playfulness:.2f}
- Supportiveness: {self.personality.supportiveness:.2f}
- Directness: {self.personality.directness:.2f}
- Curiosity: {self.personality.curiosity:.2f}

Instructions:
- Adjust tone, word choice, and style to match personality
- Keep the core meaning and information intact
- Make subtle changes that reflect the personality traits
- Don't add excessive exclamation points or emojis
- If directness is high, be more concise; if low, be more elaborate
- If formality is high, use more formal language; if low, be more casual

Modified Response:"""
            
            modified = self.llm_caller(prompt, mode="answer").strip()
            
            # Fallback to original if modification failed
            if len(modified) < len(base_response) * 0.5 or len(modified) > len(base_response) * 2:
                return self._apply_hardcoded_modifications(base_response, context)
            
            return modified
            
        except Exception as e:
            print(f"Error in LLM response modification: {e}")
            return self._apply_hardcoded_modifications(base_response, context)
    
    def _apply_hardcoded_modifications(self, base_response: str, context: Dict[str, Any] = None) -> str:
        """Apply hardcoded personality modifications as fallback"""
        response = base_response
        
        # Basic enthusiasm adjustment
        if self.personality.enthusiasm > 0.7:
            if not response.endswith('!') and random.random() < 0.3:
                response = response.rstrip('.') + '!'
        elif self.personality.enthusiasm < 0.3:
            response = response.replace('!', '.')
        
        # Basic formality adjustment
        if self.personality.formality > 0.7:
            response = response.replace(' gonna ', ' going to ')
            response = response.replace(' can\'t ', ' cannot ')
        elif self.personality.formality < 0.3:
            response = response.replace(' cannot ', ' can\'t ')
            response = response.replace(' going to ', ' gonna ')
        
        return response
    
    # Configuration methods
    def set_llm_evolution(self, enabled: bool):
        """Enable or disable LLM-driven evolution"""
        self.use_llm_evolution = enabled
        if enabled:
            print("🧠 LLM-driven personality evolution enabled")
        else:
            print("🔧 Switched to manual personality mode")
    
    def set_evolution_verbosity(self, level: int):
        """Set how much personality evolution info to show (0-2)"""
        self.evolution_verbosity = max(0, min(2, level))
    
    def force_personality_analysis(self, user_input: str, agent_response: str) -> Dict[str, Any]:
        """Manually trigger personality analysis and return details"""
        adjustments = self.evolution.analyze_interaction(
            user_input, agent_response, self.personality
        )
        
        return {
            "suggested_adjustments": adjustments,
            "current_traits": {
                "enthusiasm": self.personality.enthusiasm,
                "formality": self.personality.formality,
                "curiosity": self.personality.curiosity,
                "supportiveness": self.personality.supportiveness,
                "playfulness": self.personality.playfulness,
                "directness": self.personality.directness,
                "protectiveness": self.personality.protectiveness,
                "independence": self.personality.independence
            },
            "reasoning": adjustments.get('_reasoning', 'No reasoning provided')
        }
    
    # Delegate other methods to maintain compatibility
    def get_personality_summary(self):
        """Get personality summary (same as original)"""
        return {
            "name": self.personality.name,
            "evolution_level": self.personality.evolution_level,
            "trust_level": round(self.personality.trust_level, 2),
            "interaction_count": self.personality.interaction_count,
            "dominant_traits": self._get_dominant_traits(),
            "communication_style": self._get_communication_style(),
            "next_evolution": self._get_next_evolution_info(),
            "llm_evolution": self.use_llm_evolution
        }
    
    def _get_dominant_traits(self) -> List[str]:
        """Get the most prominent personality traits"""
        traits = []
        if self.personality.enthusiasm > 0.6:
            traits.append("enthusiastic")
        if self.personality.supportiveness > 0.6:
            traits.append("supportive")
        if self.personality.curiosity > 0.6:
            traits.append("curious")
        if self.personality.playfulness > 0.6:
            traits.append("playful")
        if self.personality.protectiveness > 0.6:
            traits.append("protective")
        if self.personality.directness > 0.6:
            traits.append("direct")
        elif self.personality.directness < 0.4:
            traits.append("detailed")
        if self.personality.formality > 0.6:
            traits.append("formal")
        elif self.personality.formality < 0.4:
            traits.append("casual")
        
        return traits[:3]
    
    def _get_communication_style(self) -> str:
        """Determine overall communication style"""
        if self.personality.formality > 0.6:
            return "professional"
        elif self.personality.playfulness > 0.6 and self.personality.formality < 0.4:
            return "casual and fun"
        elif self.personality.supportiveness > 0.7:
            return "warm and encouraging"
        elif self.personality.directness > 0.7:
            return "direct and efficient"
        else:
            return "balanced"
    
    def _get_next_evolution_info(self) -> Dict[str, Any]:
        """Get information about next evolution level"""
        current_level = self.personality.evolution_level
        if current_level >= 5:
            return {"at_max_level": True}
        
        next_threshold = self.evolution.evolution_thresholds.get(current_level + 1, 0)
        interactions_needed = next_threshold - self.personality.interaction_count
        
        return {
            "next_level": current_level + 1,
            "interactions_needed": max(0, interactions_needed),
            "progress": min(1.0, self.personality.interaction_count / next_threshold)
        }
    
    # Manual override methods (same as original)
    def set_personality_trait(self, trait: str, value: float):
        """Manually adjust a personality trait"""
        if hasattr(self.personality, trait):
            setattr(self.personality, trait, max(0.0, min(1.0, value)))
            self._save_personality()
            print(f"🔧 Manually set {trait} to {value}")
    
    def reset_personality(self):
        """Reset personality to default state"""
        self.personality = PersonalityState()
        self._save_personality()
        print("🔄 Personality reset to default")
    
    def export_personality(self) -> Dict[str, Any]:
        """Export personality for backup/sharing"""
        return asdict(self.personality)
    
    def import_personality(self, personality_data: Dict[str, Any]):
        """Import personality from backup/sharing"""
        try:
            self.personality = PersonalityState(**personality_data)
            self._save_personality()
            print("📥 Personality imported successfully")
            return True
        except (TypeError, ValueError):
            print("❌ Failed to import personality data")
            return False