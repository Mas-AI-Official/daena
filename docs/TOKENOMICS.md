# $DAENA Token Design (AGI-Native)

## Overview

$DAENA is the native utility token for the DAENA Control Plane and MAS-AI Company ecosystem. It is designed for governance, agent licensing, and treasury operations—not as a speculative asset.

## Design Principles

- **AGI-native**: Aligns incentives with autonomous agent operations and human oversight.
- **Governance-gated**: Treasury spend and high-risk actions require governance approval (see `governance_loop.py`).
- **Utility-first**: Used for agent licenses (NFTs), API access, and internal accounting.

## Token Spec

| Attribute | Value |
|-----------|--------|
| Symbol | $DAENA |
| Initial supply | 1,000,000 (configurable at deployment) |
| Decimals | 18 |
| Standard | ERC-20 compatible |
| Treasury | Multisig / governance-controlled |

## Use Cases

1. **Agent licenses**: NFTs (e.g. 48 agent slots) minted and tracked per department.
2. **Treasury reserve**: ETH/stablecoins held; $DAENA balance for internal accounting.
3. **Governance**: Future: stake or vote weight (out of scope for initial implementation).
4. **Spend**: All treasury spend is `TREASURY_SPEND` in governance—risk level CRITICAL; requires explicit approval.

## Contracts (Reference)

- See `contracts/` for interface specs and deployment notes.
- Backend API: `GET /api/v1/treasury/status` returns balances and transactions (placeholder until chain deployment).
- Frontend: Control Plane → Treasury tab consumes this API.

## Compliance

- Not offered as investment or security. For internal/ecosystem use only.
- Patch timeline and disclosure: see `SECURITY.md`.
