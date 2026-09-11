"""Deterministic clustering: embedding similarity within a rolling time window.

LLMs label/explain stories later (synthesize/); they never decide membership.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from ..models import Article, Cluster
from .embed import embed_articles

logger = logging.getLogger("argus.cluster.clustering")

# Cosine distance threshold below which two articles are considered the same
# story. Tuned conservatively (favors precision) -- v3 verified this merges
# real cross-source stories correctly; unchanged here.
DISTANCE_THRESHOLD = 0.35
MIN_SAMPLES_FOR_CLUSTERING = 2


def _most_representative_title(articles: list[Article], vectors: np.ndarray) -> str:
    if len(articles) == 1:
        return articles[0].title
    centroid = vectors.mean(axis=0, keepdims=True)
    norm_vectors = vectors / (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9)
    norm_centroid = centroid / (np.linalg.norm(centroid, axis=1, keepdims=True) + 1e-9)
    sims = (norm_vectors @ norm_centroid.T).ravel()
    best = int(np.argmax(sims))
    return articles[best].title


def cluster_articles(
    articles: list[Article],
    window_hours: int = 48,
    now: datetime | None = None,
    distance_threshold: float = DISTANCE_THRESHOLD,
) -> list[Cluster]:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=window_hours)

    windowed = [a for a in articles if a.published_at >= cutoff]
    dropped = len(articles) - len(windowed)
    if dropped:
        logger.info("cluster window dropped %d/%d articles (older than %dh)", dropped, len(articles), window_hours)

    if not windowed:
        return []

    if len(windowed) < MIN_SAMPLES_FOR_CLUSTERING:
        return [Cluster(articles=windowed, label=windowed[0].title, category=windowed[0].category_hint)]

    vectors = embed_articles(windowed)
    model = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        metric="cosine",
        linkage="average",
    )
    labels = model.fit_predict(vectors)

    groups: dict[int, list[int]] = {}
    for idx, lbl in enumerate(labels):
        groups.setdefault(int(lbl), []).append(idx)

    clusters: list[Cluster] = []
    for indices in groups.values():
        group_articles = [windowed[i] for i in indices]
        group_vectors = vectors[indices]
        categories = [a.category_hint for a in group_articles]
        category = max(set(categories), key=categories.count)
        clusters.append(
            Cluster(
                articles=group_articles,
                label=_most_representative_title(group_articles, group_vectors),
                category=category,
            )
        )

    logger.info("clustered %d articles into %d clusters", len(windowed), len(clusters))
    return clusters
