"""Entry point: build the crew and run it on a topic.

Run from the repo root:
    uv run python -m basic.code_variant.main
"""

from dotenv import load_dotenv

from basic.code_variant.crew import BloggingCrew


def main() -> None:
    load_dotenv()

    topic = "AI agents in 2026"
    result = BloggingCrew().crew().kickoff(inputs={"topic": topic})

    print("\n=== PUBLISH RESPONSE ===\n")
    print(getattr(result, "raw", str(result)))


if __name__ == "__main__":
    main()
