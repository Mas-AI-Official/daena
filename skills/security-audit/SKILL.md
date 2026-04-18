---
name: security-audit
description: "Security audit: scan code for vulnerabilities, check configurations, review access patterns. Use when user asks about security, compliance, or wants a security review."
department: Security Operations
cost_tier: high
requires: {}
---

# Security Audit Skill

Assess security posture of code, configurations, and systems.

## When to Use

- Code security review (OWASP Top 10)
- Configuration audit (secrets, permissions, CORS)
- Dependency vulnerability scan
- Access pattern review
- Compliance checks

## Audit Checklist

### Code Review
- [ ] SQL injection (parameterized queries?)
- [ ] XSS (output encoding?)
- [ ] CSRF (token validation?)
- [ ] Auth bypass (all endpoints protected?)
- [ ] Secrets in code (API keys, passwords?)
- [ ] Input validation (type, length, format?)
- [ ] Error handling (no stack traces leaked?)

### Configuration
- [ ] CORS restrictive (no wildcard in prod?)
- [ ] HTTPS enforced?
- [ ] Debug mode off in production?
- [ ] Secrets in env vars, not code?
- [ ] Rate limiting enabled?
- [ ] JWT expiry reasonable?

### Dependencies
```bash
# Python
pip audit
safety check

# Node
npm audit
```

### Access
- [ ] Principle of least privilege?
- [ ] Multi-tenant isolation?
- [ ] Admin endpoints protected?
- [ ] Audit logging enabled?

## Severity Levels

- CRITICAL: Active exploit possible, data at risk
- HIGH: Vulnerability exploitable with effort
- MEDIUM: Defense-in-depth gap
- LOW: Best practice recommendation
- INFO: Observation, no action needed
