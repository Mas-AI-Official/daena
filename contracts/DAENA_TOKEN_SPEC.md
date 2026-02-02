# $DAENA Token — Contract Spec

## Interface (ERC-20 style)

- **name**: "DAENA"
- **symbol**: "DAENA"
- **decimals**: 18
- **totalSupply()**: initial 1_000_000 * 10**18
- **balanceOf(address)**: treasury / agent balances
- **transfer**, **approve**, **transferFrom**: standard; treasury spend must go through governance (backend enforces TREASURY_SPEND = CRITICAL).

## Deployment

- Deploy after governance and treasury API are stable.
- Treasury wallet = multisig or governance-controlled address.
- Backend `GET /api/v1/treasury/status` can be wired to chain (e.g. Web3 provider) or remain config/DB until deployment.

## References

- `docs/TOKENOMICS.md` — token design and use cases
- `backend/routes/treasury.py` — API for Control Plane Treasury tab
- `backend/services/governance_loop.py` — TREASURY_SPEND risk level
