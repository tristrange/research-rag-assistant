"""Bounded, claim-level generation with deterministic evidence checks."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable

from app.grounding_durations import duration_fingerprint, validate_duration_evidence
from app.grounding_evidence import (
    _POSSIBLE_SENTENCE_START,
    _evidence_spans,
    _normalize_whitespace,
    _record_accepted_evidence,
    _render_claims,
    build_verifier_evidence,
)
from app.grounding_models import (
    _IDENTIFIER_TOKEN,
    DRAFT_SCHEMA,
    DRAFT_THINK,
    GROUNDING_CONTEXT_TOKENS,
    GROUNDING_CONTRACT_VERSION,
    GROUNDING_DRAFT_TIMEOUT_SECONDS,
    GROUNDING_MODEL,
    GROUNDING_OUTPUT_TOKENS,
    GROUNDING_SAMPLING,
    GROUNDING_VERIFIER_TIMEOUT_SECONDS,
    INSUFFICIENT_EVIDENCE,
    MAX_QUOTE_CHARS,
    PROOF_SCHEMA,
    VERIFIER_SCHEMA,
    VERIFIER_THINK,
    ApprovedProof,
    GroundedClaim,
    GroundedDraft,
    VerificationResult,
)
from app.grounding_prompts import (
    _DRAFT_INSTRUCTIONS,
    _PROOF_INSTRUCTIONS,
    _REPAIR_INSTRUCTIONS,
    _VERIFIER_INSTRUCTIONS,
    _bounded_draft_schema,
    _bounded_verifier_schema,
    build_draft_prompt,
    build_proof_prompt,
    build_repair_prompt,
    build_verifier_prompt,
)
from app.ingestion.chunking import (
    _ABBREVIATION_PERIOD,
    _SENTENCE_END,
)
from app.llm.ollama import generate_json
from app.types import AnswerClaim, ChunkData

_INLINE_CITATION = re.compile(
    r"\[|\]|\bpages?\b|\.pdf\b|\bpp?\.\s*\d+\b|\b(?:source|document|doc)\s*(?:#|no\.?|:)?\s*\d+\b",
    re.IGNORECASE,
)


def _is_reference_source(source: ChunkData) -> bool:
    section = _normalize_whitespace(source.get("section", "")).casefold()
    return section in {"reference", "references", "bibliography"}


def _validate_draft(draft: GroundedDraft, sources: list[ChunkData]) -> None:
    for claim in draft.claims:
        if not claim.text.strip():
            raise ValueError("claim text is empty")
        if _INLINE_CITATION.search(claim.text):
            raise ValueError("claim text contains an application-owned citation marker")
        for citation in claim.citations:
            if citation.source_id > len(sources):
                raise ValueError("citation source ID is outside the source catalogue")
            source = sources[citation.source_id - 1]
            if not _normalize_whitespace(source["text"]):
                raise ValueError("citation source is empty")
            if claim.attribution == "this_document_authors" and _is_reference_source(
                source
            ):
                raise ValueError("a current-study claim cites a reference entry")


def validate_verification_structure(
    question: str,
    result: VerificationResult,
    claims: list[GroundedClaim],
    sources: list[ChunkData],
) -> None:
    """Validate exact question/evidence bindings without requiring approval.

    Explicit unsupported coverage, rejected claims, and answers_question=false are
    complete negative verdicts and therefore pass this structural validation.
    """
    claim_count = len(claims)
    indexes = [verdict.claim_index for verdict in result.verdicts]
    if len(indexes) != claim_count or set(indexes) != set(range(1, claim_count + 1)):
        raise ValueError("verifier must return one unique verdict for each claim")

    evidence = build_verifier_evidence(claims, sources)
    evidence_by_id = {entry["evidence_id"]: entry for entry in evidence}

    def validate_evidence_ids(
        ids: list[int], *, claim_index: int | None = None
    ) -> None:
        if len(ids) != len(set(ids)):
            raise ValueError("supporting evidence IDs must be unique")
        for evidence_id in ids:
            entry = evidence_by_id.get(evidence_id)
            if entry is None:
                raise ValueError("verifier cited an unknown evidence ID")
            if claim_index is not None and claim_index not in entry["claim_indexes"]:
                raise ValueError(
                    "claim verdict cited evidence from a source it did not cite"
                )

    normalized_question = _normalize_whitespace(question)
    requested_answer = result.requested_answer
    if _normalize_whitespace(requested_answer.question_excerpt) != normalized_question:
        raise ValueError("requested_answer must quote the entire question")
    validate_evidence_ids(requested_answer.supporting_evidence_ids)
    for requirement in result.requirements:
        validate_evidence_ids(requirement.supporting_evidence_ids)

    for verdict in result.verdicts:
        validate_evidence_ids(
            verdict.supporting_evidence_ids,
            claim_index=verdict.claim_index,
        )


def _validate_question_identifiers(question: str, evidence_quotes: list[str]) -> None:
    """Require explicit alphanumeric question identifiers in displayed evidence.

    This is a necessary lexical condition, not proof of experiment identity.
    Acronyms, aliases and word-only qualifiers still need semantic verification.
    """
    identifiers = {
        match.group().casefold(): match.group()
        for match in _IDENTIFIER_TOKEN.finditer(question)
        if match.group().isascii()
        and match.group()[0].isalpha()
        and match.group().isalnum()
        and any(character.isdigit() for character in match.group())
    }
    observed = {
        match.group().casefold()
        for quote in evidence_quotes
        for match in _IDENTIFIER_TOKEN.finditer(quote)
    }
    missing = [
        label for identifier, label in identifiers.items() if identifier not in observed
    ]
    if missing:
        raise ValueError(
            f"approved evidence does not contain question identifier(s): {', '.join(missing)}. "
            "Select exact scope excerpts as well as result excerpts; question text, claims, "
            "metadata and unselected source context cannot supply the missing identifiers."
        )


def _validate_verification(
    question: str,
    result: VerificationResult,
    claims: list[GroundedClaim],
    sources: list[ChunkData],
) -> None:
    validate_verification_structure(question, result, claims, sources)
    if result.requested_answer.status != "supported":
        raise ValueError(
            "cited evidence does not establish an answer to the whole question"
        )
    if any(not requirement.supported for requirement in result.requirements):
        raise ValueError("cited evidence does not establish every question requirement")
    if not result.answers_question:
        raise ValueError("verified claims do not answer the question")
    if any(
        not (verdict.supported and verdict.correct_attribution and verdict.relevant)
        for verdict in result.verdicts
    ):
        raise ValueError("verifier rejected at least one claim")
    claim_evidence_ids = {
        evidence_id
        for verdict in result.verdicts
        for evidence_id in verdict.supporting_evidence_ids
    }
    if not set(result.requested_answer.supporting_evidence_ids).issubset(
        claim_evidence_ids
    ):
        raise ValueError(
            "whole-question coverage cites evidence absent from approved claims"
        )
    for requirement in result.requirements:
        if not set(requirement.supporting_evidence_ids).issubset(
            claim_evidence_ids,
        ):
            raise ValueError(
                "question requirement cites evidence absent from approved claims"
            )
    evidence_by_id = {
        entry["evidence_id"]: entry
        for entry in build_verifier_evidence(claims, sources)
    }
    failures: list[str] = []
    try:
        _validate_question_identifiers(
            question,
            [
                evidence_by_id[evidence_id]["quote"]
                for evidence_id in sorted(claim_evidence_ids)
            ],
        )
    except ValueError as error:
        failures.append(str(error))
    for verdict in result.verdicts:
        try:
            validate_duration_evidence(
                claims[verdict.claim_index - 1].text,
                [
                    evidence_by_id[evidence_id]["quote"]
                    for evidence_id in verdict.supporting_evidence_ids
                ],
            )
        except ValueError as error:
            failures.append(f"Claim {verdict.claim_index}: {error}")
    if failures:
        raise ValueError("\n".join(failures))


def generate_draft_json(
    prompt: str,
    schema: dict[str, object],
    *,
    repair: bool = False,
) -> dict[str, object]:
    """Draft normally; use the verifier's reasoning budget to correct rejected drafts."""
    return generate_json(
        prompt,
        schema,
        think=VERIFIER_THINK if repair else DRAFT_THINK,
        model=GROUNDING_MODEL,
        allow_json_fence=True,
        num_ctx=GROUNDING_CONTEXT_TOKENS,
        num_predict=GROUNDING_OUTPUT_TOKENS,
        sampling=GROUNDING_SAMPLING.options(),
        timeout_seconds=GROUNDING_VERIFIER_TIMEOUT_SECONDS
        if repair
        else GROUNDING_DRAFT_TIMEOUT_SECONDS,
    )


