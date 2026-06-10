import pytest
from pydantic import ValidationError

from advanced.models import BlogDraft, ResearchSource
from advanced.models.blog import MIN_CONTENT_WORDS
from advanced.utils import cited_indices, finalize_references, render_references


def _source(idx: int) -> ResearchSource:
    return ResearchSource(
        title=f"Source {idx}",
        url=f"https://example.com/{idx}",
        evidence="Evidence text about the topic from a credible source.",
    )


# --- A5: word-count backstop --------------------------------------------------


def _blog_with_content(content: str) -> BlogDraft:
    return BlogDraft(
        topic="AI Agents",
        title="AI Agents: A practical guide",
        summary="A practical guide for AI learners building production systems today.",
        content_markdown=content,
        tags=["ai"],
        estimated_read_minutes=6,
        sources=[_source(1)],
    )


def test_blogdraft_rejects_below_word_floor() -> None:
    # 600 chars (passes the char min_length) but only 1 word — must fail the
    # word-count backstop.
    with pytest.raises(ValidationError):
        _blog_with_content("x" * 600)


def test_blogdraft_accepts_at_or_above_word_floor() -> None:
    blog = _blog_with_content("word " * MIN_CONTENT_WORDS)
    assert len(blog.content_markdown.split()) == MIN_CONTENT_WORDS


# --- A6: references finalization ---------------------------------------------


def test_render_references_numbers_sources_as_links() -> None:
    rendered = render_references([_source(1), _source(2)])
    assert rendered.startswith("## References")
    assert "1. [Source 1](https://example.com/1)" in rendered
    assert "2. [Source 2](https://example.com/2)" in rendered


def test_cited_indices_extracts_in_order() -> None:
    assert cited_indices("text [2] more [1] and [2] again") == [2, 1, 2]


def test_finalize_replaces_existing_references_section() -> None:
    markdown = (
        "Intro with a claim [1].\n\n## Body\nMore text [2].\n\n"
        "## References\n1. [old stale link](https://stale.example/x)\n"
    )
    final, dangling = finalize_references(markdown, [_source(1), _source(2)])

    assert dangling == []
    # The stale reference is gone; canonical ones from sources are present.
    assert "stale.example" not in final
    assert final.count("## References") == 1
    assert "1. [Source 1](https://example.com/1)" in final
    # Body content is preserved.
    assert "## Body" in final and "More text [2]." in final


def test_finalize_appends_references_when_missing() -> None:
    markdown = "Just a body with a citation [1] and no references heading.\n"
    final, dangling = finalize_references(markdown, [_source(1)])

    assert dangling == []
    assert "## References" in final
    assert final.strip().endswith("1. [Source 1](https://example.com/1)")


def test_finalize_flags_dangling_citations() -> None:
    markdown = "Claim [1] and an unsupported claim [3].\n"
    final, dangling = finalize_references(markdown, [_source(1), _source(2)])

    # [3] has no matching source (only 2 provided).
    assert dangling == [3]
    assert "## References" in final
