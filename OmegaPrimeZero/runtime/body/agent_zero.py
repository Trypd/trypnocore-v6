"""Hands. A tool context is not a mind."""
from __future__ import annotations


class ToolError(RuntimeError):
    pass


def tool_context(task: str, boot: str = "") -> dict:
    if boot and boot in task:
        raise ToolError("tool context must not contain the boot")
    if task.startswith("think:"):
        raise ToolError("a tool does not write think:")
    return {"task": task, "boot": "", "answers_as_person": False}
