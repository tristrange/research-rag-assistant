"""Generate one frozen candidate arm and record replay digests at completion."""

import argparse
import json
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys

import httpx

from scripts.evaluate_answers import EVALUATOR_PROMPT_SHA256, ReportModel, SettingsModel, save_report, settings_for
from scripts.evaluate_grounding_replays import (
    CandidateConfig, ComparisonProtocol, load_inputs, validate_candidate_settings,
)
from scripts.prepare_human_review import ReviewManifest, configuration_hash, review_set_hash


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def model_identity(protocol: ComparisonProtocol, candidate: CandidateConfig) -> dict[str, object]:
    version = httpx.get("http://localhost:11434/api/version", timeout=10.0)
    version.raise_for_status()
    tags = httpx.get("http://localhost:11434/api/tags", timeout=10.0)
    tags.raise_for_status()
    models = tags.json().get("models", [])
    if version.json().get("version") != protocol.ollama_version or not any(
        item.get("name") == candidate.model and item.get("digest") == candidate.digest
        for item in models
    ):
        raise ValueError("installed candidate/runtime differs from the frozen protocol")
    return {"name": candidate.model, "digest": candidate.digest}


def record_arm(manifest: ReviewManifest, root: Path, protocol: ComparisonProtocol, output: Path) -> None:
    root, output = root.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError("Use a fresh output directory; previous trials must be preserved")
    if review_set_hash(manifest) != protocol.review_set_sha256:
        raise ValueError("comparison protocol names a different frozen selection")
    if EVALUATOR_PROMPT_SHA256 != protocol.evaluator_prompt_sha256:
        raise ValueError("evaluator prompt differs from the frozen comparison protocol")
    project = Path(__file__).resolve().parents[1]
    code_hash = sha256((project / "app/grounding.py").read_bytes()).hexdigest()
    if code_hash != protocol.grounding_code_sha256:
        raise ValueError("grounding implementation differs from the frozen protocol")
    candidate: CandidateConfig | None = None
    for selection in manifest.selections:
        raw = (root / selection.report).read_bytes()
        if sha256(raw).hexdigest() != selection.sha256:
            raise ValueError("frozen source report hash changed")
        source = ReportModel.model_validate_json(raw)
        if source.status != "complete" or configuration_hash(source) != manifest.configuration_sha256:
            raise ValueError("source report does not match the frozen configuration")
        current = validate_candidate_settings(protocol, SettingsModel.model_validate(
            settings_for(source.settings.strategy, "verified", source.settings.top_k)))
        if candidate is not None and candidate != current:
            raise ValueError("one generation record must contain only one candidate")
        candidate = current
    assert candidate is not None  # ReviewManifest requires a nonempty selection.
    identity = model_identity(protocol, candidate)
    environment = os.environ.copy() | {
        "RAG_GROUNDING_MODEL": candidate.model,
        "RAG_DRAFT_THINK": str(candidate.draft_think).lower(),
        "RAG_VERIFIER_THINK": str(candidate.verifier_think).lower(),
    }
    if protocol.schema_version == 3:
        assert candidate.sampling is not None
        environment.update({"RAG_GROUNDING_SAMPLING": json.dumps(candidate.sampling.options()),
                            "RAG_GROUNDING_OUTPUT_TOKENS": str(candidate.output_tokens)})
        if candidate.draft_timeout_seconds == candidate.verifier_timeout_seconds:
            environment["RAG_GROUNDING_TIMEOUT_SECONDS"] = str(candidate.draft_timeout_seconds)
        else:
            # Different stage timeouts can only come from the legacy thinking defaults;
            # validate_candidate_settings above already checked the effective values.
            environment.pop("RAG_GROUNDING_TIMEOUT_SECONDS", None)
    output.mkdir(parents=True, exist_ok=False)
    steps: list[dict[str, object]] = []
    record: dict[str, object] = {
        "status": "running", "started_at": now(), "server_version": {"version": protocol.ollama_version},
        "models": [identity], "grounding_code_sha256": code_hash, "protocol": protocol.model_dump(),
        "steps": steps, "methodology": "Replay SHA-256 captured immediately after each generation process exits; "
                                        "candidate/runtime checked before and after each replay.",
    }
    record_path = output / "run.json"
    save_report(record_path, record)
    paths: list[Path] = []
    try:
        for selection in manifest.selections:
            model_identity(protocol, candidate)
            path = output / f"{selection.id}.json"
            command = [sys.executable, "-m", "scripts.replay_grounding", str(root / selection.report)]
            for identifier in selection.case_ids:
                command += ["--case", identifier]
            command += ["--output", str(path)]
            with (output / f"{selection.id}.log").open("x") as log:
                completed = subprocess.run(command, cwd=project, env=environment,
                                           stdout=log, stderr=subprocess.STDOUT)
            steps.append({"report": str(path), "returncode": completed.returncode,
                          "replay_sha256": sha256(path.read_bytes()).hexdigest() if path.exists() else None,
                          "digest_recorded_at": now()})
            save_report(record_path, record)
            if completed.returncode != 0:
                raise RuntimeError(f"Replay failed for {selection.id}; original report and log preserved")
            model_identity(protocol, candidate)
            paths.append(path)
        # Require the complete, unchanged selection before calling the arm complete.
        load_inputs(manifest, root, paths, protocol=protocol)
        record["status"] = "complete"
    except BaseException as error:
        record["status"] = "failed"
        record["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        record["finished_at"] = now()
        save_report(record_path, record)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("benchmarks/v1-development-review.json"))
    parser.add_argument("--protocol", type=Path, default=Path("benchmarks/verified-model-comparison-direct.json"))
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    record_arm(ReviewManifest.model_validate_json(args.manifest.read_bytes()), args.source_root,
               ComparisonProtocol.model_validate_json(args.protocol.read_bytes()), args.output_dir)


if __name__ == "__main__":
    main()
