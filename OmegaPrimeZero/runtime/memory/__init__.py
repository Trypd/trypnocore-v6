import importlib

_gate = importlib.import_module("runtime.memory.assert")
Hole = _gate.Hole
MemoryDouble = _gate.MemoryDouble
MemoryError = _gate.MemoryError
OmegaClawWriter = _gate.OmegaClawWriter
Proof = _gate.Proof
