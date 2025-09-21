# tool_system.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import re
import ast
import operator
import json

class Tool(ABC):
    """Base class for all tools"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description for the planner"""
        pass
    
    @abstractmethod
    def can_handle(self, user_input: str, context: Dict[str, Any]) -> bool:
        """Check if this tool should handle the input"""
        pass
    
    @abstractmethod
    def execute(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool and return results"""
        pass

class CalculatorTool(Tool):
    """Mathematical calculator tool"""
    
    def __init__(self):
        self.ops = {
            ast.Add: operator.add, ast.Sub: operator.sub,
            ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.Pow: operator.pow, ast.USub: operator.neg
        }
    
    @property
    def name(self) -> str:
        return "calculator"
    
    @property
    def description(self) -> str:
        return "Performs mathematical calculations"
    
    def can_handle(self, user_input: str, context: Dict[str, Any]) -> bool:
        """Check if input contains mathematical expressions"""
        return bool(self._extract_math_expression(user_input))
    
    def _extract_math_expression(self, text: str) -> Optional[str]:
        """Extract math expression from text"""
        patterns = [
            r'(\d+(?:\.\d+)?\s*[\+\-\*/\^%]\s*\d+(?:\.\d+)?(?:\s*[\+\-\*/\^%]\s*\d+(?:\.\d+)?)*)',
            r'(\(\s*\d+(?:\.\d+)?(?:\s*[\+\-\*/\^%]\s*\d+(?:\.\d+)?)*\s*\))',
            r'(\d+(?:\.\d+)?\s*\^\s*\d+(?:\.\d+)?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        # Fallback: clean the text and try to eval
        cleaned = re.sub(r'[^\d\+\-\*/\^%\(\)\.]', '', text)
        if cleaned and any(op in cleaned for op in '+-*/^%'):
            return cleaned
            
        return None
    
    def _safe_eval(self, expr: str):
        """Safely evaluate mathematical expressions"""
        def _eval(node):
            if isinstance(node, ast.Num): 
                return node.n
            if isinstance(node, ast.BinOp): 
                return self.ops[type(node.op)](_eval(node.left), _eval(node.right))
            if isinstance(node, ast.UnaryOp): 
                return self.ops[type(node.op)](_eval(node.operand))
            raise ValueError("Unsupported expression")
        
        tree = ast.parse(expr, mode='eval').body
        return _eval(tree)
    
    def execute(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute mathematical calculation"""
        expr = self._extract_math_expression(user_input)
        if not expr:
            return {"success": False, "error": "No mathematical expression found"}
        
        try:
            result = self._safe_eval(expr)
            return {
                "success": True,
                "result": result,
                "expression": expr,
                "formatted_result": str(result)
            }
        except Exception as e:
            return {"success": False, "error": str(e), "expression": expr}

class KnowledgeGraphTool(Tool):
    """Knowledge graph query tool"""
    
    def __init__(self, kg):
        self.kg = kg
    
    @property
    def name(self) -> str:
        return "knowledge_graph"
    
    @property
    def description(self) -> str:
        return "Queries stored knowledge about entities and relationships"
    
    def can_handle(self, user_input: str, context: Dict[str, Any]) -> bool:
        """Check if input is asking about stored knowledge"""
        query_indicators = [
            "what do you know", "tell me about", "my favorite", 
            "what is my", "who is", "where do i", "do i like"
        ]
        user_lower = user_input.lower()
        return any(indicator in user_lower for indicator in query_indicators)
    
    def execute(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Query the knowledge graph"""
        try:
            entities = self.kg.search_entities(user_input, limit=5)
            if not entities:
                return {"success": True, "entities": [], "message": "No matching entities found"}
            
            results = []
            for entity in entities:
                info = self.kg.get_entity_info(entity)
                if info:
                    entity_data = {
                        "name": entity,
                        "type": info['type'],
                        "relations": []
                    }
                    
                    # Get related concepts
                    related = self.kg.get_related_concepts(entity, max_out=3)
                    for rel_entity, relation in related:
                        entity_data["relations"].append({
                            "relation": relation,
                            "target": rel_entity
                        })
                    
                    results.append(entity_data)
            
            # Generate a more helpful response
            if results:
                response_parts = []
                for entity_data in results:
                    name = entity_data["name"]
                    entity_type = entity_data["type"]
                    relations = entity_data["relations"]
                    
                    if relations:
                        relation_text = []
                        for rel in relations:
                            relation_text.append(f"{rel['relation']} {rel['target']}")
                        response_parts.append(f"{name} ({entity_type}): {', '.join(relation_text)}")
                    else:
                        response_parts.append(f"{name} ({entity_type})")
                
                return {
                    "success": True, 
                    "entities": results,
                    "message": f"Found: {'; '.join(response_parts)}"
                }
            else:
                return {"success": True, "entities": [], "message": "No matching entities found"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

class ToolRegistry:
    """Registry for managing tools"""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.tool_order: List[str] = []  # For priority ordering
    
    def register(self, tool: Tool, priority: int = 0):
        """Register a tool with optional priority"""
        self.tools[tool.name] = tool
        
        # Insert based on priority (higher priority first)
        inserted = False
        for i, existing_name in enumerate(self.tool_order):
            if priority > getattr(self.tools[existing_name], 'priority', 0):
                self.tool_order.insert(i, tool.name)
                inserted = True
                break
        
        if not inserted:
            self.tool_order.append(tool.name)
        
        # Store priority on tool for future reference
        tool.priority = priority
    
    def unregister(self, tool_name: str):
        """Remove a tool from registry"""
        if tool_name in self.tools:
            del self.tools[tool_name]
            self.tool_order.remove(tool_name)
    
    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """Get a specific tool by name"""
        return self.tools.get(tool_name)
    
    def find_best_tool(self, user_input: str, context: Dict[str, Any]) -> Optional[Tool]:
        """Find the best tool to handle the input"""
        for tool_name in self.tool_order:
            tool = self.tools[tool_name]
            if tool.can_handle(user_input, context):
                return tool
        return None
    
    def list_tools(self) -> List[Dict[str, str]]:
        """List all registered tools"""
        return [
            {"name": tool.name, "description": tool.description}
            for tool in self.tools.values()
        ]
    
    def get_tool_descriptions(self) -> str:
        """Get formatted tool descriptions for the planner"""
        descriptions = []
        for tool_name in self.tool_order:
            tool = self.tools[tool_name]
            descriptions.append(f"- {tool.name}: {tool.description}")
        return "\n".join(descriptions)

# WebSearchTool is now imported from web_search_tool.py