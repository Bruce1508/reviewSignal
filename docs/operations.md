# ReviewSignal AI — Operations
**Status:** Draft v1.1  
**Scope:** Running the deployed system: release, monitoring, backup, and failure response.

## Documentation links
Read [`README.md`](README.md) for hierarchy and conflict rules. These procedures operate the topology and
environments owned by [`deployment.md`](deployment.md), uphold the reliability boundary
in [`architecture.md`](architecture.md), and expose the health and job contracts in
[`api-spec.md`](api-spec.md).

[`deployment.md`](deployment.md) describes what the infrastructure is. This document
describes what an operator does to it after it exists.

## 1. Deployment Flow
```text
git push
→ tests
→ build
→ deploy EC2
→ migrations
→ restart containers
→ health check
```
Deployment is still manual. GitHub Actions runs the `make check` gate on every pull
request and on `main` (`.github/workflows/check.yml`), but it does not deploy.

## 2. Database Migrations
Use Alembic. Production order: backup/check → migrate → start API/worker → health check. Never edit production schema manually.

## 3. Scheduled Jobs
Daily Google sync can use worker scheduler or cron initially. EventBridge is a later option. Prefer the simplest mechanism that is visible and easy to debug.

## 4. Logging
Log timestamp, service, level, request/job ID, event, error. Never log secrets or OAuth tokens.

## 5. CloudWatch
Send API logs, worker logs, sync/model failures, and system metrics.
Minimum alerts: repeated sync failure, API unavailable, high disk usage, repeated worker failure, RDS storage warning.

## 6. Health Checks
Required:
```text
GET /api/v1/health
GET /api/v1/system/status
```
Check API, PostgreSQL, Redis, worker freshness; report Ollama/model health separately.

## 7. Backups
Use RDS automated backups. Keep deployment config in Git except secrets. Take manual snapshots before risky migrations/releases when appropriate.

## 8. Restore
```text
restore RDS snapshot
→ update connection
→ run required migrations
→ restart API/worker
→ verify health
```
Test restore procedures periodically.

## 9. Google OAuth
```text
Settings → Connect Google → OAuth → callback → protected token storage
```
Only backend handles OAuth secrets. Tokens are encrypted with
`CREDENTIAL_ENCRYPTION_KEY` and stored in `source_credentials`
([`data-model.md`](data-model.md) §18); the key itself stays in the environment.

## 10. Security Groups
EC2: allow 80/443 from Internet; SSH only from trusted IP if used.  
RDS: allow PostgreSQL only from app EC2/security group.

## 11. Updates
Regularly patch OS, Docker, Python/Node dependencies, Ollama. Model changes require benchmark evaluation before promotion.

## 12. Cost Control
Primary costs: EC2, RDS, possible GPU, storage/log retention.
Principles: one EC2 initially, small RDS, no always-on GPU unless justified, bounded log retention, scale from measurements.

## 13. Failure Scenarios
- Google API unavailable: retry, retain last successful sync, show warning.
- Worker crash: container restart + recoverable job.
- Ollama unavailable: retry AI job; existing dashboard remains usable.
- RDS unavailable: fail health check and pause write-dependent jobs.

## 14. Scaling Triggers
Split services only when API latency, queue backlog, model saturation, memory contention, or availability requirements justify it.

## 15. Future AWS Path
Possible: EC2→ECS/Fargate, Redis→ElastiCache, cron→EventBridge, queue→SQS, Ollama→dedicated GPU/vLLM. None are required for Maple Photo MVP.
