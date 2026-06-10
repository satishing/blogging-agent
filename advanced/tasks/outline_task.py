"""Outline task — plan structure before drafting (readability lever A3)."""

from crewai import Agent, Task


def build_outline_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Plan a technical educational blog on '{topic}' for AI engineers and "
            "advanced learners, using ONLY the research JSON below.\n\n"
            "Produce a structured outline — not prose:\n"
            "1. A working title (<= 70 chars) that is specific and not clickbait.\n"
            "2. A one-sentence thesis stating what the reader will be able to do "
            "after reading.\n"
            "3. 4-6 sections in logical order. For each: a '##' heading and 1-3 "
            "bullets describing what it covers and which source(s) support it, "
            "referenced by their index in the research list as [1], [2], ...\n"
            "4. A note of which sections should include a concrete example or code.\n\n"
            "Do not invent facts the sources do not support. Every section must map "
            "to at least one source index.\n\n"
            "Research JSON (sources are 1-indexed in order):\n{research_json}"
        ),
        expected_output=(
            "A markdown outline containing: a title line, a thesis line, and 4-6 "
            "'##' section headings each followed by bullets with [n] source "
            "references and an example/code note where relevant."
        ),
        agent=agent,
    )
