"""Prompt text and the version every run records (`docs/ai-pipeline.md` §35).

Prompts are constants inside the repository rather than files beside it:
`model_runs.prompt_version` has to name exactly the text that ran, and a file outside
version control can change with no commit recording that it did. A changed prompt is a
new `_v2` constant, never an edit to `_v1` — editing one in place silently rewrites the
history every earlier run is attributed to.

The id is the version. `ai-pipeline.md` §35's own examples carry it in the name
(`taxonomy_generate_v1`), so a separate version field would be a second place to
disagree with the first.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    id: str
    template: str

    def render(self, **values: str) -> str:
        return self.template.format(**values)


TAXONOMY_GENERATE_V1 = Prompt(
    id="taxonomy_generate_v1",
    template="""You are building a review analysis taxonomy for a photo imaging business.

Read the customer reviews below and produce a two-level taxonomy of the topics they
actually discuss.

Rules:
- Derive every category from these reviews. Do not add categories the reviews do not support.
- Keep categories distinct. Merge any two that would overlap in meaning.
- Give every category and subcategory one sentence describing what belongs in it.
- Prefer a few meaningful categories over many narrow ones.
- Add a subcategory only where the reviews genuinely distinguish one.

Reviews:
{reviews}""",
)
