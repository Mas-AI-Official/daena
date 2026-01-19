"""
Deterministic Gate - No-LLM Execution Path
Handles trivial tasks without calling any LLM to save tokens and improve speed.
"""

import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Types of deterministic tasks"""
    MATH = "math"
    TIME = "time"
    JSON_FORMAT = "json_format"
    JSON_EXTRACT = "json_extract"
    STRING_TRANSFORM = "string_transform"
    VALIDATION = "validation"
    LOOKUP = "lookup"
    UNKNOWN = "unknown"


class DeterministicGate:
    """
    Handles trivial tasks without LLM calls.
    Returns immediately if task can be handled deterministically.
    """
    
    def __init__(self):
        self.enabled = True
        self.math_patterns = [
            r'\b(\d+(?:\.\d+)?)\s*([+\-*/%])\s*(\d+(?:\.\d+)?)\b',  # Basic ops
            r'\b(\d+(?:\.\d+)?)\s*percent\s+of\s+(\d+(?:\.\d+)?)\b',  # Percentages
            r'\b(\d+(?:\.\d+)?)\s*%\s+of\s+(\d+(?:\.\d+)?)\b',
            r'\bwhat\s+is\s+(\d+(?:\.\d+)?)\s*([+\-*/%])\s*(\d+(?:\.\d+)?)\b',
            r'\bcalculate\s+(\d+(?:\.\d+)?)\s*([+\-*/%])\s*(\d+(?:\.\d+)?)\b',
        ]
        self.time_patterns = [
            r'\bwhat\s+time\s+is\s+it\b',
            r'\bcurrent\s+time\b',
            r'\bwhat\s+date\s+is\s+it\b',
            r'\btoday\'?s\s+date\b',
        ]
        self.json_patterns = [
            r'\bformat\s+(?:this\s+)?json\b',
            r'\bparse\s+json\b',
            r'\bextract\s+(?:keys?|values?)\s+from\s+json\b',
        ]
    
    def try_handle(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Try to handle the input deterministically.
        
        Returns:
            (handled: bool, result: Dict)
            result contains: handled, result (str), metadata (dict)
        """
        if not self.enabled:
            return False, {"handled": False}
        
        user_input_lower = user_input.lower().strip()
        
        # 1. Math operations
        math_result = self._handle_math(user_input_lower)
        if math_result["handled"]:
            return True, math_result
        
        # 2. Time/date queries
        time_result = self._handle_time(user_input_lower)
        if time_result["handled"]:
            return True, time_result
        
        # 3. JSON operations
        json_result = self._handle_json(user_input, user_input_lower)
        if json_result["handled"]:
            return True, json_result
        
        # 4. String transforms
        string_result = self._handle_string_transform(user_input, user_input_lower)
        if string_result["handled"]:
            return True, string_result
        
        # 5. Validation
        validation_result = self._handle_validation(user_input, user_input_lower)
        if validation_result["handled"]:
            return True, validation_result
        
        return False, {"handled": False}
    
    def _handle_math(self, input_lower: str) -> Dict[str, Any]:
        """Handle simple arithmetic without eval() for safety."""
        for pattern in self.math_patterns:
            match = re.search(pattern, input_lower)
            if match:
                try:
                    if '%' in match.group(0) or 'percent' in match.group(0):
                        # Percentage calculation
                        if '%' in match.group(0):
                            parts = re.split(r'%', match.group(0))
                            percent = float(re.search(r'\d+(?:\.\d+)?', parts[0]).group())
                            total = float(re.search(r'\d+(?:\.\d+)?', parts[1]).group())
                        else:
                            percent = float(match.group(1))
                            total = float(match.group(2))
                        result = (percent / 100) * total
                        return {
                            "handled": True,
                            "result": f"{result:.2f}",
                            "metadata": {
                                "type": TaskType.MATH.value,
                                "confidence": 1.0,
                                "reason": "Percentage calculation",
                                "operation": f"{percent}% of {total}"
                            }
                        }
                    else:
                        # Basic arithmetic
                        if len(match.groups()) >= 3:
                            num1 = float(match.group(1))
                            op = match.group(2)
                            num2 = float(match.group(3))
                            
                            # Safe arithmetic (no eval)
                            if op == '+':
                                result = num1 + num2
                            elif op == '-':
                                result = num1 - num2
                            elif op == '*':
                                result = num1 * num2
                            elif op == '/':
                                if num2 == 0:
                                    return {"handled": False}
                                result = num1 / num2
                            elif op == '%':
                                result = num1 % num2
                            else:
                                return {"handled": False}
                            
                            return {
                                "handled": True,
                                "result": str(result),
                                "metadata": {
                                    "type": TaskType.MATH.value,
                                    "confidence": 1.0,
                                    "reason": "Arithmetic operation",
                                    "operation": f"{num1} {op} {num2}"
                                }
                            }
                except (ValueError, AttributeError, ZeroDivisionError):
                    continue
        
        return {"handled": False}
    
    def _handle_time(self, input_lower: str) -> Dict[str, Any]:
        """Handle time/date queries."""
        for pattern in self.time_patterns:
            if re.search(pattern, input_lower):
                now = datetime.now()
                if 'date' in input_lower:
                    result = now.strftime("%Y-%m-%d")
                    detail = f"Today is {now.strftime('%A, %B %d, %Y')}"
                else:
                    result = now.strftime("%H:%M:%S")
                    detail = f"Current time: {now.strftime('%I:%M %p')} on {now.strftime('%B %d, %Y')}"
                
                return {
                    "handled": True,
                    "result": f"{result}\n{detail}",
                    "metadata": {
                        "type": TaskType.TIME.value,
                        "confidence": 1.0,
                        "reason": "Time/date query"
                    }
                }
        
        return {"handled": False}
    
    def _handle_json(self, input_text: str, input_lower: str) -> Dict[str, Any]:
        """Handle JSON formatting/extraction."""
        # Check if input contains JSON
        json_match = re.search(r'\{[^{}]*\}', input_text)
        if json_match:
            try:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                
                if 'format' in input_lower or 'pretty' in input_lower:
                    result = json.dumps(data, indent=2)
                    return {
                        "handled": True,
                        "result": result,
                        "metadata": {
                            "type": TaskType.JSON_FORMAT.value,
                            "confidence": 1.0,
                            "reason": "JSON formatting"
                        }
                    }
                elif 'extract' in input_lower or 'keys' in input_lower:
                    if 'keys' in input_lower:
                        result = ", ".join(data.keys() if isinstance(data, dict) else [])
                    elif 'values' in input_lower:
                        result = ", ".join(str(v) for v in (data.values() if isinstance(data, dict) else []))
                    else:
                        return {"handled": False}
                    
                    return {
                        "handled": True,
                        "result": result,
                        "metadata": {
                            "type": TaskType.JSON_EXTRACT.value,
                            "confidence": 1.0,
                            "reason": "JSON extraction"
                        }
                    }
            except json.JSONDecodeError:
                pass
        
        return {"handled": False}
    
    def _handle_string_transform(self, input_text: str, input_lower: str) -> Dict[str, Any]:
        """Handle simple string transformations."""
        # Uppercase
        if re.search(r'\buppercase\s+(.+?)(?:\s|$)', input_lower):
            match = re.search(r'\buppercase\s+(.+?)(?:\s|$)', input_lower)
            if match:
                text = match.group(1).strip('"\'')
                return {
                    "handled": True,
                    "result": text.upper(),
                    "metadata": {
                        "type": TaskType.STRING_TRANSFORM.value,
                        "confidence": 1.0,
                        "reason": "Uppercase transform"
                    }
                }
        
        # Lowercase
        if re.search(r'\blowercase\s+(.+?)(?:\s|$)', input_lower):
            match = re.search(r'\blowercase\s+(.+?)(?:\s|$)', input_lower)
            if match:
                text = match.group(1).strip('"\'')
                return {
                    "handled": True,
                    "result": text.lower(),
                    "metadata": {
                        "type": TaskType.STRING_TRANSFORM.value,
                        "confidence": 1.0,
                        "reason": "Lowercase transform"
                    }
                }
        
        # Word count
        if 'word count' in input_lower or 'count words' in input_lower:
            words = len(input_text.split())
            return {
                "handled": True,
                "result": str(words),
                "metadata": {
                    "type": TaskType.STRING_TRANSFORM.value,
                    "confidence": 1.0,
                    "reason": "Word count"
                }
            }
        
        return {"handled": False}
    
    def _handle_validation(self, input_text: str, input_lower: str) -> Dict[str, Any]:
        """Handle validation tasks."""
        # Email validation
        if 'validate email' in input_lower or 'is valid email' in input_lower:
            email_match = re.search(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', input_text)
            if email_match:
                email = email_match.group(0)
                is_valid = bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email))
                return {
                    "handled": True,
                    "result": f"{'Valid' if is_valid else 'Invalid'} email: {email}",
                    "metadata": {
                        "type": TaskType.VALIDATION.value,
                        "confidence": 1.0,
                        "reason": "Email validation"
                    }
                }
        
        return {"handled": False}


# Global instance
_deterministic_gate_instance: Optional[DeterministicGate] = None

def get_deterministic_gate() -> DeterministicGate:
    """Get singleton instance"""
    global _deterministic_gate_instance
    if _deterministic_gate_instance is None:
        _deterministic_gate_instance = DeterministicGate()
    return _deterministic_gate_instance




