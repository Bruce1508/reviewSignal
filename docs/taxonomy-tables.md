# ReviewSignal AI — Taxonomy Tables
**Status:** Draft v1.1  
**Scope:** `taxonomy_versions`, `taxonomy_nodes`, and `taxonomy_changes`.

## Documentation links
Read [`README.md`](README.md) for hierarchy and conflict rules. These tables belong to the schema owned by
[`data-model.md`](data-model.md), are written by
[`taxonomy-pipeline.md`](taxonomy-pipeline.md), and carry the versioning rules
[`data-model.md`](data-model.md) §19 depends on.

## 1. `taxonomy_versions`
Immutable taxonomy version.
```text
id UUID PK
version_number INTEGER
status VARCHAR
created_by VARCHAR
parent_version_id UUID NULL
created_at TIMESTAMPTZ
activated_at TIMESTAMPTZ NULL
archived_at TIMESTAMPTZ NULL
generation_model_run_id UUID NULL
```
Statuses: `candidate`, `active`, `archived`, `failed`. Only one active version.

## 2. `taxonomy_nodes`
```text
id UUID PK
taxonomy_version_id UUID FK
parent_id UUID NULL FK
name VARCHAR
description TEXT
slug VARCHAR
depth INTEGER
sort_order INTEGER
created_at TIMESTAMPTZ
```
Constraint: `UNIQUE(taxonomy_version_id, slug)`.

## 3. `taxonomy_changes`
Audit log between versions.
```text
id UUID PK
from_version_id UUID
to_version_id UUID
change_type VARCHAR
source VARCHAR
old_node_ids JSONB
new_node_ids JSONB
description TEXT
created_at TIMESTAMPTZ
```
Types: `add`, `rename`, `merge`, `split`, `move`, `delete`, `rollback`.
