"""Bounded, claim-level generation with deterministic evidence checks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from app.grounding_durations import duration_fingerprint
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
    MAX_CLAIMS,
    MAX_QUOTE_CHARS,
    PROOF_SCHEMA,
    VERIFIER_SCHEMA,
    VERIFIER_THINK,
    ApprovedProof,
    ClaimCitation,
    ClaimVerdict,
    GroundedClaim,
    GroundedDraft,
    QuestionRequirement,
    RequestedAnswerCoverage,
    StrictModel,
    VerificationResult,
    VerifierEvidence,
)
from app.grounding_prompts import (
    _DRAFT_INSTRUCTIONS,
    _PROOF_INSTRUCTIONS,
    _REPAIR_INSTRUCTIONS,
    _VERIFIER_INSTRUCTIONS,
    _bounded_draft_schema,
    _bounded_verifier_schema,
    _source_catalogue,
    build_draft_prompt,
    build_proof_prompt,
    build_repair_prompt,
    build_verifier_prompt,
)
from app.grounding_validation import (
    _INLINE_CITATION,
    _is_reference_source,
    _validate_draft,
    _validate_question_identifiers,
    _validate_verification,
    validate_verification_structure,
)
from app.ingestion.chunking import (
    _ABBREVIATION_PERIOD,
    _SENTENCE_END,
)
from app.llm.ollama import generate_json
from app.llm.telemetry import (
    VerificationStage,
    VerificationTrace,
    append_verification_trace,
    observe_verification_stage,
)
from app.types import AnswerClaim, ChunkData

# Compatibility surface: every module-level name importable from this module
# before the extraction stays importable from this facade.
__all__ = [
    "ApprovedProof",
    "ClaimCitation",
    "ClaimVerdict",
    "DRAFT_SCHEMA",
    "DRAFT_THINK",
    "GROUNDING_CONTEXT_TOKENS",
    "GROUNDING_CONTRACT_VERSION",
    "GROUNDING_DRAFT_TIMEOUT_SECONDS",
    "GROUNDING_MODEL",
    "GROUNDING_OUTPUT_TOKENS",
    "GROUNDING_SAMPLING",
    "GROUNDING_VERIFIER_TIMEOUT_SECONDS",
    "GroundedClaim",
    "GroundedDraft",
    "INSUFFICIENT_EVIDENCE",
    "MAX_CLAIMS",
    "MAX_QUOTE_CHARS",
    "PROOF_SCHEMA",
    "QuestionRequirement",
    "RequestedAnswerCoverage",
    "StrictModel",
    "VERIFIER_SCHEMA",
    "VERIFIER_THINK",
    "VerificationResult",
    "VerifierEvidence",
    "_DRAFT_INSTRUCTIONS",
    "_IDENTIFIER_TOKEN",
    "_INLINE_CITATION",
    "_POSSIBLE_SENTENCE_START",
    "_PROOF_INSTRUCTIONS",
    "_REPAIR_INSTRUCTIONS",
    "_VERIFIER_INSTRUCTIONS",
    "_bounded_draft_schema",
    "_bounded_verifier_schema",
    "_evidence_spans",
    "_is_reference_source",
    "_normalize_whitespace",
    "_record_accepted_evidence",
    "_render_claims",
    "_source_catalogue",
    "_validate_draft",
    "_validate_question_identifiers",
    "_validate_verification",
    "_verify_draft_with_feedback",
    "build_draft_prompt",
    "build_proof_prompt",
    "build_repair_prompt",
    "build_verifier_evidence",
    "build_verifier_prompt",
    "generate_approved_proof_json",
    "generate_draft_json",
    "generate_verification_json",
    "grounded_answer",
    "grounding_code_fingerprint",
    "grounding_fingerprint",
    "validate_verification_structure",
    "verify_draft",
]


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
    return generate_verification_json(
        build_proof_prompt(question, evidence), PROOF_SCHEMA
    )


def _verify_draft_with_feedback(
    question: str,
    draft: GroundedDraft,
    sources: list[ChunkData],
    *,
    verifier: Callable[[str, dict[str, object]], dict[str, object]] | None = None,
    trace: list[dict[str, object]] | None = None,
    diagnostics: list[VerificationTrace] | None = None,
    attempt: int = 1,
    contract_fingerprint: str = "",
    verification_stage: VerificationStage = "verification",
    proof_stage: VerificationStage = "verification_proof",
    rejection_stage: str = "rejected",
) -> tuple[bool, list[dict[str, object]]]:
    feedback: list[dict[str, object]] = []
    try:
        try:
            _validate_draft(draft, sources)
        except ValueError:
            append_verification_trace(
                diagnostics,
                stage="repair_draft_validation" if attempt == 2 else "draft_validation",
                attempt=attempt,
                contract_fingerprint=contract_fingerprint,
                parse_status="not_attempted",
                reason_category="draft_structure",
            )
            raise
        if not draft.answerable:
            return False, feedback
        evidence_catalogue = build_verifier_evidence(draft.claims, sources)
        with observe_verification_stage(
            diagnostics,
            stage=verification_stage,
            attempt=attempt,
            contract_fingerprint=contract_fingerprint,
        ) as diagnostic:
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
        try:
            _validate_verification(question, verification, draft.claims, sources)
        except ValueError:
            if diagnostic is not None:
                diagnostic.reason_category = "verifier_rejection"
            raise
        evidence: list[AnswerClaim] = []
        _record_accepted_evidence(draft, sources, feedback, evidence)
        proof_entry: dict[str, object] = {
            "stage": proof_stage,
            "output": None,
        }
        feedback.append(proof_entry)
        if trace is not None:
            trace.append(proof_entry)
        with observe_verification_stage(
            diagnostics,
            stage=proof_stage,
            attempt=attempt,
            contract_fingerprint=contract_fingerprint,
        ) as proof_diagnostic:
            proof_data = generate_approved_proof_json(question, evidence)
            proof_entry["output"] = proof_data
            proof = ApprovedProof.model_validate(proof_data)
        # Semantic rejection stays outside the parsing context, so it is not reclassified.
        if not proof.supported:
            if proof_diagnostic is not None:
                proof_diagnostic.reason_category = "proof_rejection"
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
    diagnostics: list[VerificationTrace] | None = None,
) -> str:
    """Render only wholly approved claims; propagate model transport errors."""
    if claim_evidence is not None:
        claim_evidence.clear()
    approved_evidence: list[AnswerClaim] = (
        claim_evidence if claim_evidence is not None else []
    )
    if not sources or not any(_evidence_spans(source["text"]) for source in sources):
        return INSUFFICIENT_EVIDENCE
    contract_fingerprint = grounding_fingerprint() if diagnostics is not None else ""
    draft_schema = _bounded_draft_schema(sources)
    draft_data: dict[str, object] | None = None
    feedback: list[dict[str, object]]
    try:
        with observe_verification_stage(
            diagnostics,
            stage="draft",
            attempt=1,
            contract_fingerprint=contract_fingerprint,
        ) as diagnostic:
            draft_data = generate_draft_json(
                build_draft_prompt(question, sources), draft_schema
            )
            if trace is not None:
                trace.append({"stage": "draft", "output": draft_data})
            try:
                draft = GroundedDraft.model_validate(draft_data)
            except ValueError:
                if draft_data.get("answerable") is not False:
                    raise
                if diagnostic is not None:
                    diagnostic.parse_status = "invalid_schema"
                    diagnostic.reason_category = "schema_mismatch"
                return INSUFFICIENT_EVIDENCE
            if not draft.answerable:
                if diagnostic is not None:
                    diagnostic.reason_category = "draft_unanswerable"
                return INSUFFICIENT_EVIDENCE
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
            diagnostics=diagnostics,
            attempt=1,
            contract_fingerprint=contract_fingerprint,
        )
        if accepted:
            _record_accepted_evidence(draft, sources, feedback, approved_evidence)
            return _render_claims(approved_evidence, sources)

    repair_diagnostic: VerificationTrace | None = None
    try:
        with observe_verification_stage(
            diagnostics,
            stage="repair_draft",
            attempt=2,
            contract_fingerprint=contract_fingerprint,
        ) as repair_diagnostic:
            repair_data = generate_draft_json(
                build_repair_prompt(question, sources, draft_data, feedback),
                _bounded_draft_schema(sources),
                repair=True,
            )
            if trace is not None:
                trace.append({"stage": "repair_draft", "output": repair_data})
            try:
                repaired_draft = GroundedDraft.model_validate(repair_data)
            except ValueError:
                if repair_data.get("answerable") is not False:
                    raise
                if repair_diagnostic is not None:
                    repair_diagnostic.parse_status = "invalid_schema"
                    repair_diagnostic.reason_category = "schema_mismatch"
                return INSUFFICIENT_EVIDENCE
            if not repaired_draft.answerable:
                if repair_diagnostic is not None:
                    repair_diagnostic.reason_category = "repair_unanswerable"
                return INSUFFICIENT_EVIDENCE
    except ValueError as error:
        if trace is not None:
            trace.append({"stage": "repair_rejected", "reason": str(error)})
        return INSUFFICIENT_EVIDENCE
    accepted, feedback = _verify_draft_with_feedback(
        question,
        repaired_draft,
        sources,
        trace=trace,
        diagnostics=diagnostics,
        attempt=2,
        contract_fingerprint=contract_fingerprint,
        verification_stage="repair_verification",
        proof_stage="repair_verification_proof",
        rejection_stage="repair_rejected",
    )
    if not accepted:
        return INSUFFICIENT_EVIDENCE
    _record_accepted_evidence(repaired_draft, sources, feedback, approved_evidence)
    return _render_claims(approved_evidence, sources)


def grounding_code_fingerprint() -> str:
    """Hash every grounding module so replay provenance covers the whole package."""
    modules = sorted(Path(__file__).resolve().parent.glob("grounding*.py"))
    digest = hashlib.sha256()
    for module in modules:
        content = module.read_bytes()
        digest.update(module.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


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
