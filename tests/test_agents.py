from crewai import LLM

from advanced.agents import (
    build_editor_agent,
    build_publisher_agent,
    build_research_agent,
    build_writer_agent,
)
from advanced.config.settings import Settings
from advanced.services import CacheService, PublishingService
from advanced.tools import DevToPublisherTool, SerperSearchTool


def _test_llm() -> LLM:
    return LLM(model="openai/gpt-4o", base_url="https://openrouter.ai/api/v1", api_key="test")


def _test_settings(tmp_path) -> Settings:
    return Settings(
        OPENROUTER_API_KEY="test",
        SERPER_API_KEY="test",
        DEVTO_API_KEY="test",
        cache_backend="file",
        data_dir=str(tmp_path / "data"),
        cache_dir=str(tmp_path / "data" / "cache"),
        output_dir=str(tmp_path / "data" / "outputs"),
        log_dir=str(tmp_path / "data" / "logs"),
    )


def test_agent_factories_create_expected_roles(tmp_path) -> None:
    llm = _test_llm()
    settings = _test_settings(tmp_path)
    research_tool = SerperSearchTool(settings=settings)
    cache = CacheService(settings=settings)
    publishing = PublishingService(settings=settings, cache_service=cache)
    publish_tool = DevToPublisherTool(publishing_service=publishing)

    research = build_research_agent(llm, research_tool)
    writer = build_writer_agent(llm)
    editor = build_editor_agent(llm)
    publisher = build_publisher_agent(llm, publish_tool)

    assert "Research" in research.role
    assert "Writer" in writer.role
    assert "Editor" in editor.role
    assert "Publisher" in publisher.role
    assert len(research.tools) == 1
    assert len(publisher.tools) == 1
