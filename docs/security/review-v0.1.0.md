# Security review – v0.1.0

Scope: self-review of this repository before the first release. It is **not** an
independent audit or penetration test, and the project is not deployed.

## Automated checks (run 2026-11-01, all clean)
| Check | Result |
|---|---|
| Bandit (core, API, infra source) | no findings |
| pip-audit (Python dependencies) | no known vulnerabilities |
| npm audit --omit=dev (dashboard) | 0 vulnerabilities |
| Ruff `S` rules, mypy strict | clean |
| Dependabot (pip, npm, actions) | enabled |

## Controls in place
- Auth: header principal only when `FRESHCAST_ENV=local`; any other env returns 501 (tested).
- RBAC with least-privilege roles; four-eyes approval (requester cannot approve own proposal).
- Strict request schemas (unknown fields rejected), SQLAlchemy parameterised queries.
- Audit log for state changes; idempotent, versioned events (no double processing).
- AI: model never decides quantities; number guard rejects ungrounded figures; prompt-injection test; template fallback.
- Infra (CDK, tests only): KMS-encrypted S3/RDS/SQS, no public access, no NAT, EU region guard, DLQ.
- No secrets in repo; `.env.example` only; DB credentials via Secrets Manager.

## Open findings (must be closed before any real deployment)
| # | Finding | Severity |
|---|---|---|
| 1 | Cognito JWT validation not implemented; the API is unusable outside `local` | High (blocker) |
| 2 | Worker stage recomputation is a logging placeholder; no outbox-to-SQS sink | Medium |
| 3 | CDK does not grant `bedrock:InvokeModel` or define an API/Lambda front end | Medium |
| 4 | In-memory rate limit added (per process); still no WAF, and no CloudWatch dashboards or alarms on business metrics | Medium |
| 5 | Dashboard has no auth; approve button is client-only | Medium |
| 6 | ~~Prediction interval under-calibrated~~ Fixed in phase 11 (conformal calibration, 80.9% coverage on synthetic data; still to be re-checked on real data) | Closed |
| 7 | GitHub OIDC deploy role not created; no deployment has been exercised | Low |
| 8 | Colour contrast of dashboard not verified in a real browser | Low |

## Compliance note
No certification is claimed. See `docs/compliance/README.md` for the evidence-based mapping (GDPR, EU AI Act transparency, BSI-style hygiene).
