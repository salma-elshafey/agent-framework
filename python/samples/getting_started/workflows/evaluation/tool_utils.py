"""
Utilities for extracting and formatting tool definitions from Agent Framework conversations.
"""

import inspect
from typing import Dict, List, Any, Union


def extract_tool_definitions_by_agent() -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract tool definitions organized by agent name in converter output format.
    
    Returns:
        Dict mapping agent names to their tool definition lists in converter format
    """
    from _tools import (
        run_calculator, get_date_information, google_search, wikipedia_search, wolfram_alpha_query,
        get_current_weather, get_historical_weather,
        get_intraday_time_series, get_daily_time_series, find_stock_ticker
    )
    
    # Agent tool mappings
    agent_tools = {
        "general_tools_assistant": [
            run_calculator, get_date_information, google_search, 
            wikipedia_search, wolfram_alpha_query
        ],
        "weather_tools_assistant": [
            get_current_weather, get_historical_weather
        ],
        "financial_tools_assistant": [
            get_intraday_time_series, get_daily_time_series, find_stock_ticker
        ]
    }
    
    tool_definitions_by_agent = {}
    
    for agent_name, tools in agent_tools.items():
        tool_definitions_by_agent[agent_name] = []
        
        for tool_func in tools:
            tool_def = _convert_function_to_tool_definition(tool_func)
            tool_definitions_by_agent[agent_name].append(tool_def)
    
    return tool_definitions_by_agent


def _convert_function_to_tool_definition(func) -> Dict[str, Any]:
    """
    Convert a Python function to OpenAI tool definition format.
    
    Args:
        func: Python function to convert
        
    Returns:
        Tool definition in converter output format
    """
    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or "No description available"
    
    # Build parameters object
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    for param_name, param in sig.parameters.items():
        # Determine parameter type
        param_type = _get_parameter_type(param.annotation)
        
        # Extract parameter description from docstring if available
        param_description = f"The {param_name} parameter."
        
        parameters["properties"][param_name] = {
            "type": param_type,
            "description": param_description
        }
        
        # Add to required if no default value
        if param.default == inspect.Parameter.empty:
            parameters["required"].append(param_name)
    
    return {
        "name": func.__name__,
        "type": "function",
        "description": doc.strip(),
        "parameters": parameters
    }


def _get_parameter_type(annotation) -> str:
    """Convert Python type annotation to JSON schema type."""
    if annotation == inspect.Parameter.empty:
        return "string"  # Default to string
    
    type_mapping = {
        str: "string",
        int: "integer", 
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object"
    }
    
    # Handle Union types (like Optional[str])
    if hasattr(annotation, '__origin__'):
        if annotation.__origin__ is Union:
            # For Optional[T], use the non-None type
            non_none_types = [t for t in annotation.__args__ if t != type(None)]
            if non_none_types:
                return _get_parameter_type(non_none_types[0])
        elif annotation.__origin__ in (list, List):
            return "array"
        elif annotation.__origin__ in (dict, Dict):
            return "object"
    
    return type_mapping.get(annotation, "string")


def format_tool_calls_for_converter(sequential_tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format captured tool calls into converter output format.
    
    Args:
        sequential_tool_calls: List of captured tool call dictionaries
        
    Returns:
        List of tool calls in converter format
    """
    formatted_calls = []
    
    for call in sequential_tool_calls:
        formatted_call = {
            "type": "tool_call",
            "name": call["function"],
            "arguments": call.get("args", {}),
            "call_id": call["call_id"],
            "agent": call["agent"]
        }
        formatted_calls.append(formatted_call)
    
    return formatted_calls