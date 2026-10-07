"""Shared retrieval cutoffs; expanded contexts retain a separate character cap."""

DEFAULT_TOP_K = 3
VERIFIED_TOP_K = 6
EXPANDED_TOP_K = 6
CANDIDATE_COUNT = 10
VERIFIED_CANDIDATE_COUNT = 20


def default_top_k(expanded: bool, *, verified: bool = False) -> int:
    if expanded:
        return EXPANDED_TOP_K
    return VERIFIED_TOP_K if verified else DEFAULT_TOP_K
