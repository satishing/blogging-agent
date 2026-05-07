"""Entry point: re-exports the API factory and CLI runner.

The pyproject `blogging-agent` script and `uvicorn advanced.main:create_app`
both resolve their targets from this module. Implementation lives in
`advanced/api.py` and `advanced/cli.py`.
"""

from advanced.api import create_app
from advanced.cli import main

__all__ = ["create_app", "main"]


if __name__ == "__main__":
    main()
