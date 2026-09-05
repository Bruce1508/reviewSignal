# ReviewSignal AI — AI Evaluation
**Status:** Draft v1.1  
**Goal:** Measure whether the AI is reliable and useful.

## Documentation links
Read [`README.md`](README.md) for hierarchy and conflict rules. Product intent is
owned by [`PRD.md`](PRD.md); evaluation covers the AI workflows in
[`ai-pipeline.md`](ai-pipeline.md), the records in [`data-model.md`](data-model.md),
the evaluation endpoints in [`api-spec.md`](api-spec.md), and production signals
from [`deployment.md`](deployment.md), within the boundaries of
[`architecture.md`](architecture.md).

## 1. Principle
Do not accept `"the output looks good"` as validation. Taxonomy, classification, sentiment, confidence, anomaly detection, and recommendations need measurable evaluation.

## 2. Human Benchmark
Create an initial manually reviewed benchmark of about 100 reviews. For each review label relevant taxonomy aspects and sentiment per aspect.
Benchmark files live at `data/benchmarks/<dataset_version>.json`, not in PostgreSQL: `data-model.md` §16 refers to a dataset by version string and defines no benchmark entity. An item may carry no aspects; rating-only reviews are valid ground truth.

## 3. Benchmark Versioning
Store dataset version, taxonomy version, labeling date, labeler, and notes. Never silently rewrite ground truth; create a new version.
A new version means a new file. Loading validates rather than coerces, so a malformed file fails the run instead of shrinking it.

## 4. Train vs Evaluation Data
Once enough labeled data exists, separate training, validation, and held-out benchmark data. With small data, use cross-validation carefully and document limitations.

## 5. Multi-Label Metrics
Primary:
```text
Micro Precision / Recall / F1
Macro Precision / Recall / F1
```
Macro F1 matters because rare categories should not disappear behind frequent ones.

## 6. Per-Category Metrics
Track precision, recall, and F1 per category to reveal weak categories or poor taxonomy descriptions.

## 7. Sentiment Evaluation
Use accuracy, Macro F1, and confusion matrix for aspect-level sentiment. Inspect mixed-sentiment, neutral-vs-positive, and subtle complaint errors.
Score sentiment only on categories present in both gold and prediction. A missed category is already counted by §5; scoring it again as a sentiment error would conflate finding an aspect with reading its tone. Macro F1 averages only sentiments the benchmark contains, while the confusion matrix always spans the full `data-model.md` §9 vocabulary so an absent label stays visible.

## 8. Evidence Quality
Manual rubric:
```text
2 = clearly supports prediction
1 = partially supports prediction
0 = irrelevant/incorrect
```
Evidence quality directly affects trust and reviewability.

## 9. Confidence Calibration
Because confidence controls LLM fallback, evaluate with Brier Score, Expected Calibration Error, and reliability curves.
Confidence belongs to a whole aspect, so a prediction counts as correct only when its category and its sentiment are both right. Empty reliability buckets are reported rather than dropped: a gap in the curve is a finding.

## 10. Routing Evaluation
Measure ML acceptance rate, LLM fallback rate, accuracy of accepted ML predictions, and final accuracy after fallback.

## 11. Threshold Selection
Do not choose a confidence threshold arbitrarily. Tune it on validation/benchmark data to balance quality, fallback rate, and latency.

## 12. Taxonomy Dimensions
Evaluate coverage, overlap, fragmentation, stability, clarity, and actionability.

## 13. Coverage
Measure what percentage of reviews fit meaningful categories. Too many unmatched reviews indicate missing concepts; too many generic categories indicate poor specificity.

## 14. Fragmentation
Track category count, low-support categories, and median reviews per category. Too many tiny categories indicate over-fragmentation.

## 15. Overlap
Use human review plus semantic similarity between category descriptions as a signal. Similarity should trigger review, not automatic merging.

## 16. Stability
Run taxonomy generation on similar samples and compare semantic categories/hierarchy. Small sampling changes should not radically reshape the production taxonomy.

