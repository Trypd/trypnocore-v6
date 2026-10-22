"""Atom gate. Production refuses unless OmegaClaw is configured.

The in-memory double is for tests. It is not MeTTa and it is not SQL.
"""
from __future__ import annotations

from dataclasses import dataclass


class MemoryError(RuntimeError):
    pass


class Hole(MemoryError):
    """A failed query. Not a license to invent an atom."""


@dataclass(frozen=True)
class Proof:
    claim: str
    pointer: str
    evidence: str


@dataclass(frozen=True)
class Atom:
    proof: Proof


class MemoryDouble:
    """Explicit test double. Not a store beside MeTTa."""

    def __init__(self) -> None:
        self.phase = "awake"
        self.atoms: list[Atom] = []

    def count(self) -> int:
        return len(self.atoms)

    def exists(self, pointer: str) -> bool:
        return any(
            atom.proof.pointer == pointer or atom.proof.claim == pointer for atom in self.atoms
        )

    def assert_atom(self, proof: Proof) -> None:
        if self.phase not in {"deep_sleep", "explicit_remember"}:
            raise MemoryError("atom written outside deep sleep or explicit remember")
        claim = proof.claim.strip()
        if claim.startswith("saw:") or claim.startswith("heard:"):
            raise MemoryError("a raw sensory line is not an atom")
        if not proof.pointer or not proof.evidence or not proof.claim:
            raise MemoryError("no proof, no write")
        self.atoms.append(Atom(proof))

    def query(self, _expression: str) -> None:
        raise Hole("failed query is a hole")

    def remember(self, proof: Proof) -> None:
        previous = self.phase
        self.phase = "explicit_remember"
        try:
            self.assert_atom(proof)
        finally:
            self.phase = previous


class OmegaClawWriter:
    """Production writer. Refuses to fake MeTTa until a space is passed in."""

    def __init__(self, space=None) -> None:
        self._space = space

    def assert_atom(self, proof: Proof) -> None:
        if self._space is None:
            raise MemoryError("OmegaClaw is not configured. Refusing to invent atoms.")
        self._space.assert_atom(proof)

    def remember(self, proof: Proof) -> None:
        if self._space is None:
            raise MemoryError("OmegaClaw is not configured. Refusing to invent atoms.")
        self._space.remember(proof)
