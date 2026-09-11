"""Local embeddings for clustering only. No API cost, no network at runtime
(model is downloaded once and cached)."""

from __future__ import annotations

import logging

import numpy as np

from ..models import Article

logger = logging.getLogger("argus.cluster.embed")

_MODEL_NAME = "minishlab/potion-base-8M"
_model = None


def _get_model():
    global _model
    if _model is None:
        from model2vec import StaticModel

        logger.info("loading embedding model %s", _MODEL_NAME)
        _model = StaticModel.from_pretrained(_MODEL_NAME)
    return _model


def embed_articles(articles: list[Article]) -> np.ndarray:
    """Returns an (n_articles, dim) float32 array. Embeds title + summary."""
    if not articles:
        return np.zeros((0, 1), dtype=np.float32)

    texts = [f"{a.title}\n{a.summary}".strip() for a in articles]
    model = _get_model()
    vectors = model.encode(texts)
    return np.asarray(vectors, dtype=np.float32)