## 17. Actionability
Human rubric 1–5:
```text
1 = not useful
5 = directly actionable
```
Example: `Customer Experience` is vague; `Wait Time` is actionable.

## 18. Anomaly Evaluation
Measure alert precision, false-positive rate, support count, and human usefulness. For Maple Photo, precision matters more than alert volume.

## 19. Low-Volume Tests
Explicitly test scenarios like `1→3 complaints`, `0→2`, steady low count, single spike, and gradual increase. Percentage change alone must not dominate alerts.

## 20. Insight Evaluation
Score 1–5 on evidence grounding, correctness, specificity, clarity, and business usefulness.

## 21. Recommendation Evaluation
Rubric:
```text
grounded
actionable
specific
realistic
non-redundant
safe
```
Judge usefulness, not writing style.

## 22. Hallucination Check
Fail recommendations that invent staff counts, operational facts, unsupported causation, unseen data, or claims contradicting evidence. Target zero unsupported factual claims.

## 23. Regression Testing
Every important model/prompt/taxonomy change reruns the benchmark against the current production baseline.

## 24. Model Promotion Gate
Promote only when required metrics pass, no critical regression appears, and structured-output reliability is acceptable. Exact numeric gates are set after baseline measurements exist.

## 25. Prompt Evaluation
Version prompts such as `classification_v1`, `classification_v2`. Compare F1, sentiment F1, parse success, and latency on the same benchmark.

## 26. Embedding Comparison
Compare BGE small/base and MiniLM using classification F1, latency, memory, and embedding size. Prefer the smallest model that meets quality needs.

## 27. LLM Comparison
If testing Qwen sizes, compare taxonomy quality, fallback classification accuracy, recommendation grounding, latency, and memory. Reasoning quality is prioritized but deployment practicality matters.

## 28. Production Quality Signals
Track average confidence, fallback rate, novelty rate, parse failure rate, model error rate, taxonomy rebuild frequency, and alert frequency.

## 29. Drift Signals
Possible indicators: falling classifier confidence, rising fallback rate, more unmatched reviews, increasing novelty, and category distribution change. These trigger investigation, not automatic conclusions.

## 30. Evaluation Run Record
Store evaluation type, dataset version, taxonomy version, model version, prompt version, metrics, timestamp, and notes.
A metric family the run could not measure is stored as null, never as zero: zero is a measurement and would pollute a baseline comparison under §23.

## 31. Manual Review Loop
Future UI:
```text
review → AI prediction → accept/correct
```
Reviewed corrections can become training/evaluation data after quality checks.

## 32. Initial Success Criteria
Before numeric thresholds are known, prove that:
1. taxonomy covers most reviews and is understandable,
2. classification is consistently useful,
3. mixed sentiment works,
4. uncertain cases route to Qwen,
5. alerts are mostly meaningful,
6. recommendations remain grounded.

## 33. Portfolio Reporting
Good claims:
```text
Evaluated on a manually labeled benchmark of 100 reviews.
Macro F1 improved from X to Y after calibration.
LLM fallback dropped by X% while preserving Y F1.
```
Only report real measured values.

## 34. Related Docs
- [`architecture.md`](architecture.md): system boundaries and non-goals.
- [`ai-pipeline.md`](ai-pipeline.md): workflows and model decisions being evaluated.
- [`data-model.md`](data-model.md): `evaluation_runs`, `model_runs`, and version references.
- [`api-spec.md`](api-spec.md): evaluation run and history endpoints.
- [`deployment.md`](deployment.md): production quality signals and operational constraints.

Implementation: `reviewsignal_api.ai.evaluation` (metrics, dataset loader, runner) with persistence in `repositories/evaluation_runs.py`. The runner scores anything satisfying its `Predictor` protocol, so the harness exists before the classifier it measures (PRD §10 puts them in different phases).

## 35. Summary
```text
Human Ground Truth
→ Evaluate
→ Analyze Errors
→ Improve Model/Prompt/Taxonomy
→ Re-evaluate
→ Promote if better
```
Evaluation is a core system component, not a final optional step.
