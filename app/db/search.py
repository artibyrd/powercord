"""Reusable search utilities for PostgreSQL trigram-based fuzzy matching.

This module provides composable query builders that leverage the ``pg_trgm``
extension to perform fuzzy search with similarity ranking.  The ``pg_trgm``
extension must be enabled via an Alembic migration before these utilities
can be used (see ``alembic/versions/a1b2c3d4e5f6_enable_pg_trgm.py``).

Usage example::

    from app.db.search import build_trigram_query

    stmt = select(MidiFile)
    stmt = build_trigram_query(stmt, [MidiFile.filename, MidiFile.tags], "metllica")
    results = session.exec(stmt).all()
"""

from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import InstrumentedAttribute
from sqlmodel.sql.expression import SelectOfScalar

# Default trigram similarity threshold — the PostgreSQL default is 0.3.
# Lowering this value returns more results with weaker matches;
# raising it filters more aggressively.
DEFAULT_SIMILARITY_THRESHOLD: float = 0.3


def build_trigram_query(
    stmt: SelectOfScalar,
    columns: list[InstrumentedAttribute],
    search_term: str,
    *,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    limit: int | None = None,
) -> SelectOfScalar:
    """Apply trigram fuzzy search filters and similarity-based ordering.

    Filters rows where **any** of the provided ``columns`` has a trigram
    similarity to ``search_term`` that meets or exceeds ``threshold``.
    Results are ordered by the highest similarity score across all
    columns (best match first).

    Args:
        stmt: An existing ``select()`` statement to augment.
        columns: One or more mapped string columns to search across.
        search_term: The user's search query.
        threshold: Minimum similarity score (0.0–1.0) for a row to be
            included.  Defaults to :data:`DEFAULT_SIMILARITY_THRESHOLD`.
        limit: Optional maximum number of results to return.

    Returns:
        The modified ``select()`` statement with filters, ordering, and
        optional limit applied.

    Raises:
        ValueError: If ``columns`` is empty.
    """
    if not columns:
        raise ValueError("At least one column must be provided for trigram search.")

    # Build per-column similarity expressions
    similarities = [func.similarity(col, search_term) for col in columns]

    # Filter: at least one column must meet the threshold
    conditions = [sim >= threshold for sim in similarities]
    stmt = stmt.where(or_(*conditions))

    # Order by the best similarity across all columns (descending)
    if len(similarities) == 1:
        best_similarity = similarities[0]
    else:
        best_similarity = func.greatest(*similarities)

    stmt = stmt.order_by(best_similarity.desc())

    if limit is not None:
        stmt = stmt.limit(limit)

    return stmt
