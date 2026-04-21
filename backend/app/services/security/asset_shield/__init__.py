"""Asset Shield: asymmetric-governance primitives.

The Asset Shield protects OPERATOR assets (API keys, finance,
identity, legal, founder-private memory) from egress while ENABLING
offensive work against targets. Three primitives:

    * ``VaultAdapter``: wraps the existing AES-256 vault, exposes a
      fingerprint API that the Egress Filter can scan against.
    * ``EgressFilter``: Aho-Corasick-style multi-pattern scan of
      every outbound byte (tool output, LLM stream chunk, SSE event,
      audit payload).
    * ``ConsentToken``: one-shot, destination-bound credential lease
      for pivot-with-creds operations.
    * ``is_operator_initiated``: 5-minute session-lineage trace that
      decides auto-consent vs interactive gate.

See ``backend/app/services/security/asset_shield/*.py`` for details.
"""

from app.services.security.asset_shield.consent_token import (
    ConsentToken,
    ConsentTokenExpired,
    ConsentTokenRevoked,
    clear_tokens,
    mint_token,
    use_token,
)
from app.services.security.asset_shield.egress_filter import (
    EgressFilter,
    EgressRedaction,
)
from app.services.security.asset_shield.operator_initiation import (
    is_operator_initiated,
    mark_operator_initiated,
)
from app.services.security.asset_shield.vault_adapter import (
    VaultAdapter,
    list_asset_classes,
    register_fingerprint,
)

__all__ = [
    "ConsentToken",
    "ConsentTokenExpired",
    "ConsentTokenRevoked",
    "clear_tokens",
    "EgressFilter",
    "EgressRedaction",
    "VaultAdapter",
    "is_operator_initiated",
    "list_asset_classes",
    "mark_operator_initiated",
    "mint_token",
    "register_fingerprint",
    "use_token",
]
