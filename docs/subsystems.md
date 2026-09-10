# ReviewSignal AI — Subsystem Boundaries
**Status:** Draft v1.1  
**Scope:** Per-subsystem responsibilities: ingestion, AI, taxonomy, classification, analytics, insights, and cross-cutting concerns.

## Documentation links
Read [`README.md`](README.md) for hierarchy and conflict rules. These boundaries sit under the system shape owned
by [`architecture.md`](architecture.md) and are realised by
[`ai-pipeline.md`](ai-pipeline.md), [`data-model.md`](data-model.md),
[`api-spec.md`](api-spec.md), and [`deployment.md`](deployment.md).

[`architecture.md`](architecture.md) answers "what is the system made of". This document
answers "what is each part responsible for, and what must it not do".

## 1. Review Ingestion
Initial setup:
```text
Google Business Profile
→ backfill historical reviews
→ normalize + preserve raw payload
→ PostgreSQL
→ initial taxonomy
→ historical classification
→ baseline analytics
```
Daily sync:
```text
scheduler
→ fetch new/updated reviews
→ persist
→ queue analysis
→ update analytics
→ detect anomalies
→ generate/update insights
```
The ingestion contract should be source-agnostic so Yelp, surveys, or support tickets can be added later.

## 2. AI System Boundaries
Four AI-facing subsystems:
1. Taxonomy discovery/refinement.
2. Review classification + aspect sentiment.
3. Anomaly interpretation.
4. Action recommendation.
Detailed behavior lives in `ai-pipeline.md`.

## 3. Taxonomy Lifecycle
```text
reviews
→ generate/update taxonomy
→ quality gate
→ activate version
→ reclassify history
→ recompute analytics
```
Manager edits: rename, merge, split, add, delete, move, rollback. Every mutation creates a new immutable taxonomy version.

## 4. Classification Strategy
Start with Qwen classification, then evolve to:
```text
review
→ embedding
→ ML classifier
→ confidence gate
   ├─ high → accept
   └─ low/novel → Qwen fallback
```
This keeps quality while reducing inference cost.

## 5. Analytics & Insights
```text
structured review labels
→ aggregation
→ statistical anomaly detection
→ evidence packet
→ Qwen explanation
→ action recommendation
```
Statistics decide whether a pattern is unusual. The LLM explains verified evidence rather than inventing trends.

## 6. Insight Lifecycle
States: `New → Monitoring → Resolved`.
The system may suggest transitions; the user can override status and add operational notes. Actions can be compared before/after, but the system must not claim causal proof.

## 7. Reliability
All external/AI jobs follow:
```text
run → retry with backoff → retry → dead-letter queue
```
A failure arising from configuration or registration the job itself cannot change — an unregistered predictor, an unset benchmark path — skips the backoff schedule and dead-letters on its first attempt. The chain above is for failures that might not recur; spending it on one that recurs identically only delays the same outcome and reports three failures where there was one, which `api-spec.md` §2 surfaces as operational alarm.
A job type with no registered handler stays on the full chain, because it has a transient reading the two above do not: during a rolling deploy an updated API can queue work the older worker cannot yet route, and a retry succeeds once that worker is upgraded.
Required protections: idempotent Google sync, structured-output validation, model timeout handling, failed-job inspection, and manual requeue.

## 8. Security
- Google OAuth secrets never enter source control.
- HTTPS only in production.
- PostgreSQL, Redis, and Ollama are private.
- FastAPI is the only public application boundary.
- Dashboard access is restricted to the owner/admin.
- Secrets use environment variables or AWS secret storage.

## 9. Deployment
Development:
```text
MacBook: Next.js + FastAPI + PostgreSQL + Redis + Worker + Ollama
```
Production MVP:
```text
AWS EC2: Nginx + Next.js + FastAPI + Redis + Worker + Ollama where practical
AWS RDS: PostgreSQL
CloudWatch: logs + basic alerts
```
No Kubernetes for MVP.

## 10. Scalability Path
Stage 1: `EC2 + Docker Compose + RDS`.  
Stage 2: split Web/API, worker, and AI inference only if measured contention appears.  
Stage 3: future SaaS may adopt ECS/Fargate, SQS, dedicated inference, multi-tenancy, and multiple connectors.