def generate_verification_json(
    prompt: str, schema: dict[str, object]
) -> dict[str, object]:
    """Use reasoning for semantic verification; drafting and judging stay separate."""
    return generate_json(
        prompt,
        schema,
        think=VERIFIER_THINK,
        model=GROUNDING_MODEL,
        allow_json_fence=True,
        num_ctx=GROUNDING_CONTEXT_TOKENS,
        num_predict=GROUNDING_OUTPUT_TOKENS,
        sampling=GROUNDING_SAMPLING.options(),
        timeout_seconds=GROUNDING_VERIFIER_TIMEOUT_SECONDS,
    )


def generate_approved_proof_json(
    question: str, evidence: list[AnswerClaim]
) -> dict[str, object]:
    """Check only the excerpts that would be displayed, without previous verdicts."""
    return generate_verification_json(build_proof_prompt(question, evidence), PROOF_SCHEMA)


def _verify_draft_with_feedback(
    question: str,
    draft: GroundedDraft,
    sources: list[ChunkData],
    *,
    verifier: Callable[[str, dict[str, object]], dict[str, object]] | None = None,
    trace: list[dict[str, object]] | None = None,
    verification_stage: str = "verification",
    rejection_stage: str = "rejected",
) -> tuple[bool, list[dict[str, object]]]:
    feedback: list[dict[str, object]] = []
    try:
        _validate_draft(draft, sources)
        if not draft.answerable:
            return False, feedback
        evidence_catalogue = build_verifier_evidence(draft.claims, sources)
        verification_data = (verifier or generate_verification_json)(
            build_verifier_prompt(question, draft.claims, sources),
            _bounded_verifier_schema(question, draft.claims, sources),
        )
        verification_entry: dict[str, object] = {
            "stage": verification_stage,
            "output": verification_data,
            "evidence_catalogue": evidence_catalogue,
        }
        feedback.append(verification_entry)
        if trace is not None:
            trace.append(verification_entry)
        verification = VerificationResult.model_validate(verification_data)
        _validate_verification(question, verification, draft.claims, sources)
        evidence: list[AnswerClaim] = []
        _record_accepted_evidence(draft, sources, feedback, evidence)
        proof_entry: dict[str, object] = {
            "stage": f"{verification_stage}_proof",
            "output": None,
        }
        feedback.append(proof_entry)
        if trace is not None:
            trace.append(proof_entry)
        proof_data = generate_approved_proof_json(question, evidence)
        proof_entry["output"] = proof_data
        proof = ApprovedProof.model_validate(proof_data)
        if not proof.supported:
            raise ValueError(
                f"approved excerpts do not establish the answer: {proof.reason}"
            )
        return True, feedback
    except ValueError as error:
        rejection_entry: dict[str, object] = {
            "stage": rejection_stage,
            "reason": str(error),
        }
        feedback.append(rejection_entry)
        if trace is not None:
            trace.append(rejection_entry)
        return False, feedback


