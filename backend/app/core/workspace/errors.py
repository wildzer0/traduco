"""Errors raised by workspace operations; ``code`` maps to the API error format."""

from __future__ import annotations


class WorkspaceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
