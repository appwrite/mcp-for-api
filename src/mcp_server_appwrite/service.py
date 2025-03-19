from typing import Any, get_type_hints, Dict
import inspect
from mcp.types import Tool
from docstring_parser import parse

class Service():
    """Base class for all Appwrite services"""
    
    def __init__(self, service_instance, service_name: str):
        self.service = service_instance
        self.service_name = service_name
        self._method_name_overrides = self.get_method_name_overrides()
    
    def get_method_name_overrides(self) -> Dict[str, str]:
        """
        Override this method to provide method name mappings.
        Returns a dictionary where:
        - key: original method name
        - value: new method name to be used
        """
        return {}
    
    def python_type_to_json_schema(self, py_type: Any) -> dict:
        """Converts Python type hints to JSON Schema types."""
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object"
        }

        if hasattr(py_type, "__origin__") and py_type.__origin__ is list:
            item_type = py_type.__args__[0]
            return {
                "type": "array",
                "items": self.python_type_to_json_schema(item_type)
            }

        return {"type": type_mapping.get(py_type, "string")}

    def list_tools(self) -> Dict[str, Dict]:
        """Lists all available tools for this service"""
        tools = {}

        for name, func in inspect.getmembers(self.service, predicate=inspect.ismethod):
            if name.startswith('_'): # Skip private methods
                continue

            original_func = func.__func__
            
            # Skip if not from the service's module
            if original_func.__module__ != self.service.__class__.__module__:
                continue

            # Get the overridden name if it exists
            tool_name = self._method_name_overrides.get(name, f"{self.service_name}_{name}")

            docstring = parse(original_func.__doc__)
            signature = inspect.signature(original_func)
            type_hints = get_type_hints(original_func)

            properties = {}
            required = []

            for param_name, param in signature.parameters.items():
                if param_name == 'self':
                    continue

                param_type = type_hints.get(param_name, str)
                properties[param_name] = self.python_type_to_json_schema(param_type)
                properties[param_name]["description"] = f"Parameter '{param_name}'"
                
                for doc_param in docstring.params:
                    if doc_param.arg_name == param_name:
                        properties[param_name]["description"] = doc_param.description

                if param.default is param.empty:
                    required.append(param_name)

            tool_definition = Tool(
                name=tool_name,
                description=f"{docstring.short_description or "No description available"}",
                inputSchema={
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            )
            
            tools[tool_name] = {
                "definition": tool_definition,
                "function": func
            }
            
        return tools