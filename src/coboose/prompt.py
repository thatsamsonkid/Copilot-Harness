from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TextIO


@dataclass
class PromptSession:
    """Interactive stdin prompts. Writes questions to stderr so JSON stdout stays clean."""

    stdin: TextIO | None = None
    stderr: TextIO | None = None
    interactive: bool | None = None

    def __post_init__(self) -> None:
        if self.stdin is None:
            self.stdin = sys.stdin
        if self.stderr is None:
            self.stderr = sys.stderr
        if self.interactive is None:
            self.interactive = bool(getattr(self.stdin, "isatty", lambda: False)())

    def can_prompt(self) -> bool:
        return bool(self.interactive)

    def write(self, message: str) -> None:
        assert self.stderr is not None
        self.stderr.write(message)
        self.stderr.flush()

    def ask(self, message: str, default: str | None = None) -> str:
        suffix = f" [{default}]" if default else ""
        self.write(f"{message}{suffix}: ")
        assert self.stdin is not None
        line = self.stdin.readline()
        if line == "":
            raise EOFError("No more input")
        value = line.strip()
        if not value and default is not None:
            return default
        return value

    def confirm(self, message: str, default: bool = True) -> bool:
        hint = "Y/n" if default else "y/N"
        answer = self.ask(f"{message} [{hint}]", default="")
        if not answer:
            return default
        return answer.lower() in {"y", "yes", "true", "1"}
