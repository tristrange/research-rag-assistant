"""Deterministic evidence selection, approved-claim assembly and rendering."""

from __future__ import annotations

import re

from app.grounding_models import (
    MAX_QUOTE_CHARS,
    GroundedClaim,
    GroundedDraft,
    VerificationResult,
    VerifierEvidence,
)
from app.ingestion.chunking import _SENTENCE_END, _is_abbreviation_period
from app.types import AnswerClaim, ChunkData, EvidenceQuote


def build_verifier_evidence(
    claims: list[GroundedClaim],
    sources: list[ChunkData],
) -> list[VerifierEvidence]:
    """Give each cited source span one ID and retain its eligible claim indexes."""
    claims_by_source: dict[int, list[int]] = {}
    for claim_index, claim in enumerate(claims, start=1):
        seen_sources: set[int] = set()
        for citation in claim.citations:
            source_id = citation.source_id
            if source_id > len(sources):
                raise ValueError("citation source ID is outside the source catalogue")
            if source_id in seen_sources:
                continue
            seen_sources.add(source_id)
            claims_by_source.setdefault(source_id, []).append(claim_index)
    catalogue: list[VerifierEvidence] = []
    for source_id in sorted(claims_by_source):
        for quote in _evidence_spans(sources[source_id - 1]["text"]):
            catalogue.append(
                {
                    "evidence_id": len(catalogue) + 1,
                    "claim_indexes": claims_by_source[source_id],
                    "source_id": source_id,
                    "quote": quote,
                }
            )
    return catalogue


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


_POSSIBLE_SENTENCE_START = re.compile(r"\s+[\"'“‘(]*[A-Z][a-z]")


def _evidence_spans(text: str) -> list[str]:
    """Extract deterministic quote choices after the validator's normalization."""
    normalized = _normalize_whitespace(text)
    if not normalized:
        return []
    spans: list[str] = []
    seen: set[str] = set()
    boundaries: list[int] = []
    possible_boundaries: list[int] = []
    for match in _SENTENCE_END.finditer(normalized):
        if not _is_abbreviation_period(normalized, match):
            boundaries.append(match.end())
            possible_boundaries.append(match.end())
        elif _POSSIBLE_SENTENCE_START.match(normalized, match.end()):
            possible_boundaries.append(match.end())
    # ponytail: title-case continuations are ambiguous; offer both quote choices.
    for ends in (boundaries, possible_boundaries):
        start = 0
        for end in [*ends, len(normalized)]:
            sentence = normalized[start:end].strip()
            start = end
            for offset in range(0, len(sentence), MAX_QUOTE_CHARS):
                span = sentence[offset : offset + MAX_QUOTE_CHARS]
                if span and span not in seen:
                    seen.add(span)
                    spans.append(span)
    return spans


def _assemble_citation_context(
    citations: list[EvidenceQuote], sources: list[ChunkData]
) -> list[EvidenceQuote]:
    """Show all text between selected quotes so experiment boundaries stay visible."""
    by_source: dict[int, list[str]] = {}
    for citation in citations:
        by_source.setdefault(citation["source_index"], []).append(citation["quote"])
    assembled: list[EvidenceQuote] = []
    for source_index, quotes in by_source.items():
        text = _normalize_whitespace(sources[source_index]["text"])
        if len(quotes) == 1:
            context = quotes[0]
        else:
            positions = [text.find(quote) for quote in quotes]
            if any(
                start < 0 or text.find(quote, start + 1) != -1
                for quote, start in zip(quotes, positions)
            ):
                raise ValueError(
                    "selected quotes do not identify unambiguous source context"
                )
            start = min(positions)
            end = max(start + len(quote) for quote, start in zip(quotes, positions))
            if end - start > MAX_QUOTE_CHARS:
                raise ValueError(
                    "selected quote context exceeds the quote limit; select a smaller evidence span"
                )
            context = text[start:end]
        assembled.append({"source_index": source_index, "quote": context})
    return assembled


def _record_accepted_evidence(
    draft: GroundedDraft,
    sources: list[ChunkData],
    feedback: list[dict[str, object]],
    claim_evidence: list[AnswerClaim] | None,
) -> None:
    """Assemble source-bound context around the final verifier's selections."""
    if claim_evidence is None:
        return
    verification = VerificationResult.model_validate(feedback[0]["output"])
    catalogue = {
        entry["evidence_id"]: entry
        for entry in build_verifier_evidence(draft.claims, sources)
    }
    verdicts = {verdict.claim_index: verdict for verdict in verification.verdicts}
    for index, claim in enumerate(draft.claims, start=1):
        claim_evidence.append(
            {
                "text": claim.text,
                "attribution": claim.attribution,
                "citations": _assemble_citation_context(
                    [
                        {
                            "source_index": catalogue[evidence_id]["source_id"] - 1,
                            "quote": catalogue[evidence_id]["quote"],
                        }
                        for evidence_id in verdicts[index].supporting_evidence_ids
                    ],
                    sources,
                ),
            }
        )


def _render_claims(claims: list[AnswerClaim], sources: list[ChunkData]) -> str:
    rendered: list[str] = []
    labels = {
        "this_document_authors": "",
        "external_publication": "Cited literature: ",
        "non_study_context": "Context: ",
    }
    for claim in claims:
        locations: list[str] = []
        for citation in claim["citations"]:
            source = sources[citation["source_index"]]
            location = f"{source['document']}, page {source['page']}"
            if location not in locations:
                locations.append(location)
        rendered.append(
            f"{labels[claim['attribution']]}{claim['text']} ({'; '.join(locations)})"
        )
    return "\n".join(rendered)
