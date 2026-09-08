# ReviewSignal AI — Documentation Index

## Documentation hierarchy

```text
PRD.md (product source of truth: what/why)
        ↓
architecture.md (system-level how and boundaries)
        ↓
ai-pipeline.md · data-model.md · api-spec.md · deployment.md · evaluation.md
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

- [`architecture.md`](architecture.md) — system boundaries, components, lifecycle, and key decisions.
- [`ai-pipeline.md`](ai-pipeline.md) — taxonomy, classification, anomaly, insight, and model workflows.
- [`data-model.md`](data-model.md) — PostgreSQL entities, relationships, versioning, and retention.
- [`api-spec.md`](api-spec.md) — REST contracts, validation, authentication, and async jobs.
- [`deployment.md`](deployment.md) — local/AWS topology, operations, security, and failure handling.
- [`evaluation.md`](evaluation.md) — benchmark, metrics, calibration, regression, and promotion gates.

## Recommended reading order

1. `PRD.md` to understand product intent and scope.
2. `architecture.md` for system boundaries and non-goals.
3. The relevant subsystem document: `ai-pipeline.md`, `data-model.md`, or `api-spec.md`.
4. `deployment.md` for runtime and operational constraints.
5. `evaluation.md` for quality evidence and release decisions.

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

Six documents predate this limit and are still over it: `evaluation.md`, `deployment.md`,
`architecture.md`, `api-spec.md`, `ai-pipeline.md`, and `data-model.md`. Split them the way
`model-runs.md` was split out: move a section into its own document and leave a numbered
stub behind, because `§N` citations resolve by heading number and renumbering breaks them
all at once. New documents meet the limit from the start.
