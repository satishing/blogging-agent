"""Entry point for the YAML-driven variant of the basic blogging crew.

Run from the repo root:
    uv run python -m basic.yaml_variant.main
"""

from dotenv import load_dotenv

from basic.yaml_variant.crew import BloggingCrew


def main() -> None:
    load_dotenv()

    topic = "AI agents in 2026"
    result = BloggingCrew().crew().kickoff(inputs={"topic": topic})

    print("\n=== PUBLISH RESPONSE ===\n")
    print(getattr(result, "raw", str(result)))


if __name__ == "__main__":
    main()
