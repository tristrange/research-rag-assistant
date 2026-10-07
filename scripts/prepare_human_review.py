"""Prepare an offline human-review packet from frozen, completed answer reports."""

import argparse
import csv
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from scripts.evaluate_answers import CompletedResultModel, ReportModel, StrictModel


class ReviewSelection(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    report: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_selection(self) -> "ReviewSelection":
        path = Path(self.report)
        if path.is_absolute() or ".." in path.parts or path.parts[:1] != ("evaluation-results",):
            raise ValueError("report must be under evaluation-results")
        if len(self.case_ids) != len(set(self.case_ids)) or any(not value for value in self.case_ids):
            raise ValueError("selected case IDs must be unique and nonempty")
        return self


class ReviewManifest(StrictModel):
    schema_version: Literal[1]
    purpose: Literal["development"]
    configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selections: list[ReviewSelection] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_selections(self) -> "ReviewManifest":
        ids = [selection.id for selection in self.selections]
        if len(ids) != len(set(ids)):
            raise ValueError("selection IDs must be unique")
        return self


REVIEW_COLUMNS = ["case_key", "decision", "notes", "review_set_sha256"]
DECISIONS = {"pending", "pass", "needs_fix", "label_issue"}


def case_keys(manifest: ReviewManifest) -> list[str]:
    return [f"{selection.id}/{case_id}" for selection in manifest.selections for case_id in selection.case_ids]


def review_set_hash(manifest: ReviewManifest) -> str:
    return sha256(manifest.model_dump_json().encode()).hexdigest()


def configuration_hash(report: ReportModel) -> str:
    settings = report.settings.model_dump()
    # Preserve the identity of frozen reports written before these settings.
    # Missing fields remain unknown; they must not be inferred from today's defaults.
    for key in ("grounding_sampling", "grounding_draft_timeout_seconds", "grounding_verifier_timeout_seconds",
                "reserve_vector_page"):
        if key not in report.settings.model_fields_set:
            settings.pop(key)
    configuration = {"settings": settings,
                     "generator_model": report.generator_model, "judge_model": report.judge_model,
                     "embedding_model": report.embedding_model, "reranker_model": report.reranker_model}
    if report.runtime_before is not None:
        configuration["runtime_before"] = report.runtime_before.model_dump()
    return sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()


def _text(value: str) -> str:
    return f"<pre>{escape(value)}</pre>"


def _location(document: str, page: int, pdf_document: str, pdf_uri: str) -> str:
    label = f"{escape(document)}, PDF page {page}"
    if document == pdf_document:
        return f'<a href="{escape(pdf_uri, quote=True)}#page={page}" target="_blank" rel="noopener">{label}</a>'
    return label


def _case_html(key: str, result: CompletedResultModel, number: int, pdf_document: str, pdf_uri: str) -> str:
    label = "answerable" if result.case.answerable else "unanswerable"
    sources = "".join(
        f"<h4>Passage {index}: {_location(source.document, source.page, pdf_document, pdf_uri)}, "
        f"chunk {source.chunk_index}, {escape(source.section)}</h4>{_text(source.text)}"
        for index, source in enumerate(result.sources, 1)
    ) or "<p>No passages returned.</p>"
    evidence = "".join(
        f"<h4>{_location(item.document, item.page, pdf_document, pdf_uri)}</h4>{_text(item.quote)}"
        for item in result.case.evidence
    ) or "<p>No evidence label; inspect the paper to confirm unanswerability.</p>"
    if result.claim_evidence is None:
        accepted = "<p>Unknown: this report did not capture accepted claim evidence.</p>"
    elif not result.claim_evidence:
        accepted = "<p>No claims were approved by the grounding verifier.</p>"
    else:
        accepted = "".join(
            f"<h4>{escape(claim.attribution)}</h4>{_text(claim.text)}" + "".join(
                f"<p>Passage {quote.source_index + 1}</p>{_text(quote.quote)}"
                for quote in claim.citations
            ) for claim in result.claim_evidence
        )
    return (
        f'<article id="case-{number}"><h2>{escape(key)}</h2>'
        f'<p>Original paper: <a href="{escape(pdf_uri, quote=True)}" target="_blank" '
        f'rel="noopener">{escape(pdf_document)}</a></p><h3>Question</h3>{_text(result.case.question)}'
        f"<h3>Recorded answer</h3>{_text(result.answer)}"
        f"<h3>Machine-approved claim evidence</h3>{accepted}"
        f"<h3>Retrieved passages</h3>{sources}"
        f"<details><summary>Reference label ({label}) — review this too</summary>"
        f"{_text(result.case.reference_answer)}{evidence}</details></article>"
    )


def prepare_packet(manifest: ReviewManifest, root: Path, output: Path) -> None:
    root = root.resolve()
    output = output.resolve()
    if (root / "evaluation-results").resolve() not in output.parents:
        raise ValueError("output must be a new directory under evaluation-results")
    articles: list[str] = []
    rows: list[list[str]] = []
    provenance: list[dict[str, object]] = []
    # Validate every input before creating output. Do not regenerate or alter reports.
    for selection in manifest.selections:
        path = (root / selection.report).resolve()
        if (root / "evaluation-results").resolve() not in path.parents:
            raise ValueError("report resolves outside evaluation-results")
        data = path.read_bytes()
        if sha256(data).hexdigest() != selection.sha256:
            raise ValueError(f"Report hash changed: {selection.id}")
        report = ReportModel.model_validate_json(data)
        if report.status != "complete" or report.settings.answer_mode != "verified":
            raise ValueError("human review requires completed verified-answer reports")
        if configuration_hash(report) != manifest.configuration_sha256:
            raise ValueError(f"Answer configuration differs from the frozen protocol: {selection.id}")
        documents = list(report.corpus.chunks_by_document)
        if len(documents) != 1:
            raise ValueError("review requires an isolated single-paper report")
        document = documents[0]
        if Path(document).name != document or "\\" in document or Path(document).suffix.lower() != ".pdf":
            raise ValueError("paper identity must be a PDF filename")
        pdf = (root / "data" / document).resolve()
        if (root / "data").resolve() not in pdf.parents:
            raise ValueError("paper resolves outside data")
        if sha256(pdf.read_bytes()).hexdigest() != report.paper_sha256:
            raise ValueError(f"PDF hash changed: {selection.id}")
        results = {result.case.id: result for result in report.results}
        if not set(selection.case_ids) <= results.keys():
            raise ValueError(f"Missing selected cases: {selection.id}")
        provenance.append({
            "id": selection.id, "report": selection.report, "sha256": selection.sha256,
            "started_at": report.started_at, "generator_model": report.generator_model,
            "embedding_model": report.embedding_model, "reranker_model": report.reranker_model,
            "settings": report.settings.model_dump(), "corpus": report.corpus.model_dump(),
            "paper_sha256": report.paper_sha256,
        })
        for case_id in selection.case_ids:
            result = results[case_id]
            key = f"{selection.id}/{case_id}"
            articles.append(_case_html(key, result, len(articles) + 1, document, pdf.as_uri()))
            rows.append([key, "pending", "", review_set_hash(manifest)])
    navigation = "<ol>" + "".join(
        f'<li><a href="#case-{number}">{escape(key)}</a></li>'
        for number, key in enumerate(case_keys(manifest), 1)
    ) + "</ol>"
    html = (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>v1 development review</title><style>'
        'body{max-width:900px;margin:2rem auto;padding:0 1rem;font:17px/1.5 system-ui}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;background:#f5f7f6;padding:1rem}'
        'article{border-top:2px solid #ccc;margin-top:3rem;padding-top:1rem}'
        'summary{cursor:pointer;font-weight:bold}@media print{article{break-before:page}}'
        '</style><h1>v1 development review</h1>'
        '<p>Read each question and answer before opening its reference label. Check the original PDF '
        'as well as the returned passages. Labels are assistant-authored and may be wrong. '
        'Model-judge scores are deliberately omitted.</p>'
        '<p>In review.csv, replace pending with pass, needs_fix, or label_issue. Record notes for '
        'any problem: factual accuracy, completeness, population/duration qualifiers, attribution, '
        'the passages actually cited, or refusal behavior. An answerable question may be refused '
        'because retrieval missed evidence; mark that needs_fix. Missing evidence is not a negative result.</p>'
        '<p>This packet reuses inspected development cases and historical answers. It is not a '
        'fresh validation run or a release approval. Reports contain displayed page references '
        'and retrieved passages, but not the original selected quote for each claim. A cited page '
        'may match several passages; inspect their support rather than assuming every passage was cited.</p>'
        + navigation + "".join(articles) + '</html>'
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "packet.html").write_text(html, encoding="utf-8")
    (output / "provenance.json").write_text(json.dumps({
        "review_set_sha256": review_set_hash(manifest),
        "configuration_sha256": manifest.configuration_sha256, "reports": provenance,
    }, indent=2) + "\n", encoding="utf-8")
    with (output / "review.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(REVIEW_COLUMNS)
        writer.writerows(rows)


def summarize_review(manifest: ReviewManifest, path: Path) -> dict[str, int]:
    expected = set(case_keys(manifest))
    counts = dict.fromkeys(sorted(DECISIONS), 0)
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != REVIEW_COLUMNS:
            raise ValueError("review CSV columns changed")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("review CSV row has missing or extra fields")
            if row["review_set_sha256"] != review_set_hash(manifest):
                raise ValueError("review belongs to a different frozen selection")
            key = row["case_key"]
            if key not in expected or key in seen:
                raise ValueError("review contains unknown or duplicate cases")
            seen.add(key)
            decision = row["decision"]
            if decision not in DECISIONS:
                raise ValueError(f"Unknown review decision for {key}")
            if decision in {"needs_fix", "label_issue"} and not row["notes"].strip():
                raise ValueError(f"Problem requires notes: {key}")
            counts[decision] += 1
    if seen != expected:
        raise ValueError("review is missing selected cases")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("benchmarks/v1-development-review.json"))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path, help="new packet directory under evaluation-results")
    mode.add_argument("--summarize", type=Path, help="completed review CSV (no model calls)")
    args = parser.parse_args()
    manifest = ReviewManifest.model_validate_json(args.manifest.read_text(encoding="utf-8"))
    if args.output is not None:
        prepare_packet(manifest, Path.cwd(), args.output)
        print(f"Prepared {len(case_keys(manifest))} cases in {args.output}")
    else:
        counts = summarize_review(manifest, args.summarize)
        print(json.dumps(counts, indent=2))
        if any(counts[key] for key in ("pending", "needs_fix", "label_issue")):
            raise SystemExit("Human review is incomplete or has unresolved issues")


if __name__ == "__main__":
    main()
