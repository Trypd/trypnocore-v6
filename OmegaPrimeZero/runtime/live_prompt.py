"""Trinket suffix for a loaded chat. The system prefix stays put."""
from __future__ import annotations

import hashlib
import re

from runtime.memory import Proof
from runtime.trinkets.asyncactivity_trinket import AsyncActivityTrinket
from runtime.trinkets.composer import compose
from runtime.trinkets.domaindoc_trinket import DomainDocTrinket
from runtime.trinkets.email_trinket import EmailTrinket
from runtime.trinkets.forage_trinket import ForageTrinket
from runtime.trinkets.live_context_compaction_trinket import LiveContextCompactionTrinket
from runtime.trinkets.location_trinket import LocationTrinket
from runtime.trinkets.lora_trinket import LoraTrinket
from runtime.trinkets.manifest_trinket import ManifestTrinket
from runtime.trinkets.memory_curator_trinket import MemoryCuratorTrinket
from runtime.trinkets.peanutgallery_trinket import PeanutGalleryTrinket
from runtime.trinkets.proactive_memory_trinket import ProactiveMemoryTrinket
from runtime.trinkets.reminder_manager import ReminderManager
from runtime.trinkets.time_manager import TimeManager
from runtime.trinkets.whilethecatsaway_trinket import WhileTheCatsAwayTrinket

TRINKET_MARK = "[trinket "
_REMEMBER = re.compile(r"^\s*remember\b[:\s,-]*(.*)$", re.IGNORECASE | re.DOTALL)
_REMIND = re.compile(r"^\s*remind\s+me\b[:\s,-]*(.*)$", re.IGNORECASE | re.DOTALL)
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "that", "this", "what", "remember", "remind", "and", "for", "with", "you", "your",
}


def is_trinket_message(message: dict) -> bool:
    content = message.get("content")
    return (
        message.get("role") == "user"
        and isinstance(content, str)
        and content.startswith(TRINKET_MARK)
    )


def roster() -> list:
    return [
        TimeManager(),
        ProactiveMemoryTrinket(),
        MemoryCuratorTrinket(),
        ReminderManager(),
        LiveContextCompactionTrinket(),
        LocationTrinket(),
        ForageTrinket(),
        EmailTrinket(),
        AsyncActivityTrinket(),
        WhileTheCatsAwayTrinket(),
        PeanutGalleryTrinket(),
        LoraTrinket(),
        ManifestTrinket(),
        DomainDocTrinket(),
    ]


def live_sections(ctx: dict) -> list[str]:
    trinkets = roster()
    sections = []
    for trinket, text in zip(trinkets, compose(trinkets, ctx)):
        if text:
            sections.append(f"{TRINKET_MARK}{trinket.section}]\n{text}")
    return sections


def _words(text: str) -> set[str]:
    return {word for word in _WORD.findall(text.lower()) if len(word) > 2 and word not in _STOP}


def choose_memories(claims_in_order: list[str], text: str, limit: int = 5, pool: str = "") -> list[str]:
    """Rank atoms for injection. Semantic cosine dominates when the embedder
    is up (EmbeddingGemma-2, disk-cached per pool); lexical overlap is the
    fallback and a tiebreaker. Recency breaks remaining ties. Not a search.
    """
    memories = [claim for claim in claims_in_order if not claim.startswith("reminder: ")]
    if not memories:
        return []
    semantic: dict[str, float] | None = None
    if pool:
        try:
            from runtime.memory.embedder import rank
            semantic = rank(pool, memories, text)
        except Exception:
            semantic = None
    words = _words(text)
    total = max(len(memories) - 1, 1)

    def score(index: int, claim: str) -> float:
        recency = (index / total) * 0.5
        if semantic is not None:
            return semantic.get(claim, -1.0) * 4.0 + len(words & _words(claim)) * 0.5 + recency
        return len(words & _words(claim)) * 2.0 + recency

    ranked = sorted(
        ((score(index, claim), index, claim) for index, claim in enumerate(memories)),
        key=lambda row: (row[0], row[1]),
        reverse=True,
    )
    picked: list[str] = []
    floor = 0.0 if semantic is not None else 2.0
    for weighted, _index, claim in ranked:
        if weighted < floor or claim in picked:
            continue
        picked.append(claim)
        if len(picked) >= limit:
            break
    newest = memories[-1]
    if newest not in picked:
        if len(picked) >= limit:
            picked[-1] = newest
        else:
            picked.append(newest)
    return picked


