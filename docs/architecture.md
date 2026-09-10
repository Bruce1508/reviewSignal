# ReviewSignal AI — Architecture
**Pilot:** Maple Photo Imaging  
**Status:** Draft v1.2  
**Scope:** High-level system structure only.

## Documentation links
Product intent belongs in [`PRD.md`](PRD.md). This document
defines system boundaries; details live in [`ai-pipeline.md`](ai-pipeline.md),
[`data-model.md`](data-model.md), [`api-spec.md`](api-spec.md),
[`deployment.md`](deployment.md), and [`evaluation.md`](evaluation.md). Use
[`README.md`](README.md) for reading order and conflict resolution.

**Split out of this document:** [`subsystems.md`](subsystems.md) holds what were sections 7-16.
Numbering here keeps its gaps so existing `§N` citations resolve.

## 1. Purpose
ReviewSignal AI is an internal AI Customer Intelligence Platform that converts Google Business Profile reviews into structured feedback, trends, anomalies, insights, and trackable actions.
Architecture goals: simple for one developer, production-oriented, cost-conscious, local-model friendly, extensible beyond Google Reviews, and portfolio-ready.

## 2. Non-goals for MVP
- Multi-tenant SaaS or multiple locations.
- Kubernetes or complex microservices.
- Real-time streaming.
- Complex RBAC.
- Distributed training.

## 3. Tech Stack
| Layer | Technology |
|---|---|
| Frontend | Next.js + TypeScript |
| Backend | FastAPI + Python |
| Database | PostgreSQL |
| Queue | Redis + RQ/Celery |
| AI workflow | LangGraph |
| LLM utilities | LangChain |
| LLM runtime | Ollama |
| Reasoning model | Qwen |
| Deep learning | PyTorch |
| Embeddings | Sentence Transformers / BGE |
| ML | scikit-learn |
| Analytics | Pandas + NumPy + SciPy |
| Source | Google Business Profile API |
| Infra | Docker Compose + Nginx |
| Cloud | AWS EC2 + RDS |
| Monitoring | CloudWatch + app logs |

## 4. High-Level Architecture
```mermaid
flowchart TD
    G[Google Business Profile API] --> A[FastAPI]
    W[Next.js] --> A
    A --> D[(PostgreSQL)]
    A --> R[(Redis)]
    R --> Q[Worker]
    Q --> L[LangGraph]
    L --> O[Ollama + Qwen]
    Q --> E[BGE / Sentence Transformers]
    Q --> M[scikit-learn]
    Q --> S[Statistical Analytics]
    L --> D
    M --> D
    S --> D
    D --> A
```

## 5. Core Principle
> **LLM-powered, not LLM-dependent.**
Use Qwen for taxonomy generation/review, difficult classification, grounded explanations, and recommendations. Use normal software/ML/statistics for syncing, embeddings, routine classification, aggregation, trend calculation, anomaly detection, and dashboard metrics.

## 6. Main Components
### Next.js
Pages: `/overview`, `/reviews`, `/taxonomy`, `/trends`, `/insights`, `/settings`.
Responsibilities: presentation, filtering/search, taxonomy editing, insight/action management, manual job triggers, system status.
It never runs AI inference directly.

### FastAPI
Responsibilities: REST API, business logic, Google OAuth/API integration, taxonomy operations, analytics retrieval, job submission, settings, health endpoints.
Suggested modules: `api/`, `services/`, `repositories/`, `integrations/`, `ai/`, `analytics/`, `jobs/`.

### PostgreSQL
Source of truth for raw/normalized reviews, taxonomy versions/nodes, analyses, insights/actions, anomalies, sync runs, model runs, and evaluations.

### Redis + Worker
Async jobs: backfill, daily sync, review analysis, taxonomy rebuild, reclassification, classifier training, anomaly detection, insight generation, impact analysis.
Long-running AI work never blocks HTTP requests.

## 7. Review Ingestion
Moved to [`subsystems.md`](subsystems.md) §1. The heading stays so existing
`architecture.md` §7 citations still resolve.

## 13. Reliability
Moved to [`subsystems.md`](subsystems.md) §7. The heading stays so existing
`architecture.md` §13 citations still resolve.

## 17. Repository Shape
```text
reviewsignal-ai/
├── apps/web/
├── apps/api/
├── workers/
├── packages/ai/
├── packages/analytics/
├── packages/integrations/
├── infra/
├── docs/
└── tests/
```

## 18. Key Decisions
1. FastAPI because the AI/ML stack is Python-first.
2. PostgreSQL as single source of truth.
3. Async workers for slow/failure-prone workloads.
4. LangGraph for iterative stateful AI workflows.
5. LangChain only where utilities reduce boilerplate.
6. Ollama + Qwen for open-weight/local-first reasoning.
7. Hybrid ML + LLM classification for efficiency.
8. Statistical detection before LLM explanations.
9. Modular monolith first; microservices only when justified.

## 19. Related Docs
- [`ai-pipeline.md`](ai-pipeline.md): AI workflows/models; depends on the boundaries here and the persisted fields in [`data-model.md`](data-model.md).
- [`data-model.md`](data-model.md): database entities/relations; persists outputs from the pipeline and supports the API.
- [`api-spec.md`](api-spec.md): REST contracts; exposes the components and jobs described here.
- [`deployment.md`](deployment.md): AWS/Docker operations for this topology and its health checks.
- [`evaluation.md`](evaluation.md): benchmark and quality gates for AI decisions and model promotion.
- [`README.md`](README.md): documentation map, hierarchy, and conflict rules.

## 20. Summary
```text
Google Business Profile
→ FastAPI ingestion
→ PostgreSQL
→ Redis jobs
→ LangGraph / Qwen / ML / Statistics
→ Customer Intelligence
→ FastAPI
→ Next.js
```
The MVP is a **modular monolith with asynchronous AI workers**: simple enough to maintain, but structured enough to evolve.
