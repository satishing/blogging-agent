"""CLI entry point: generate-only / generate-and-publish / api commands."""

from __future__ import annotations

import argparse
import json

from advanced.config import get_settings
from advanced.runtime import run_pipeline
from advanced.utils import setup_logging


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Production blogging agent runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate-and-publish", help="Generate blog and publish as draft")
    generate.add_argument("--topic", required=True)
    generate.add_argument("--min-year", type=int, default=None)
    generate.add_argument("--force-refresh", action="store_true")

    generate_only = subparsers.add_parser("generate-only", help="Generate blog without publishing")
    generate_only.add_argument("--topic", required=True)
    generate_only.add_argument("--min-year", type=int, default=None)
    generate_only.add_argument("--force-refresh", action="store_true")

    api = subparsers.add_parser("api", help="Run FastAPI server")
    api.add_argument("--host", default="0.0.0.0")
    api.add_argument("--port", type=int, default=8000)

    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_level, f"{settings.log_dir}/app.log")

    if args.command == "api":
        import uvicorn

        uvicorn.run(
            "advanced.main:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=False,
        )
        return

    publish = args.command == "generate-and-publish"
    result = run_pipeline(
        topic=args.topic,
        publish=publish,
        force_refresh=args.force_refresh,
        min_year=args.min_year,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
