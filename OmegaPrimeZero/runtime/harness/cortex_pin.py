"""One executive. Extra minds are refused."""
from __future__ import annotations

from dataclasses import dataclass

from runtime.paths import MIND_ID


@dataclass(frozen=True)
class Actor:
    name: str
    model_id: str
    can_think: bool = False
    has_boot: bool = False
    has_soul: bool = False


class PinError(RuntimeError):
    pass


def pin(actors: list[Actor]) -> Actor:
    minds = [actor for actor in actors if actor.can_think or actor.has_boot or actor.has_soul]
    if len(minds) != 1:
        raise PinError("one executive")
    mind = minds[0]
    if mind.model_id != MIND_ID or not mind.can_think:
        raise PinError("the executive is the 8B")
    return mind
