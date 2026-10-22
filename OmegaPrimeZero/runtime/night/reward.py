"""Checkable reward. Does not launch training."""
from __future__ import annotations

from pathlib import Path

from runtime.memory import MemoryDouble
from runtime.paths import AUDIO_ID, MIND_ID, VL_ID


class HardFail(RuntimeError):
    pass


def score(rollout: dict, store: MemoryDouble) -> float:
    if rollout.get("boot_changed_outside_markers"):
        raise HardFail("discard the update")
    total = 0.0
    missed = False
    for cited in rollout.get("cited_atoms", []):
        if store.exists(cited):
            total += 1
        else:
            total -= 1
            missed = True
    if rollout.get("plan_present"):
        total += 1
    if rollout.get("audio_text") == rollout.get("utterance"):
        total += 1
    else:
        total -= 1
    if rollout.get("patch_ok"):
        total += 1
    if rollout.get("operator_kept"):
        total += 1
    if rollout.get("saw_asserted") or rollout.get("heard_asserted") or rollout.get("atom_before_deep"):
        total -= 1
    if missed:
        return min(total, -1.0)
    return total


def load_night_config(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"')
    trainable = data.get("trainable", "")
    if trainable not in {MIND_ID, f"lora:{MIND_ID}"}:
        raise HardFail("trainable set must be the 8B or its LoRA")
    if data.get("launch_from_tests", "false") != "false":
        raise HardFail("tests must not launch training")
    frozen = data.get("frozen", "")
    if VL_ID not in frozen or "Audio-1.5B" not in frozen:
        raise HardFail("slaves stay frozen")
    if AUDIO_ID.split("/")[-1] not in frozen and "Audio-1.5B" not in frozen:
        raise HardFail("audio slave stays frozen")
    return data
