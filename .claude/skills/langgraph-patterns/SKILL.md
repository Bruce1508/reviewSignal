---
name: langgraph-patterns
description: LangGraph patterns for ReviewSignal taxonomy generation, review/refinement, state graphs, conditional edges, structured outputs, retries, and Ollama/Qwen workflows.
allowed-tools: Read, Grep, Glob
---
# LangGraph Patterns

Use LangGraph for stateful branching/looping workflows, especially taxonomy generation/update/review/refinement.

Do not use it for simple deterministic functions.

## State
Keep state explicit, typed, and serializable where practical.

## Nodes
Each node should:
- perform one meaningful step,
- have clear typed input/output,
- avoid hidden globals,
- return structured data.

## Loops
Every loop is bounded by success or max iterations.

## Structured Output
Schema-validate all production LLM node outputs.
Retry parse failures before DLQ.

## Model Role
Qwen performs semantic reasoning.
Normal code computes numeric trends.

## Evidence
Classification returns concise source spans.
Insight nodes receive structured evidence packets.
Never store hidden chain-of-thought.

## Prompt Versioning
Use stable IDs like `taxonomy_generate_v1`.

## Avoid
- unbounded loops,
- giant graph nodes,
- free-form output when schema exists,
- LLM calls for deterministic calculations,
- taxonomy activation without versioning.
