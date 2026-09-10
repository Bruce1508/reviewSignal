# ReviewSignal AI — Documentation Index

## Documentation hierarchy

```text
PRD.md (product source of truth: what/why)
        ↓
architecture.md (system-level how and boundaries)
        ↓
subsystem documents (pipeline · data · API · runtime · evaluation)
        ↓
implementation and tests
```

`PRD.md` v1.0 is the product source of truth. The technical documents describe
the decisions and constraints below that product layer and must not silently
redefine a product requirement.

**Not in this repository.** `PRD.md` is client-confidential and excluded via
`.gitignore`. Links to it resolve in a local checkout and 404 on GitHub. Anyone
working on this code needs the local copy; requirements must never be inferred
from the technical documents alone.

## Document map

**System**
- [`architecture.md`](architecture.md) — system shape, stack, repository layout, and key decisions.
- [`subsystems.md`](subsystems.md) — what each subsystem is responsible for, and what it must not do.

**AI pipeline**
- [`ai-pipeline.md`](ai-pipeline.md) — pipeline overview, model abstraction, prompt versioning, failure handling.
- [`taxonomy-pipeline.md`](taxonomy-pipeline.md) — discovering, reviewing, accepting, and rebuilding the taxonomy.
- [`classification-pipeline.md`](classification-pipeline.md) — aspects, sentiment, evidence, and confidence routing.
- [`insight-pipeline.md`](insight-pipeline.md) — metrics, anomalies, insights, and tracked actions.

**Data**
- [`data-model.md`](data-model.md) — principles, relationships, `reviews`, constraints, and retention.
- [`taxonomy-tables.md`](taxonomy-tables.md) — taxonomy versions, nodes, and changes.
- [`analysis-tables.md`](analysis-tables.md) — analyses, aspects, anomalies, insights, and actions.
- [`operational-tables.md`](operational-tables.md) — sync runs, jobs, settings, and credentials.
- [`model-runs.md`](model-runs.md) — `model_runs` and `evaluation_runs`: what happened during one execution.

**API**
- [`api-spec.md`](api-spec.md) — conventions, validation, authentication, errors, and the async contract.
- [`api-dashboard.md`](api-dashboard.md) — the page-facing endpoints and the jobs they poll.

**Runtime**
- [`deployment.md`](deployment.md) — local and AWS topology, services, network, and environment.
- [`operations.md`](operations.md) — release, monitoring, backup and restore, and failure response.

**Evaluation**
- [`evaluation.md`](evaluation.md) — benchmark, classifier metrics, regression, and promotion gates.
- [`taxonomy-insight-evaluation.md`](taxonomy-insight-evaluation.md) — taxonomy quality, anomaly, insight, and recommendation scoring.

## Recommended reading order

1. `PRD.md` to understand product intent and scope.
2. `architecture.md` for system boundaries and non-goals.
3. `subsystems.md` for the responsibility split between the parts.
4. The relevant subsystem document from the map above, then only the siblings its links name.
5. `deployment.md` and `operations.md` for runtime and operational constraints.
6. `evaluation.md` for quality evidence and release decisions.

For a feature, start with the PRD requirement, trace it to architecture, then
follow the links from the relevant subsystem document. Read only the sibling
documents that its dependency links identify.

## Source of truth and conflicts

- Product behavior, scope, and acceptance intent: `PRD.md`.
- System boundaries and technical constraints: `architecture.md`.
- Detailed contracts: the owning technical document linked above.
- Actual behavior: implementation and tests, which may reveal drift but do not silently redefine requirements.

If two documents disagree, pause implementation, record the exact conflicting
statements, and resolve the conflict at the higher-level source of truth. A
technical document must not silently change a product requirement; update the
affected links and dependent documents after the decision is made.

**Documentation rule:** every technical document stays at or below 150 physical lines and focuses on one responsibility.

Every document now meets it. To split one, move whole sections into a new document and
never renumber what stays: `§N` citations resolve by heading number, so renumbering breaks
them all at once. Leave a numbered stub behind for any section that is cited, and record
the move in a **Split out of this document** line so the numbering gaps are explained.

A bare `§N` inside moved text is a self-reference and moves with it, so it must be
renumbered to the new document. `make check` reads `docs/` and catches this; a reader
scanning the prose will not.
