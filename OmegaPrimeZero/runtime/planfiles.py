"""Disk plans. Not copied onto the tape."""
from __future__ import annotations

from pathlib import Path

PLAN_FILES = ("task_plan.md", "findings.md", "progress.md")


def ensure_plan_files(project: Path, expected_tool_calls: int) -> None:
    if expected_tool_calls <= 5:
        return
    project.mkdir(parents=True, exist_ok=True)
    for name in PLAN_FILES:
        path = project / name
        if not path.exists():
            path.write_text(f"# {name}\n", encoding="utf-8")


class ToolSession:
    def __init__(self, project: Path, expected_tool_calls: int) -> None:
        self.project = project
        self.expected = expected_tool_calls
        self.calls = 0
        ensure_plan_files(project, expected_tool_calls)

    def call(self) -> int:
        self.calls += 1
        if self.expected > 5 and self.calls >= 3:
            missing = [name for name in PLAN_FILES if not (self.project / name).is_file()]
            if missing:
                raise FileNotFoundError(", ".join(missing))
        return self.calls
