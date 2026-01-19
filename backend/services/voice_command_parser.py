"""
Voice Command Parser
Parses voice commands and determines intent for execution
"""
import re
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class VoiceCommandParser:
    """Parse voice commands and extract intent + parameters"""
    
    # Command patterns with regex
    COMMAND_PATTERNS = {
        # Project management
        "create_project": [
            r"create (a |an )?project (called |named )?(.*)",
            r"new project (called |named )?(.*)",
            r"start (a |an )?project (called |named )?(.*)"
        ],
        "list_projects": [
            r"(list|show) (all )?(my )?projects",
            r"what projects (do|are) (i have|there)"
        ],
        "project_status": [
            r"what('?s| is) the status of (project )?(.+)",
            r"(project )?(.+) status"
        ],
        
        # Department queries
        "list_departments": [
            r"(list|show) (all |the )?departments",
            r"what departments (do|are) (we have|there)"
        ],
        "department_agents": [
            r"(list|show) agents in (.+) (department)?",
            r"who (works|is) in (the )?(.+) (department)?"
        ],
        
        # Council
        "list_councils": [
            r"(list|show) (all |the )?councils",
            r"what councils (do|are) (we have|there)"
        ],
        
        # System status
        "system_status": [
            r"(what'?s|how is) (the )?system status",
            r"system health( check)?",
            r"(check|show) (system )?status"
        ],
        
        # Navigation
        "open_dashboard": [
            r"open (the )?dashboard",
            r"go to (the )?dashboard",
            r"show (me )?(the )?dashboard"
        ],
        "open_projects": [
            r"open (the )?projects( page)?",
            r"go to projects",
            r"show (me )?(the )?projects"
        ],
        
        # General chat
        "chat": [
            r".*"  # Fallback: treat as general chat if no command matches
        ]
    }
    
    def parse(self, text: str) -> Dict[str, Any]:
        """
        Parse text and extract command intent + parameters
        
        Args:
            text: User's voice input text
        
        Returns:
            dict with 'is_command', 'command', 'parameters', 'original_text'
        """
        text_lower = text.lower().strip()
        
        # Try to match each command pattern
        for command, patterns in self.COMMAND_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    # Don't treat general chat pattern as a command
                    if command == "chat":
                        continue
                    
                    # Extract parameters from regex groups
                    parameters = self._extract_parameters(command, match)
                    
                    logger.info(f"Matched command: {command} with params: {parameters}")
                    
                    return {
                        "is_command": True,
                        "command": command,
                        "parameters": parameters,
                        "original_text": text,
                        "confidence": 1.0
                    }
        
        # No command matched → treat as general chat
        logger.info(f"No command matched, treating as chat: '{text[:50]}...'")
        return {
            "is_command": False,
            "command": "chat",
            "parameters": {},
            "original_text": text,
            "confidence": 0.0
        }
    
    def _extract_parameters(self, command: str, match: re.Match) -> Dict[str, Any]:
        """Extract parameters from regex match groups"""
        params = {}
        
        if command == "create_project":
            # Extract project name from last group
            groups = [g for g in match.groups() if g]
            if groups:
                params["name"] = groups[-1].strip()
        
        elif command == "project_status":
            # Extract project ID/name
            groups = [g for g in match.groups() if g]
            if groups:
                params["project_name"] = groups[-1].strip()
        
        elif command == "department_agents":
            # Extract department name
            groups = [g for g in match.groups() if g]
            for g in groups:
                if g and g not in ["list", "show", "agents", "in", "works", "is", "the", "department"]:
                    params["department"] = g.strip()
                    break
        
        return params
    
    def get_help_text(self) -> str:
        """Get help text listing available commands"""
        return """
Available voice commands:

**Projects**:
- "Create a project called [name]"
- "List all projects"
- "What's the status of project [name]"

**Departments**:
- "List all departments"  
- "Show agents in [department] department"

**Councils**:
- "List all councils"

**System**:
- "System status"
- "Open dashboard"
- "Open projects"

**Chat**:
- Any other input is treated as a chat message to Daena
"""
