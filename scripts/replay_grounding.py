"""Replay saved evidence through grounding, retaining drafts and rejection reasons."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import cast

from app.grounding import grounded_answer
from app.types import ChunkData
from scripts.evaluate_answers import load_report, reserve_output, save_report, settings_for


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
    results: list[dict[str, object]] = []
    report: dict[str, object] = {
        "status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
        "source_report": str(args.report), "corpus": saved.corpus.model_dump(),
        "settings": settings_for(saved.settings.strategy, "verified", saved.settings.top_k), "results": results,
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
            try:
                answer = grounded_answer(result.case.question,
                    [cast(ChunkData, s.model_dump()) for s in result.sources], trace=trace)
                item["answer"] = answer
                print(result.case.id + ": " + answer, flush=True)
            finally:
                item["elapsed_ms"] = (perf_counter() - start) * 1000
                save_report(args.output, report)
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
