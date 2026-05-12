"""Tests for the basic/ folder — both code_variant and yaml_variant.

These tests do not call the LLM or any external API. They only construct
the crew, inspect agent / task / tool wiring, and (for the publisher tool)
mock requests.post to verify the payload shape.
"""

import json

import pytest


@pytest.fixture(autouse=True)
def _basic_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("SERPER_API_KEY", "test")
    monkeypatch.setenv("DEVTO_API_KEY", "test")


_EXPECTED_AGENT_ROLES = ["Research Analyst", "Content Writer", "Editor", "Publisher"]


# ----- code_variant -----


def test_code_variant_creates_four_agents_with_expected_roles() -> None:
    from basic.code_variant.crew import BloggingCrew

    crew = BloggingCrew()
    roles = [
        crew.researcher().role,
        crew.writer().role,
        crew.editor().role,
        crew.publisher().role,
    ]
    assert roles == _EXPECTED_AGENT_ROLES


def test_code_variant_researcher_has_serper_tool() -> None:
    from basic.code_variant.crew import BloggingCrew

    crew = BloggingCrew()
    tool_names = [tool.name for tool in crew.researcher().tools]
    assert tool_names == ["Search the internet with Serper"]


def test_code_variant_publisher_has_devto_tool() -> None:
    from basic.code_variant.crew import BloggingCrew

    crew = BloggingCrew()
    tool_names = [tool.name for tool in crew.publisher().tools]
    assert tool_names == ["publish_to_devto"]


def test_code_variant_writer_and_editor_have_no_tools() -> None:
    from basic.code_variant.crew import BloggingCrew

    crew = BloggingCrew()
    assert not crew.writer().tools
    assert not crew.editor().tools


def test_code_variant_tasks_chain_through_context() -> None:
    from basic.code_variant.crew import BloggingCrew

    crew = BloggingCrew()
    # writing/editing/publishing each receive the previous task via context.
    # research is the head of the chain (no upstream task).
    assert len(crew.writing().context) == 1
    assert len(crew.editing().context) == 1
    assert len(crew.publishing().context) == 1
    # And the chain is wired correctly: editing reads from writing's agent's task,
    # publishing reads from editing's, etc.
    assert crew.writing().context[0].agent.role == "Research Analyst"
    assert crew.editing().context[0].agent.role == "Content Writer"
    assert crew.publishing().context[0].agent.role == "Editor"


def test_code_variant_search_tool_is_shared_across_agents() -> None:
    from basic.code_variant.crew import BloggingCrew

    # The fix that hoisted SerperDevTool() into __init__ means the
    # researcher should reference the same tool instance the crew owns.
    crew = BloggingCrew()
    assert crew.researcher().tools[0] is crew._search_tool


# ----- yaml_variant -----


def test_yaml_variant_creates_four_agents_from_yaml() -> None:
    from basic.yaml_variant.crew import BloggingCrew

    crew = BloggingCrew()
    roles = [
        crew.researcher().role,
        crew.writer().role,
        crew.editor().role,
        crew.publisher().role,
    ]
    assert roles == _EXPECTED_AGENT_ROLES


def test_yaml_variant_resolves_yaml_agent_refs_to_real_instances() -> None:
    from basic.yaml_variant.crew import BloggingCrew

    # `agent: writer` in tasks.yaml must resolve to the writer Agent.
    crew = BloggingCrew()
    assert crew.writing().agent.role == "Content Writer"
    assert crew.publishing().agent.role == "Publisher"


def test_yaml_variant_resolves_yaml_context_refs_to_real_tasks() -> None:
    from basic.yaml_variant.crew import BloggingCrew

    # `context: [research]` in tasks.yaml must resolve to the research Task.
    crew = BloggingCrew()
    assert len(crew.writing().context) == 1
    assert len(crew.publishing().context) == 1


# ----- equivalence -----


def test_both_variants_produce_equivalent_crews() -> None:
    from basic.code_variant.crew import BloggingCrew as CodeCrew
    from basic.yaml_variant.crew import BloggingCrew as YamlCrew

    code = CodeCrew()
    yaml_ = YamlCrew()

    code_roles = [
        code.researcher().role,
        code.writer().role,
        code.editor().role,
        code.publisher().role,
    ]
    yaml_roles = [
        yaml_.researcher().role,
        yaml_.writer().role,
        yaml_.editor().role,
        yaml_.publisher().role,
    ]
    assert code_roles == yaml_roles

    code_tools = [tool.name for tool in code.publisher().tools]
    yaml_tools = [tool.name for tool in yaml_.publisher().tools]
    assert code_tools == yaml_tools


# ----- DevToPublishTool -----


class _FakeDevtoResponse:
    def __init__(self) -> None:
        self.text = '{"id": 4242, "url": "https://dev.to/example/test"}'

    def raise_for_status(self) -> None:
        return None


def _capture_post(captured: dict):
    def _post(url, json, headers, timeout):
        captured.update(url=url, json=json, headers=headers, timeout=timeout)
        return _FakeDevtoResponse()

    return _post


def test_devto_publish_tool_posts_draft_with_correct_payload(monkeypatch) -> None:
    from basic.code_variant import tools as code_tools

    captured: dict = {}
    monkeypatch.setattr(code_tools.requests, "post", _capture_post(captured))

    article = {
        "title": "Test Title",
        "tags": ["ai", "test"],
        "content": "# Heading\n\nBody.",
    }
    result = code_tools.DevToPublishTool()._run(json.dumps(article))

    assert captured["url"] == "https://dev.to/api/articles"
    payload = captured["json"]["article"]
    assert payload["title"] == "Test Title"
    assert payload["body_markdown"] == "# Heading\n\nBody."
    assert payload["tags"] == ["ai", "test"]
    assert payload["published"] is False  # draft-first
    assert captured["headers"]["api-key"] == "test"
    assert "4242" in result


def test_devto_publish_tool_in_yaml_variant_is_identical(monkeypatch) -> None:
    # Both variants ship their own copy of tools.py — verify they behave the same.
    from basic.yaml_variant import tools as yaml_tools

    captured: dict = {}
    monkeypatch.setattr(yaml_tools.requests, "post", _capture_post(captured))

    article = {"title": "X", "tags": ["t"], "content": "body"}
    yaml_tools.DevToPublishTool()._run(json.dumps(article))

    assert captured["url"] == "https://dev.to/api/articles"
    assert captured["json"]["article"]["published"] is False
