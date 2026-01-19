"""
Dev User for Local Development - No Auth Mode
"""

from pydantic import BaseModel
from typing import List


class DevUser(BaseModel):
    """Mock user for local development when DISABLE_AUTH=True"""

    id: str = "local-dev-founder"
    user_id: str = "local-dev-founder"
    username: str = "Masoud"
    name: str = "Masoud"
    email: str = "masoud@daena.ai"
    role: str = "founder"
    roles: List[str] = ["founder", "admin"]
    is_admin: bool = True
    is_active: bool = True

    def has_role(self, role: str) -> bool:
        return role.lower() in [r.lower() for r in self.roles]

    def is_founder(self) -> bool:
        return "founder" in [r.lower() for r in self.roles]











