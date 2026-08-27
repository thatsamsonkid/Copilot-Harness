"""Copilot harness CLI for sibling repos, workspaces, and Jira Cloud."""

__version__ = "0.1.0"


class HarnessError(Exception):
    """User-facing failure with an exit code."""

    def __init__(self, message: str, code: int = 1, payload: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.payload = payload
