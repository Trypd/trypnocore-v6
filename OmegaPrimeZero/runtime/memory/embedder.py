"""Semantic recall for the MeTTa pools via EmbeddingGemma-2.

Lazy-loads google/embeddinggemma-2 once per process (CUDA if present), embeds
pool claims, and caches vectors on disk next to the pool files
(out/metta/vec-<pool>.npz). The cache keys on sha256(claim), so pool edits,
reimports, and roster refreshes only ever embed the delta.

rank(claims, query) returns {claim: cosine} or None when the model is
unavailable — callers must keep the lexical path as fallback.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np

MODEL_ID = os.environ.get("OPZ_EMBED_MODEL", "google/embeddinggemma-2")
VEC_DIR = Path(__file__).resolve().parent.parent.parent / "out" / "metta"

_model = None
_model_failed = False


def _load():
    global _model, _model_failed
    if _model is not None or _model_failed:
        return _model
    try:
        import torch
        from sentence_transformers import SentenceTransformer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        _model = SentenceTransformer(MODEL_ID, device=device)
    except Exception:
        _model_failed = True
        _model = None
    return _model


def _key(claim: str) -> str:
    return hashlib.sha256(claim.encode("utf-8")).hexdigest()[:16]


def _cache_path(pool: str) -> Path:
    return VEC_DIR / f"vec-{pool}.npz"


def _embed(texts: list[str]) -> np.ndarray:
    model = _load()
    vecs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return vecs.astype(np.float32)


def pool_vectors(pool: str, claims: list[str]) -> tuple[list[str], np.ndarray] | None:
    """Embeddings for every claim, disk-cached; None if the model can't load."""
    if _load() is None or not claims:
        return None
    path = _cache_path(pool)
    cached: dict[str, np.ndarray] = {}
    if path.is_file():
        try:
            blob = np.load(path)
            keys = blob["keys"]
            cached = {k: blob[k] for k in keys}
        except Exception:
            cached = {}
    missing = [c for c in claims if _key(c) not in cached]
    if missing:
        vecs = _embed(missing)
        for claim, vec in zip(missing, vecs):
            cached[_key(claim)] = vec
        VEC_DIR.mkdir(parents=True, exist_ok=True)
        live = {_key(c) for c in claims}
        pruned = {k: v for k, v in cached.items() if k in live}
        np.savez_compressed(path, keys=np.array(list(pruned)), **pruned)
        cached = pruned
    matrix = np.stack([cached[_key(c)] for c in claims])
    return claims, matrix


def rank(pool: str, claims: list[str], query: str) -> dict[str, float] | None:
    """Cosine similarity per claim (vectors are L2-normalized). None = fallback."""
    if not query.strip():
        return None
    got = pool_vectors(pool, claims)
    if got is None:
        return None
    ordered, matrix = got
    q = _embed([query])[0]
    sims = matrix @ q
    return {claim: float(score) for claim, score in zip(ordered, sims)}
