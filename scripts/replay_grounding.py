"""Replay saved evidence through grounding, retaining drafts and rejection reasons."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import cast

from app.grounding import GROUNDING_MODEL, grounded_answer
from app.llm.telemetry import capture_calls, runtime_snapshot
from app.types import AnswerClaim, ChunkData
from scripts.evaluate_answers import load_report, reserve_output, save_report, settings_for, validate_runtime


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--case", dest="ids", action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    saved = load_report(args.report)
    cases = [r for r in saved.results if args.ids is None or r.case.id in args.ids]
    if not cases or (args.ids and set(args.ids) != {r.case.id for r in cases}):
        parser.error("Selected case IDs must exist in the saved results")
    reserve_output(args.output)
    before = runtime_snapshot([GROUNDING_MODEL])
    results: list[dict[str, object]] = []
    settings = settings_for(saved.settings.strategy, "verified", saved.settings.top_k)
    # These passages were selected by the saved run, not today's retrieval policy.
    settings.update({
        "candidate_count": saved.settings.candidate_count,
        "reserve_vector_page": saved.settings.reserve_vector_page,
        "neighbor_radius": saved.settings.neighbor_radius,
        "max_context_chars": saved.settings.max_context_chars,
    })
    report: dict[str, object] = {
        "schema_version": 2,
        "status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
        "source_report": str(args.report), "corpus": saved.corpus.model_dump(),
        "settings": settings, "results": results,
        "runtime_before": before.model_dump(), "runtime_after": None,
        "methodology": "Fixed saved sources; new grounding only, no retrieval or evaluation judge. Inspect traces manually.",
    }
    save_report(args.output, report)
    try:
        for result in cases:
            trace: list[dict[str, object]] = []
            item: dict[str, object] = {"case": result.case.model_dump(),
                                      "sources": [s.model_dump() for s in result.sources], "trace": trace}
            results.append(item)
            start = perf_counter()
            claims: list[AnswerClaim] = []
            # Save failed-call timing too, but never expose draft evidence as accepted.
            with capture_calls() as calls:
                try:
                    answer = grounded_answer(result.case.question,
                        [cast(ChunkData, s.model_dump()) for s in result.sources],
                        trace=trace, claim_evidence=claims)
                    item["answer"] = answer
                    item["claim_evidence"] = claims
                    print(result.case.id + ": " + answer, flush=True)
                finally:
                    item["elapsed_ms"] = (perf_counter() - start) * 1000
                    item["answer_calls"] = [call.model_dump() for call in calls]
                    save_report(args.output, report)
        after = runtime_snapshot([GROUNDING_MODEL])
        report["runtime_after"] = after.model_dump()
        validate_runtime(before, after)
        report["status"] = "complete"
    except (Exception, KeyboardInterrupt) as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_report(args.output, report)


if __name__ == "__main__":
    main()
