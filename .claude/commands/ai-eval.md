---
description: Evaluate a ReviewSignal model, prompt, classifier, taxonomy, or AI workflow.
allowed-tools: Read, Grep, Glob, Bash
---
# AI Evaluation
Target: $ARGUMENTS

## Context
1. Read `CLAUDE.md` and `docs/README.md`.
2. If `docs/PRD.md` exists, identify the relevant product acceptance intent.
3. Read `docs/architecture.md`, `docs/evaluation.md`, and the relevant section of
   `docs/ai-pipeline.md`.
4. Read dependencies as needed:
   - `docs/data-model.md` for run/version records and persisted outputs,
   - `docs/api-spec.md` for evaluation endpoints or exposed behavior,
   - `docs/deployment.md` for latency, memory, runtime, or production signals.

If these sources conflict, report a `SPEC CONFLICT` before interpreting results.

## Evaluation
1. Identify dataset, taxonomy, model, prompt, classifier, and benchmark versions.
2. Confirm that candidate and production baseline use comparable data and metrics.
3. Run the evaluation defined for the target.
4. Compare the candidate with the production baseline.
5. Inspect representative errors, rare categories, and failure cases—not only
   aggregate metrics.
6. Check structured-output reliability and latency, confidence calibration,
   novelty, or fallback rate where relevant.
7. Record limitations and missing evidence.

## Verdict
Recommend `PROMOTE`, `DO NOT PROMOTE`, or `NEEDS MORE DATA`, with the evidence
supporting the decision. Never fabricate metrics or promote from impressions.

Flag implementation findings for `.claude/commands/review.md` and documentation
drift for `.claude/commands/docs-sync.md`.