def _store_pool(store) -> str:
    """pool-<name>.metta -> <name>; anything else -> no semantic cache key."""
    stem = getattr(getattr(store, "path", None), "stem", "") or ""
    return stem.removeprefix("pool-") if stem.startswith("pool-") else ""


def live_ctx(store, latest: str, now: str) -> dict:
    claims = store.claims()
    pool = _store_pool(store)
    reminders = [claim[len("reminder: "):] for claim in claims if claim.startswith("reminder: ")]
    return {
        "now": now,
        "memories": choose_memories(claims, latest, pool=pool),
        "reminders": reminders[-8:],
        "curator_status": f"metta atoms: {len(claims)}",
        "lora_loaded": False,
        "channels": {},
    }


def _strip_lead(body: str, prefixes: tuple[str, ...]) -> str:
    text = body.strip()
    lower = text.lower()
    for prefix in prefixes:
        if lower.startswith(prefix):
            return text[len(prefix):].strip()
    return text


def explicit_notes(text: str) -> list[Proof]:
    """An explicit remember or reminder. Ordinary chat is not an atom."""
    stripped = text.strip()
    reminder = _REMIND.match(stripped)
    if reminder:
        claim = _strip_lead(reminder.group(1), ("to ",))
        prefix = "reminder: "
    else:
        remembered = _REMEMBER.match(stripped)
        if not remembered:
            return []
        claim = _strip_lead(remembered.group(1), ("that ", "this "))
        prefix = ""
    if not claim or claim.startswith("saw:") or claim.startswith("heard:"):
        return []
    full = prefix + claim
    pointer = hashlib.sha256(full.encode("utf-8")).hexdigest()[:16]
    return [Proof(claim=full, pointer=pointer, evidence=stripped[:500])]


def insert_trinkets(messages: list[dict], sections: list[str]) -> list[dict]:
    blocks = [{"role": "user", "content": section} for section in sections if section]
    if not blocks:
        return list(messages)
    index = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user" and not is_trinket_message(messages[i]):
            index = i
            break
    if index is None:
        return [*messages, *blocks]
    return [*messages[:index], *blocks, *messages[index:]]


def _visible(history: list[dict]) -> list[dict]:
    visible = []
    for message in history:
        role = message.get("role")
        content = message.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            visible.append({"role": role, "content": content})
    return visible


def _same_prefix(saved: list[dict], client: list[dict]) -> bool:
    if len(client) < len(saved):
        return False
    return all(
        saved[i]["role"] == client[i]["role"] and saved[i]["content"] == client[i]["content"]
        for i in range(len(saved))
    )


def reconcile(client: list[dict], saved: list[dict]) -> list[dict]:
    """Keep frozen trinket lines in place when the page drops them."""
    client_visible = _visible(client)
    if not saved:
        return client_visible
    if _same_prefix(saved, client_visible):
        return client_visible
    saved_plain = [(m["role"], m["content"]) for m in saved if not is_trinket_message(m)]
    client_plain = [(m["role"], m["content"]) for m in client_visible if not is_trinket_message(m)]
    if client_plain[:len(saved_plain)] == saved_plain:
        tail = [{"role": role, "content": content} for role, content in client_plain[len(saved_plain):]]
        return [*saved, *tail]
    if (
        client_visible
        and client_visible[-1]["role"] == "user"
        and not is_trinket_message(client_visible[-1])
        and (not saved or saved[-1]["content"] != client_visible[-1]["content"])
    ):
        return [*saved, client_visible[-1]]
    return list(saved)
