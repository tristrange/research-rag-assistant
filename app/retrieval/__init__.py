"""Shared retrieval cutoffs; expanded contexts retain a separate character cap."""

DEFAULT_TOP_K = 3
EXPANDED_TOP_K = 6
CANDIDATE_COUNT = 10


def default_top_k(expanded: bool) -> int:
    return EXPANDED_TOP_K if expanded else DEFAULT_TOP_K
