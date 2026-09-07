"""Unit tests for the doc-citation linter.

Pure string tests: no filesystem, no repository walk, except the one integration
case at the end that asserts the real tree is clean.
"""

from pathlib import Path

from tools.check_citations import check, parse_citations, resolve, section_titles

# --- Rule 1: a section number is attributed to the document nearest before it ---


def test_a_backticked_path_on_the_same_line_attributes_the_citation() -> None:
    (citation,) = parse_citations("Runs a benchmark (`docs/evaluation.md` §35).")

    assert citation.document == "evaluation.md"
    assert citation.section == "35"
    assert citation.line == 1


def test_a_path_without_backticks_still_attributes() -> None:
    (citation,) = parse_citations("`evaluation_runs` (data-model.md §16) needs these.")

    assert citation.document == "data-model.md"
    assert citation.section == "16"


def test_a_comma_continuation_inherits_the_document() -> None:
    first, second = parse_citations("The contract (`docs/evaluation.md` §2, §3).")

    assert (first.document, first.section) == ("evaluation.md", "2")
    assert (second.document, second.section) == ("evaluation.md", "3")


def test_the_prd_shorthand_resolves_without_a_file_extension() -> None:
    (citation,) = parse_citations("PRD §10 puts the harness in Phase 0.")

    assert citation.document == "PRD.md"
    assert citation.section == "10"


def test_a_citation_wrapped_onto_the_next_line_inherits_the_document() -> None:
    text = "Synchronous by design, because (`docs/PRD.md`\n§11 requires queued work)."

    (citation,) = parse_citations(text)

    assert citation.document == "PRD.md"
    assert citation.line == 2


def test_a_document_mentioned_in_a_different_sentence_does_not_leak_downward() -> None:
    """The one-line lookback exists for a citation the formatter wrapped, not for any
    document mentioned nearby. Attributing to the wrong document is worse than failing:
    the section resolves, so the report shows a heading that supports nothing."""
    text = (
        "Field naming follows `docs/data-model.md` for the review schema.\n"
        "Multi-label scoring in this module follows §5's averaging rule.\n"
    )

    (citation,) = parse_citations(text)

    assert citation.section == "5"
    assert citation.document is None


def test_a_document_named_further_back_than_one_line_does_not_attribute() -> None:
    """Guessing across a whole docstring would silently mis-attribute; failing loudly
    forces the citation to name its own document."""
    text = "One review (`docs/data-model.md` §4).\n\nfiller\nfiller\nwhich §19 requires.\n"

    citations = parse_citations(text)

    assert citations[1].section == "19"
    assert citations[1].document is None


def test_a_dotted_section_number_is_kept_whole() -> None:
    (citation,) = parse_citations("Trends complete (`docs/PRD.md` §3.1).")

    assert citation.section == "3.1"


# --- Rule 2: headings are read as numbered sections ---------------------------


def test_a_numbered_heading_yields_its_title() -> None:
    assert section_titles("## 16. `evaluation_runs`") == {"16": "evaluation_runs"}


def test_a_bold_dotted_heading_yields_its_title() -> None:
    assert section_titles("## **3.1 Goals**") == {"3.1": "Goals"}


def test_a_bold_top_level_heading_with_an_escaped_period_is_read() -> None:
    """`docs/PRD.md` writes its sections as `# **10\\. Title**`."""
    titles = section_titles(r"# **10\. MVP Scope & Phased Rollout**")

    assert titles == {"10": "MVP Scope & Phased Rollout"}


def test_a_numbered_list_item_becomes_a_sub_section() -> None:
    """A citation like `api-spec.md` §16.5 means rule 5 inside section 16, which is a
    list item rather than a heading of its own."""
    markdown = (
        "## 16. Design Rules\n"
        "1. Keep business logic out of route handlers.\n"
        "5. Never return secrets.\n"
    )

    titles = section_titles(markdown)

    assert titles["16"] == "Design Rules"
    assert titles["16.5"] == "Never return secrets."


def test_unnumbered_headings_are_ignored() -> None:
    markdown = "# ReviewSignal AI\n## Documentation links\n## 5. Multi-Label Metrics\n"

    assert section_titles(markdown) == {"5": "Multi-Label Metrics"}


# --- Rule 3: each citation lands in exactly one bucket ------------------------

DOCS = {"evaluation.md": {"5": "Multi-Label Metrics"}}


def test_a_citation_matching_a_real_section_is_ok() -> None:
    report = resolve(parse_citations("(`evaluation.md` §5)"), DOCS)

    assert [c.section for c in report.ok] == ["5"]
    assert not report.broken


def test_a_section_the_document_does_not_have_is_broken() -> None:
    report = resolve(parse_citations("(`evaluation.md` §99)"), DOCS)

    assert [c.section for c in report.broken] == ["99"]


def test_a_document_that_is_not_on_disk_is_skipped_not_failed() -> None:
    """`docs/PRD.md` is gitignored, so a clean checkout must still pass."""
    report = resolve(parse_citations("(`PRD.md` §3.1)"), DOCS)

    assert [c.section for c in report.skipped] == ["3.1"]
    assert not report.broken


def test_an_unattributed_citation_is_reported_separately() -> None:
    report = resolve(parse_citations("which §19 requires"), DOCS)

    assert [c.section for c in report.unattributed] == ["19"]


def test_a_report_fails_on_broken_or_unattributed_only() -> None:
    assert resolve(parse_citations("(`evaluation.md` §5)"), DOCS).failed is False
    assert resolve(parse_citations("(`evaluation.md` §99)"), DOCS).failed is True
    assert resolve(parse_citations("which §19 requires"), DOCS).failed is True
    assert resolve(parse_citations("(`PRD.md` §1)"), DOCS).failed is False


# --- Rule 4: the repository itself is clean ----------------------------------


def test_every_citation_in_the_repository_resolves() -> None:
    report, documents = check(Path(__file__).resolve().parents[2])

    # `resolve` files a citation whose document is missing under `skipped`, and `failed`
    # ignores `skipped`. So an unreadable `docs/` leaves every assertion below true while
    # nothing was checked at all: proven by running `check` on a tree with no `docs/`,
    # which reported 162 skipped, 0 broken, and exited 0. These two lines pin that shut.
    assert "evaluation.md" in documents, "docs/ did not parse; every citation would skip"
    assert len(report.ok) > 100, "almost nothing resolved; check the file globs"
    assert report.broken == [], f"broken citations: {report.broken}"
    assert report.unattributed == [], f"unattributed citations: {report.unattributed}"
