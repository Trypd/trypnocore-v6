"""Optional semantic recall. Lexical fallback requires no model or GPU."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np

from sql_space import data_home

MODEL_ID = os.environ.get("OPZ_EMBED_MODEL", "").strip()
DEVICE = os.environ.get("OPZ_EMBED_DEVICE", "cpu").strip() or "cpu"
_model = None
_model_failed = False


def _load():
    global _model, _model_failed
    if not MODEL_ID or _model_failed:
        return None
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_ID, device=DEVICE)
    except Exception:
        _model_failed = True
        _model = None
    return _model


def _key(claim: str) -> str:
    return hashlib.sha256(claim.encode("utf-8")).hexdigest()[:16]


def _embed(texts: list[str]) -> np.ndarray:
    model = _load()
    return model.encode(texts, convert_to_numpy=True, normalize_embeddings=True).astype(np.float32)


def pool_vectors(pool: str, claims: list[str]):
    if _load() is None or not claims:
        return None
    path = data_home() / f"vec-{pool}.npz"
    cached = {}
    if path.is_file():
        try:
            blob = np.load(path)
            cached = {k: blob[k] for k in blob["keys"]}
        except Exception:
            cached = {}
    missing = [c for c in claims if _key(c) not in cached]
    if missing:
        vecs = _embed(missing)
        for claim, vec in zip(missing, vecs):
            cached[_key(claim)] = vec
        live = {_key(c) for c in claims}
        pruned = {k: v for k, v in cached.items() if k in live}
        np.savez_compressed(path, keys=np.array(list(pruned)), **pruned)
        cached = pruned
    return claims, np.stack([cached[_key(c)] for c in claims])


def rank(pool: str, claims: list[str], query: str) -> dict[str, float] | None:
    if not query.strip() or not MODEL_ID:
        return None
    got = pool_vectors(pool, claims)
    if got is None:
        return None
    ordered, matrix = got
    q = _embed([query])[0]
    return {claim: float(score) for claim, score in zip(ordered, matrix @ q)}
