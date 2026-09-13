"""The shape a taxonomy generation reply must take (`docs/taxonomy-pipeline.md` §4).

Two fixed levels rather than open recursion. `taxonomy-pipeline.md` §4 models a node as a
parent holding children, and a self-referencing Pydantic model produces a JSON Schema
with a recursive `$ref` that constrained decoding cannot reliably honour. Depth is a
product decision either way: a third level gets added here deliberately, rather than
arriving because a model felt like nesting.

Descriptions are required, not optional, because `taxonomy-pipeline.md` §4 makes
classification depend on semantic meaning rather than on label names alone.
"""

from pydantic import BaseModel, Field


class GeneratedSubcategory(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class GeneratedCategory(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    children: list[GeneratedSubcategory] = Field(default_factory=list)


class GeneratedTaxonomy(BaseModel):
    """`min_length=1` because an empty taxonomy is a failed run, not a result."""

    nodes: list[GeneratedCategory] = Field(min_length=1)
