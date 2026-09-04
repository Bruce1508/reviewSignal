---
name: ai-evaluation
description: AI evaluation patterns for ReviewSignal taxonomy, aspect classification, sentiment, calibration, anomaly detection, recommendations, prompts, embeddings, and model promotion.
allowed-tools: Read, Grep, Glob
---
# AI Evaluation

## Ground Truth
Use the manually reviewed benchmark. Never fabricate labels.

## Classification
Track Micro/Macro Precision, Recall, F1, plus per-category metrics.

## Sentiment
Track accuracy, Macro F1, confusion matrix.

## Confidence
Evaluate calibration because confidence controls Qwen fallback.

## Routing
Measure ML acceptance, Qwen fallback, accepted-ML accuracy, final accuracy.

## Taxonomy
Evaluate coverage, fragmentation, overlap, stability, clarity, actionability.

## Anomalies
Prioritize alert precision and low false-positive rate.

## Recommendations
Evaluate grounding, correctness, specificity, realism, actionability.

## Promotion
Compare candidate vs production baseline on the same benchmark.

## Avoid
- arbitrary thresholds,
- benchmark leakage,
- cherry-picked examples,
- hidden regressions,
- unmeasured portfolio claims.
