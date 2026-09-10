# ReviewSignal AI — Analytics and Insight Pipeline
**Status:** Draft v1.1  
**Scope:** Turning classified reviews into metrics, anomalies, insights, and tracked actions.

## Documentation links
Read [`README.md`](README.md) for hierarchy and conflict rules. This workflow runs inside the pipeline owned by
[`ai-pipeline.md`](ai-pipeline.md), consumes classifications from
[`classification-pipeline.md`](classification-pipeline.md), writes the tables in
[`analysis-tables.md`](analysis-tables.md), and is scored by
[`taxonomy-insight-evaluation.md`](taxonomy-insight-evaluation.md).

## 1. Analytics Inputs
Use structured fields: rating, date, weekday, category, sentiment, confidence, taxonomy version.
Normal aggregations do not require an LLM.

## 2. Core Metrics
Review count, average rating, category frequency, negative/positive mention rate, rating by category, rolling trends, and period comparisons.

## 3. Anomaly Goal
Avoid naive rules such as `increase > 50% → alert`; low volume makes those noisy.

## 4. Anomaly Inputs
Current count, historical baseline, negative rate, total review volume, average rating, confidence, variance, and rolling history.

## 5. Statistical Strategy
Start simple and low-volume aware: rolling baselines, EWMA, count-based/Bayesian methods, and minimum-support rules. An anomaly advances only when statistical evidence + minimum support + acceptable classification confidence are present.

## 6. Evidence Packet
```json
{"category":"Wait Time","current_negative_mentions":5,"historical_baseline":1.4,"average_rating":2.6,"high_frequency_weekdays":["Friday","Saturday"],"representative_reviews":["..."],"owner_reply_context":["..."]}
```

## 7. Insight Output
```json
{"title":"Wait-time complaints increased","summary":"Negative wait-time mentions are above the recent baseline.","severity":"medium","evidence_summary":"5 mentions versus an expected baseline of 1.4.","recommended_actions":["Review staffing coverage during peak periods.","Measure average customer handling time."]}
```

## 8. Recommendation Rules
The model must separate observation from hypothesis, avoid causal claims, remain grounded in supplied evidence, avoid generic advice, and recommend specific operational actions.

## 9. Insight Lifecycle
States: `New`, `Monitoring`, `Resolved`. The system may propose transitions; the user can override them.

## 10. Action & Impact
Store action text/date/notes. Compare negative aspect rate, average rating, category frequency, and review volume before vs after. Report association, not causation.