def verify_draft(
    question: str,
    draft: GroundedDraft,
    sources: list[ChunkData],
    *,
    verifier: Callable[[str, dict[str, object]], dict[str, object]] | None = None,
    trace: list[dict[str, object]] | None = None,
) -> bool:
    """Check structure/evidence first, then require complete semantic approval.

    The same entry point permits live adversarial tests with fixed drafts.
    verifier overrides the full-context call; the isolated proof uses the normal
    verifier profile. Model transport failures propagate; invalid content fails closed.
    """
    accepted, _ = _verify_draft_with_feedback(
        question,
        draft,
        sources,
        verifier=verifier,
        trace=trace,
    )
    return accepted


def grounded_answer(
    question: str,
    sources: list[ChunkData],
    *,
    trace: list[dict[str, object]] | None = None,
    claim_evidence: list[AnswerClaim] | None = None,
) -> str:
    """Render only wholly approved claims; propagate model transport errors."""
    if claim_evidence is not None:
        claim_evidence.clear()
    approved_evidence: list[AnswerClaim] = (
        claim_evidence if claim_evidence is not None else []
    )
    if not sources or not any(_evidence_spans(source["text"]) for source in sources):
        return INSUFFICIENT_EVIDENCE
    draft_schema = _bounded_draft_schema(sources)
    draft_data: dict[str, object] | None = None
    feedback: list[dict[str, object]]
    try:
        draft_data = generate_draft_json(
            build_draft_prompt(question, sources), draft_schema
        )
        if trace is not None:
            trace.append({"stage": "draft", "output": draft_data})
        if draft_data.get("answerable") is False:
            return INSUFFICIENT_EVIDENCE
        draft = GroundedDraft.model_validate(draft_data)
    except ValueError as error:
        feedback = [{"stage": "rejected", "reason": str(error)}]
        if trace is not None:
            trace.extend(feedback)
    else:
        accepted, feedback = _verify_draft_with_feedback(
            question,
            draft,
            sources,
            trace=trace,
        )
        if accepted:
            _record_accepted_evidence(draft, sources, feedback, approved_evidence)
            return _render_claims(approved_evidence, sources)

    try:
        repair_data = generate_draft_json(
            build_repair_prompt(question, sources, draft_data, feedback),
            _bounded_draft_schema(sources),
            repair=True,
        )
    except ValueError as error:
        if trace is not None:
            trace.append({"stage": "repair_rejected", "reason": str(error)})
        return INSUFFICIENT_EVIDENCE
    if trace is not None:
        trace.append({"stage": "repair_draft", "output": repair_data})
    if repair_data.get("answerable") is False:
        return INSUFFICIENT_EVIDENCE
    try:
        repaired_draft = GroundedDraft.model_validate(repair_data)
    except ValueError as error:
        if trace is not None:
            trace.append({"stage": "repair_rejected", "reason": str(error)})
        return INSUFFICIENT_EVIDENCE
    accepted, feedback = _verify_draft_with_feedback(
        question,
        repaired_draft,
        sources,
        trace=trace,
        verification_stage="repair_verification",
        rejection_stage="repair_rejected",
    )
    if not accepted:
        return INSUFFICIENT_EVIDENCE
    _record_accepted_evidence(repaired_draft, sources, feedback, approved_evidence)
    return _render_claims(approved_evidence, sources)


