"""Writing task — production version of demo/04_content_writer_agent.ipynb.

Carries the bulk of the "readable blog" spec: required structure, length band,
voice, inline citations, and markdown hygiene. A guardrail enforces the
measurable parts (length, structure, citations) and feeds failures back to the
writer for a bounded number of retries.
"""

from __future__ import annotations

import re

from crewai import Agent, Task

from advanced.utils import get_logger

logger = get_logger(__name__)

# Headings that must be present (case-insensitive) for the post to read as a
# complete article rather than a wall of text.
_REQUIRED_SECTIONS = ("key takeaways", "conclusion", "references")
_MIN_BODY_SECTIONS = 3


def build_writing_task(
    agent: Agent, *, min_words: int, max_words: int, min_sources: int
) -> Task:
    return Task(
        description=(
            "Write a complete, publication-ready technical blog on '{topic}' for AI "
            "engineers and advanced learners. Follow the outline produced in the "
            "previous step and draw ONLY on the research JSON below — never invent "
            "facts, numbers, or sources.\n\n"
            "Requirements:\n"
            f"- Length: {min_words}-{max_words} words of body content.\n"
            "- Start with a 2-4 sentence hook that frames the problem (no H1 title "
            "in the body).\n"
            "- Add a '## Key takeaways' bulleted list near the top (3-5 bullets).\n"
            f"- Include {_MIN_BODY_SECTIONS}+ '##' content sections that build on "
            "each other; explain a term before you use it.\n"
            "- Include at least one concrete example or fenced code block (with a "
            "language tag) where it aids understanding.\n"
            "- Support non-obvious claims with inline citations like [1], [2] that "
            "refer to the numbered sources.\n"
            "- End with a '## Conclusion' and a '## References' section that lists "
            f"each of the {min_sources}+ sources as a numbered markdown link "
            "([Title](url)).\n"
            "- Voice: clear, direct, practical. Prefer short paragraphs and active "
            "voice. No marketing fluff.\n\n"
            "Research JSON (sources are 1-indexed in order):\n{research_json}"
        ),
        expected_output=(
            f"A {min_words}-{max_words} word markdown blog: hook intro, "
            "'## Key takeaways' list, 3+ '##' sections with examples/code, "
            "'## Conclusion', and a '## References' section of numbered markdown "
            "links. Non-obvious claims carry inline [n] citations."
        ),
        agent=agent,
        guardrail=_build_readability_guardrail(
            min_words=min_words, max_words=max_words
        ),
        guardrail_max_retries=2,
    )


def _build_readability_guardrail(*, min_words: int, max_words: int):
    """Return a guardrail enforcing length, structure, and citation presence.

    CrewAI guardrails return `(ok, payload)`: on success the payload is the
    original output (passed downstream); on failure it's a feedback string the
    agent uses to revise. We only check deterministic, measurable properties
    here — subjective quality is left to the editor agent.
    """

    def guardrail(output):
        text = getattr(output, "raw", str(output))
        word_count = len(text.split())
        if word_count < min_words:
            return (
                False,
                f"Draft is too short ({word_count} words). Expand to "
                f"{min_words}-{max_words} words with more depth and examples.",
            )
        if word_count > max_words:
            return (
                False,
                f"Draft is too long ({word_count} words). Tighten to "
                f"{min_words}-{max_words} words; cut repetition, keep substance.",
            )

        lowered = text.lower()
        missing = [name for name in _REQUIRED_SECTIONS if f"## {name}" not in lowered]
        if missing:
            pretty = ", ".join(f"'## {name.title()}'" for name in missing)
            return (
                False,
                f"Missing required section(s): {pretty}. Add them as '##' headings.",
            )

        section_count = len(re.findall(r"(?m)^##\s+\S", text))
        # Body sections beyond the three required structural ones.
        if section_count - len(_REQUIRED_SECTIONS) < _MIN_BODY_SECTIONS:
            return (
                False,
                f"Add at least {_MIN_BODY_SECTIONS} '##' content sections in "
                "addition to Key takeaways, Conclusion, and References.",
            )

        if not re.search(r"\[\d+\]", text):
            return (
                False,
                "No inline citations found. Cite non-obvious claims with [1], [2], "
                "matching the numbered References.",
            )

        logger.info("Writing guardrail passed (%s words).", word_count)
        return (True, output)

    return guardrail
