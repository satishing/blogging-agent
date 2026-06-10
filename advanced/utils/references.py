"""Canonical References rendering + inline-citation validation (readability A6).

The writer drafts a References section and inline [n] citations, but the source
list is overridden deterministically by SourceService after generation. To keep
the rendered references in lockstep with the *actual* sources, we rebuild the
References section ourselves from `blog.sources` and report any inline citation
that points at a source index we don't have.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from advanced.models import ResearchSource

_CITATION_RE = re.compile(r"\[(\d+)\]")
# Matches a '## References' (or 'Sources') heading at the start of a line.
_REFERENCES_HEADING_RE = re.compile(r"(?im)^##\s+(references|sources)\s*$")


def cited_indices(markdown: str) -> list[int]:
    """Return every inline [n] citation index, in order of appearance."""
    return [int(match) for match in _CITATION_RE.findall(markdown)]


def render_references(sources: Sequence[ResearchSource]) -> str:
    """Render a numbered '## References' markdown section from sources."""
    lines = ["## References", ""]
    for index, source in enumerate(sources, start=1):
        title = (source.title or "Source").strip()
        lines.append(f"{index}. [{title}]({source.url})")
    return "\n".join(lines)


def _strip_references_section(markdown: str) -> str:
    """Remove an existing trailing References/Sources section, if present."""
    match = _REFERENCES_HEADING_RE.search(markdown)
    if match:
        return markdown[: match.start()].rstrip() + "\n"
    return markdown.rstrip() + "\n"


def finalize_references(
    markdown: str, sources: Sequence[ResearchSource]
) -> tuple[str, list[int]]:
    """Replace the references section with a canonical one built from sources.

    Returns the rewritten markdown and a sorted list of *dangling* citation
    indices — those referenced inline but outside ``1..len(sources)``. The body
    is preserved verbatim except for the swapped references section, so it can
    never drop below the content-length floor.
    """
    body = _strip_references_section(markdown)
    dangling = sorted(
        {index for index in cited_indices(body) if index < 1 or index > len(sources)}
    )
    final = body
    if sources:
        final = f"{body}\n{render_references(sources)}\n"
    return final, dangling