def grounding_fingerprint() -> str:
    """Hash the prompts, schemas, and deterministic rendering contract."""
    contract = {
        "version": GROUNDING_CONTRACT_VERSION,
        "json_response_envelope": "Strict JSON object, optionally inside one whole-response lowercase json fence with LF delimiters; no content rewriting",
        "duration_guard_sha256": duration_fingerprint(),
        "question_identifier_pattern": _IDENTIFIER_TOKEN.pattern,
        "question_identifier_filter": "Scan maximal Unicode word tokens, then require ASCII, letter-leading, alphanumeric question tokens containing a digit",
        "question_identifier_guard": "Letter-leading contiguous ASCII alphanumeric question tokens containing a digit must occur as case-insensitive whole tokens in final approved claim quotes; lexical presence never replaces semantic proof",
        "deterministic_repair_feedback": "Collect missing question identifiers and every claim's duration failures before the single repair",
        "model": GROUNDING_MODEL,
        "context_tokens": GROUNDING_CONTEXT_TOKENS,
        "output_tokens": GROUNDING_OUTPUT_TOKENS,
        "draft_think": DRAFT_THINK,
        "verifier_think": VERIFIER_THINK,
        "repair_think": VERIFIER_THINK,
        "sampling": GROUNDING_SAMPLING.options(),
        "draft_timeout_seconds": GROUNDING_DRAFT_TIMEOUT_SECONDS,
        "verifier_timeout_seconds": GROUNDING_VERIFIER_TIMEOUT_SECONDS,
        "repair_timeout_seconds": GROUNDING_VERIFIER_TIMEOUT_SECONDS,
        "draft_instructions": _DRAFT_INSTRUCTIONS,
        "repair_instructions": _REPAIR_INSTRUCTIONS,
        "verifier_instructions": _VERIFIER_INSTRUCTIONS,
        "draft_schema": DRAFT_SCHEMA,
        "draft_prompt_schema": "Draft and repair serialize the same bounded response schema before untrusted input and send it to the API",
        "dynamic_citation_schema": (
            "ClaimCitation is anyOf one object per nonempty source; source_id is const, "
            "only source_id is required and additional fields including quotes are forbidden"
        ),
        "dynamic_verifier_schema": (
            "Requirement, claim and full-question evidence IDs are restricted to application-owned IDs "
            "built once per cited source span in source catalogue order; shared sources have "
            "shared IDs and explicit eligible claim indexes; per-claim schema variants bind "
            "claim_index and evidence IDs to that claim's cited sources; "
            "supported variants require nonempty evidence IDs; requested_answer quotes the "
            "entire whitespace-normalized original question"
        ),
        "evidence_span_rule": (
            "whitespace-normalize, split at ingestion sentence boundaries except known abbreviations; also offer separate quotes after title-case abbreviation continuations; hard-split spans every "
            f"{MAX_QUOTE_CHARS} characters, discard empty spans, preserve order and deduplicate"
        ),
        "sentence_end_pattern": _SENTENCE_END.pattern,
        "abbreviation_pattern": _ABBREVIATION_PERIOD.pattern,
        "possible_sentence_start_pattern": _POSSIBLE_SENTENCE_START.pattern,
        "coverage_claim_binding": "Supported full-question evidence IDs must be used by approved claim verdicts",
        "requirement_coverage_binding": "Every supported requirement's evidence IDs must be used by approved claim verdicts; whole-question coverage is independently required",
        "verifier_schema": VERIFIER_SCHEMA,
        "proof_instructions": _PROOF_INSTRUCTIONS,
        "proof_schema": PROOF_SCHEMA,
        "proof_input": "Question and claim targets with only final approved display excerpts; no full sources or previous verifier output",
        "verifier_prompt_schema": "The same bounded response schema is serialized compactly before untrusted input and sent to the API",
        "verifier_source_selection": "Draft selects source IDs; application supplies exact source excerpts and eligible evidence IDs",
        "insufficient_evidence": INSUFFICIENT_EVIDENCE,
        "render_citations": "Locations come only from final approved evidence selections, even without evidence capture",
        "render_labels": {
            "this_document_authors": "",
            "external_publication": "Cited literature: ",
            "non_study_context": "Context: ",
        },
        "citation_render": "{document}, page {page}",
        "evidence_text": "Application-owned whitespace-normalized source spans selected by verifier evidence IDs; drafts cannot supply quotes",
        "inline_citation_pattern": _INLINE_CITATION.pattern,
    }
    encoded = json.dumps(
        contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
