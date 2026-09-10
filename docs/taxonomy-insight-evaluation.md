# ReviewSignal AI — Taxonomy and Insight Evaluation
**Status:** Draft v1.1  
**Scope:** How taxonomy quality, anomalies, insights, and recommendations are scored.

## Documentation links
Read [`README.md`](README.md) for hierarchy and conflict rules. These metrics score workflows owned by
[`ai-pipeline.md`](ai-pipeline.md) and share the benchmark, regression, and reporting
rules owned by [`evaluation.md`](evaluation.md), within the boundaries of
[`architecture.md`](architecture.md).

[`evaluation.md`](evaluation.md) scores the classifier — labels, sentiment, evidence, and
calibration. This document scores what the system builds on top of it, where the unit
under test is a taxonomy, an anomaly, or a recommendation rather than a label.

## 1. Taxonomy Dimensions
Evaluate coverage, overlap, fragmentation, stability, clarity, and actionability.

## 2. Coverage
Measure what percentage of reviews fit meaningful categories. Too many unmatched reviews indicate missing concepts; too many generic categories indicate poor specificity.

## 3. Fragmentation
Track category count, low-support categories, and median reviews per category. Too many tiny categories indicate over-fragmentation.

## 4. Overlap
Use human review plus semantic similarity between category descriptions as a signal. Similarity should trigger review, not automatic merging.

## 5. Stability
Run taxonomy generation on similar samples and compare semantic categories/hierarchy. Small sampling changes should not radically reshape the production taxonomy.

## 6. Actionability
Human rubric 1–5:
```text
1 = not useful
5 = directly actionable
```
Example: `Customer Experience` is vague; `Wait Time` is actionable.

## 7. Anomaly Evaluation
Measure alert precision, false-positive rate, support count, and human usefulness. For Maple Photo, precision matters more than alert volume.

## 8. Low-Volume Tests
Explicitly test scenarios like `1→3 complaints`, `0→2`, steady low count, single spike, and gradual increase. Percentage change alone must not dominate alerts.

## 9. Insight Evaluation
Score 1–5 on evidence grounding, correctness, specificity, clarity, and business usefulness.

## 10. Recommendation Evaluation
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

## 11. Hallucination Check
Fail recommendations that invent staff counts, operational facts, unsupported causation, unseen data, or claims contradicting evidence. Target zero unsupported factual claims.
