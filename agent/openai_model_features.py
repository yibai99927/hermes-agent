"""Model-family helpers for OpenAI-compatible routing decisions."""

from __future__ import annotations

from typing import Set


def _model_name_candidates(model: str | None) -> Set[str]:
    normalized = (model or "").strip().lower()
    if not normalized:
        return set()

    candidates = {normalized}
    if "/" in normalized:
        _, bare = normalized.split("/", 1)
        candidates.add(bare)
    return candidates


def is_gpt54_family_model(model: str | None) -> bool:
    """Return True for current GPT-5.4 family model IDs.

    Matches both bare IDs (``gpt-5.4``) and provider-prefixed IDs
    (``openai/gpt-5.4``), plus current hyphenated variants such as
    ``gpt-5.4-mini``, ``gpt-5.4-nano``, ``gpt-5.4-pro``, and similar future
    ``gpt-5.4-*`` slugs.
    """

    return any(
        candidate == "gpt-5.4" or candidate.startswith("gpt-5.4-")
        for candidate in _model_name_candidates(model)
    )
