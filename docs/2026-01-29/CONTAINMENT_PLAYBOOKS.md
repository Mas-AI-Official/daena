# Guardian Containment Playbooks

## Overview

When decoy routes are hit or operators trigger containment, the security containment service can block IPs, set lockdown, and log playbook actions. This integrates deception hits with Guardian-style response.

## Service: `backend/services/security_containment.py`

- **Blocklist**: In-memory set of blocked IPs; requests from these IPs get 403 in lockdown middleware (before lockdown check).
- **On deception hit**: Each decoy hit calls `on_deception_hit(hit)`. The service counts hits per IP in a sliding window; after `DECEPTION_HITS_BEFORE_BLOCK` hits from the same IP in `DECEPTION_HITS_WINDOW_SEC` seconds, that IP is auto-added to the blocklist. If `AUTO_LOCKDOWN_ON_BLOCK` is true, lockdown is also set.
- **Playbook log**: Last N actions (block_ip, unblock_ip, lockdown, auto_block, etc.) are kept in memory for the status API.

## Config (env)

| Env | Default | Description |
|-----|---------|-------------|
| `DECEPTION_HITS_BEFORE_BLOCK` | 3 | Number of decoy hits from same IP in window before auto-block |
| `DECEPTION_HITS_WINDOW_SEC` | 300 | Sliding window (seconds) for counting hits per IP |
| `AUTO_LOCKDOWN_ON_BLOCK` | false | If true, set lockdown when an IP is auto-blocked |

## API: `GET/POST /api/v1/security/containment/*`

- **GET /api/v1/security/containment/status** – `blocked_ips`, `blocked_count`, `recent_playbook`, `config`
- **POST /api/v1/security/containment/block-ip** – Body: `{ "ip": "1.2.3.4", "reason": "manual" }`
- **POST /api/v1/security/containment/unblock-ip** – Body: `{ "ip": "1.2.3.4" }`
- **POST /api/v1/security/containment/playbook** – Body: `{ "action": "lockdown" \| "block_ip" \| "unblock_ip", "payload": { ... } }`. For `block_ip`/`unblock_ip`, `payload.ip` is required.

Containment API is whitelisted during lockdown so operators can unblock IPs and run playbooks from Incident Room.

## Flow

1. Attacker hits a decoy route → `deception._log_hit` → `emit("security.deception_hit", hit)` and `on_deception_hit(hit)`.
2. Containment service counts hit per IP; if threshold reached, adds IP to blocklist and optionally sets lockdown.
3. All subsequent requests from that IP get 403 (lockdown middleware checks blocklist first).
4. Operator opens Incident Room, sees decoy hits, can run playbook (unblock_ip, lockdown) or use founder-panel unlock.

## QA Guardian

Guardian loop and quarantine manager remain separate (agent quarantine, incidents). Containment playbooks are for **security** (deception, IP block, lockdown). To have Guardian automatically run containment on incidents, you could subscribe to `security.deception_hit` from EventLog or call the containment API from Guardian logic when severity is high.
