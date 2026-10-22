"""MeTTa atom space. Hyperon is the interpreter. An unconfigured writer still refuses.

Pools: an agent's memory is slaved to its identity, not its model or provider.
`MettaSpace.for_pool(directory, pool)` gives each bootstrap identity its own
file (pool-<name>.metta) so a model swap never moves or orphans memory.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path
from hyperon import E, MeTTa, S, V, ValueAtom

_gate = importlib.import_module("runtime.memory.assert")
Hole = _gate.Hole
MemoryError = _gate.MemoryError
Proof = _gate.Proof

POOL_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")

# hyperon-space's trie index panics (native abort, trie.rs:179) once a space
# holds ~342 atoms. Prune oldest-first well below that, on every write path.
MAX_ATOMS = 300


def check_pool(pool: str) -> str:
    pool = pool.strip().lower()
    if not POOL_RE.fullmatch(pool):
        raise ValueError(f"bad pool name: {pool!r}")
    return pool


def _ground(atom) -> str:
    if hasattr(atom, "get_object"):
        obj = atom.get_object()
        if hasattr(obj, "value"):
            return str(obj.value)
    return str(atom)


class MettaSpace:
    """One Hyperon space, persisted as MeTTa expressions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.phase = "awake"
        self._order: list[str] = []
        self._metta = MeTTa()
        self._load()

    @classmethod
    def for_pool(cls, directory: Path, pool: str) -> "MettaSpace":
        """The pool file for one bootstrap identity, inside a shared directory."""
        return cls(directory / f"pool-{check_pool(pool)}.metta")

    def count(self) -> int:
        return len(self.claims())

    def exists(self, pointer: str) -> bool:
        return any(pointer == p for _c, p, _e in self._match())

    def claims(self) -> list[str]:
        by_pointer = {pointer: claim for claim, pointer, _evidence in self._match()}
        ordered: list[str] = []
        seen: set[str] = set()
        for pointer in self._order:
            claim = by_pointer.get(pointer)
            if claim is not None and pointer not in seen:
                ordered.append(claim)
                seen.add(pointer)
        for pointer, claim in by_pointer.items():
            if pointer not in seen:
                ordered.append(claim)
                seen.add(pointer)
        return ordered

    def query(self, expression: str) -> list:
        try:
            pattern = self._metta.parse_single(expression)
            return list(self._metta.space().query(pattern))
        except Exception as exc:
            raise Hole(f"metta query failed: {exc}") from exc

    def assert_atom(self, proof: Proof) -> None:
        if self.phase not in {"deep_sleep", "explicit_remember"}:
            raise MemoryError("atom written outside deep sleep or explicit remember")
        claim = proof.claim.strip()
        if claim.startswith("saw:") or claim.startswith("heard:"):
            raise MemoryError("a raw sensory line is not an atom")
        if not proof.pointer or not proof.evidence or not claim:
            raise MemoryError("no proof, no write")
        if any(pointer == proof.pointer for _claim, pointer, _evidence in self._match()):
            return
        self._metta.space().add_atom(
            E(S("memory"), ValueAtom(claim), ValueAtom(proof.pointer), ValueAtom(proof.evidence))
        )
        self._order.append(proof.pointer)
        if len(self._order) > MAX_ATOMS:
            self._prune_oldest()
        self._persist()

    def _prune_oldest(self) -> None:
        """Drop oldest atoms down to MAX_ATOMS (rebuilds the space in place)."""
        keep = set(self._order[-MAX_ATOMS:])
        by_pointer = {pointer: (claim, evidence) for claim, pointer, evidence in self._match() if pointer in keep}
        self._metta = MeTTa()
        self._order = [pointer for pointer in self._order if pointer in by_pointer]
        for pointer in self._order:
            claim, evidence = by_pointer[pointer]
            self._metta.space().add_atom(
                E(S("memory"), ValueAtom(claim), ValueAtom(pointer), ValueAtom(evidence))
            )

    def remember(self, proof: Proof) -> None:
        previous = self.phase
        self.phase = "explicit_remember"
        try:
            self.assert_atom(proof)
        finally:
            self.phase = previous

    def _match(self) -> list[tuple[str, str, str]]:
        try:
            found = self._metta.space().query(E(S("memory"), V("c"), V("p"), V("e")))
        except Exception as exc:
            raise Hole(f"metta query failed: {exc}") from exc
        return [(_ground(row["c"]), _ground(row["p"]), _ground(row["e"])) for row in found]

    def _load(self) -> None:
        if not self.path.is_file():
            return
        text = self.path.read_text(encoding="utf-8")
        if not text.strip():
            return
        try:
            self._metta.run(text)
        except Exception as exc:
            raise MemoryError(f"metta store failed to load: {exc}") from exc
        self._order = []
        for atom in self._metta.space().get_atoms():
            children = atom.get_children() if hasattr(atom, "get_children") else None
            if not children or len(children) != 4 or str(children[0]) != "memory":
                continue
            self._order.append(_ground(children[2]))

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = [str(atom) for atom in self._metta.space().get_atoms()]
        text = ("\n".join(lines) + "\n") if lines else ""
        # Hyperon emits \'-style escapes MeTTa cannot parse back ("Invalid
        # escape sequence"). Drop the backslash off any escape the MeTTa
        # string reader does not accept (\n \t \r \" \\ are valid). Fixpoint
        # loop: \\' collapses to \' first, then to ' — a single pass leaves it.
        for _ in range(3):
            fixed = re.sub(r"\\([^ntr\"\\])", r"\1", text)
            if fixed == text:
                break
            text = fixed
        temporary = self.path.with_suffix(".metta.tmp")
        temporary.write_text(text, encoding="utf-8")
        # Windows AV/indexers briefly hold fresh files; a rename can race them.
        for attempt in range(5):
            try:
                temporary.replace(self.path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                import time as _time

                _time.sleep(0.1 * (attempt + 1))
