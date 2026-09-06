"""Check that every `<doc>.md §N` citation in the source resolves to a real section.

Code across this repository cites the documents in `docs/` by section number. Nothing
verified those numbers, and three separate reviews found citations pointing at sections
that had moved. This walks the source, attributes each `§N` to a document, and looks the
section up in that document's headings.

Two failure modes are hard errors: a section the document does not have, and a `§N` that
names no document at all. A citation to a document that is not on disk is skipped rather
than failed, because `docs/PRD.md` is gitignored and a clean checkout must still pass.
"""

import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

SOURCE_GLOBS = (
    "apps/api/**/*.py",
    "workers/**/*.py",
    "tests/**/*.py",
    "migrations/**/*.py",
    "tools/**/*.py",
)

# This linter's own test fixtures contain deliberately broken citations.
EXCLUDED = ("tests/tools/test_check_citations.py",)

_SECTION = re.compile(r"§(\d+(?:\.\d+)*)")
_DOCUMENT = re.compile(r"([A-Za-z0-9_-]+\.md)")
_PRD_SHORTHAND = re.compile(r"\bPRD\s*$")
# A wrapped citation leaves the document at the end of one line and the `§` at the
# start of the next. Anything looser is a different sentence about a different
# document, and inheriting from it would validate the claim against the wrong doc.
_WRAPPED_DOCUMENT = re.compile(r"([A-Za-z0-9_-]+\.md)[`)\s]*$")
# `docs/PRD.md` writes headings as `# **10\\. Title**`; the others as `## 16. Title`.
_HEADING = re.compile(r"^#{1,6}\s+\*{0,2}(\d+(?:\.\d+)*)\\?\.?\s+(.+?)\s*$")
# A citation may name a numbered rule inside a section, as in `api-spec.md` §16.5.
_LIST_ITEM = re.compile(r"^(\d+)\.\s+(.+?)\s*$")


# Section number -> title, for each document filename under `docs/`.
Documents = dict[str, dict[str, str]]


@dataclass(frozen=True)
class Citation:
    line: int
    section: str
    document: str | None
    path: str = ""

    def __str__(self) -> str:
        return f"{self.path}:{self.line} {self.document or '<no document>'} §{self.section}"


@dataclass
class Report:
    ok: list[Citation] = field(default_factory=list)
    broken: list[Citation] = field(default_factory=list)
    skipped: list[Citation] = field(default_factory=list)
    unattributed: list[Citation] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.ok) + len(self.broken) + len(self.skipped) + len(self.unattributed)

    @property
    def failed(self) -> bool:
        return bool(self.broken or self.unattributed)


def _document_in(text: str) -> str | None:
    """The last document named in `text`, as a bare filename."""
    named = _DOCUMENT.findall(text)
    return named[-1] if named else None


def parse_citations(text: str) -> list[Citation]:
    """Find every `§N` and attribute it to the document it belongs to.

    A document is looked for before the `§` on the same line, then as the bare `PRD`
    shorthand, then on the line immediately above — but only in the shape the formatter
    produces when it wraps a citation: the document ends that line and the `§` opens this
    one. A document merely mentioned nearby does not count, because attributing to the
    wrong document is worse than not attributing at all — the section resolves, so the
    report prints a heading that supports nothing and no one is warned.
    """
    lines = text.splitlines()
    citations: list[Citation] = []
    for number, line in enumerate(lines, start=1):
        for match in _SECTION.finditer(line):
            before = line[: match.start()]
            document = _document_in(before)
            if document is None and _PRD_SHORTHAND.search(before):
                document = "PRD.md"
            if document is None and number >= 2 and not before.strip():
                wrapped = _WRAPPED_DOCUMENT.search(lines[number - 2])
                document = wrapped.group(1) if wrapped else None
            citations.append(Citation(line=number, section=match.group(1), document=document))
    return citations


def section_titles(markdown: str) -> dict[str, str]:
    """Map section number to title.

    Numbered headings become `"16"`. Numbered list items inside a section become
    `"16.5"`, because the citations treat a rule inside a section as a subsection.
    """
    titles: dict[str, str] = {}
    section = ""  # the numbered heading currently open; "" before the first one
    for line in markdown.splitlines():
        heading = _HEADING.match(line)
        if heading:
            section = heading.group(1)
            titles[section] = heading.group(2).strip("*` ").strip()
            continue
        item = _LIST_ITEM.match(line)
        if item and section:
            titles[f"{section}.{item.group(1)}"] = item.group(2).strip("*` ").strip()
    return titles


def resolve(citations: list[Citation], documents: Documents) -> Report:
    """Sort citations into ok, broken, skipped and unattributed."""
    report = Report()
    for citation in citations:
        if citation.document is None:
            report.unattributed.append(citation)
        elif citation.document not in documents:
            report.skipped.append(citation)
        elif citation.section not in documents[citation.document]:
            report.broken.append(citation)
        else:
            report.ok.append(citation)
    return report


def check(root: Path) -> tuple[Report, Documents]:
    """Walk the source under `root` and resolve every citation against `docs/`.

    The parsed documents come back with the report because `--report` needs the
    heading titles, and reading `docs/` a second time to get them risks printing
    titles that disagree with the ones the report was built from.
    """
    documents = {
        path.name: section_titles(path.read_text(encoding="utf-8"))
        for path in sorted((root / "docs").glob("*.md"))
    }
    citations: list[Citation] = []
    for pattern in SOURCE_GLOBS:
        for path in sorted(root.glob(pattern)):
            relative = path.relative_to(root).as_posix()
            if "__pycache__" in path.parts or relative in EXCLUDED:
                continue
            for citation in parse_citations(path.read_text(encoding="utf-8")):
                citations.append(replace(citation, path=relative))
    return resolve(citations, documents), documents


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    report, documents = check(root)

    if "--report" in (argv if argv is not None else sys.argv[1:]):
        for citation in report.ok:
            title = documents[citation.document or ""][citation.section]
            print(f"{citation}  ->  {title!r}")
        for citation in report.skipped:
            print(f"{citation}  ->  skipped, {citation.document} not on disk")

    print(
        f"citations: {report.total} checked, {len(report.ok)} ok, "
        f"{len(report.skipped)} skipped, {len(report.broken)} broken, "
        f"{len(report.unattributed)} unattributed"
    )
    for citation in report.broken:
        print(f"  BROKEN       {citation}  -> no such section")
    for citation in report.unattributed:
        print(f"  UNATTRIBUTED {citation}  -> name the document, e.g. `data-model.md` §N")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
