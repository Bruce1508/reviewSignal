---
name: database-patterns
description: PostgreSQL patterns for ReviewSignal AI. Use for tables, migrations, repositories, taxonomy versioning, analyses, insights, jobs, model runs, indexes, and transactions.
allowed-tools: Read, Grep, Glob
---
# Database Patterns

PostgreSQL is authoritative.

Preserve raw review payload, normalized fields, historical analyses, taxonomy versions, model/evaluation metadata.

## Versioning
Never overwrite taxonomy history destructively.

## Taxonomy Activation
Use one transaction:
1. create candidate,
2. insert nodes,
3. archive active,
4. activate candidate,
5. record changes.

Never allow two active versions.

## Reviews
Deduplicate by source review ID.
Daily sync must be idempotent.

## Repositories
Repositories own persistence; services own business rules.

## Migrations
Use Alembic. Never hand-edit production schema.

## Constraints
Prefer DB constraints for rating range, confidence range, uniqueness, and FK integrity.

## Avoid
- deleting old analyses after reclassification,
- secrets in settings table,
- chain-of-thought storage,
- routine reads from raw Google JSON,
- speculative multi-tenant columns.
