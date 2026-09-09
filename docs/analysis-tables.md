# ReviewSignal AI — Analysis and Insight Tables
**Status:** Draft v1.1  
**Scope:** `review_analyses`, `review_aspects`, `anomalies`, `insights`, and `insight_actions`.

## Documentation links
Read [`README.md`](README.md) for hierarchy and conflict rules. These tables belong to the schema owned by
[`data-model.md`](data-model.md) and hold what the AI produced: they are written by
[`classification-pipeline.md`](classification-pipeline.md) and
[`insight-pipeline.md`](insight-pipeline.md), and read by
[`api-dashboard.md`](api-dashboard.md).

## 1. `review_analyses`
One analysis pass of one review under one taxonomy/model state.
```text
id UUID PK
review_id UUID FK
taxonomy_version_id UUID FK
model_run_id UUID FK
classifier_type VARCHAR
overall_confidence FLOAT NULL
created_at TIMESTAMPTZ
superseded_at TIMESTAMPTZ NULL
```
Classifier type: `llm`, `ml`, `hybrid`, `manual`. Keep previous analyses for auditability.

## 2. `review_aspects`
```text
id UUID PK
review_analysis_id UUID FK
taxonomy_node_id UUID FK
sentiment VARCHAR
confidence FLOAT
evidence_text TEXT
source VARCHAR
created_at TIMESTAMPTZ
```
Sentiment: `positive`, `neutral`, `negative`.
Indexes: `taxonomy_node_id`, `sentiment`, `review_analysis_id`.

## 3. `anomalies`
```text
id UUID PK
taxonomy_node_id UUID FK
taxonomy_version_id UUID FK
period_start DATE
period_end DATE
observed_value FLOAT
expected_value FLOAT
anomaly_score FLOAT
support_count INTEGER
status VARCHAR
method VARCHAR
metadata JSONB
created_at TIMESTAMPTZ
```
Statuses: `candidate`, `accepted`, `dismissed`, `resolved`.

## 4. `insights`
```text
id UUID PK
anomaly_id UUID NULL FK
taxonomy_node_id UUID NULL FK
title VARCHAR
summary TEXT
severity VARCHAR
evidence_summary TEXT
status VARCHAR
generated_by_model_run_id UUID NULL
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
resolved_at TIMESTAMPTZ NULL
manual_status_override BOOLEAN DEFAULT FALSE
```
Statuses: `new`, `monitoring`, `resolved`.

## 5. `insight_actions`
```text
id UUID PK
insight_id UUID FK
action_text TEXT
action_date DATE NULL
note_text TEXT NULL
status VARCHAR
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```
Statuses: `planned`, `in_progress`, `completed`, `cancelled`.
