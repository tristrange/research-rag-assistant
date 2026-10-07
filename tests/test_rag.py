import unittest
from typing import Literal
from unittest.mock import ANY, MagicMock, call, patch

from app.db.models import Chunk
from app.grounding import INSUFFICIENT_EVIDENCE
from app.rag import OVERVIEW_SECTION_PRIORITY, answer_each_document, answer_question
from app.retrieval.rerank import with_vector_reserve
from app.retrieval.search import QuestionEmbedding
from app.types import AnswerClaim, ChunkData


class RagTests(unittest.TestCase):
    def test_verified_default_retains_six_seeds_and_their_citation_indexes(self) -> None:
        candidates = [Chunk(document="paper.pdf", page=2, chunk_index=index,
                            text=f"Result {index}.", section="results") for index in range(10)]

        def retain(query: str, chunks: list[Chunk], limit: int) -> list[Chunk]:
            return chunks[:limit]

        def approve(question: str, sources: list[ChunkData],
                    *, claim_evidence: list[AnswerClaim]) -> str:
            claim_evidence.append({"text": "Supported comparison.",
                                   "attribution": "this_document_authors",
                                   "citations": [{"source_index": 5, "quote": "Result 5."}]})
            return "Supported comparison."

        with patch("app.rag.search_chunks", return_value=candidates) as search, \
                patch("app.rag.rerank_chunks", side_effect=retain), \
                patch("app.rag.grounded_answer", side_effect=approve), \
                patch("app.rag.expand_chunks") as expand:
            result = answer_question("Comparison?", answer_mode="verified", document="paper.pdf")
        self.assertEqual(len(result["sources"]), 6)
        self.assertEqual(result["sources"][5]["text"], "Result 5.")
        self.assertEqual(result["claim_evidence"][0]["citations"][0]["source_index"], 5)
        self.assertEqual(search.call_args.kwargs["document"], "paper.pdf")
        self.assertEqual(search.call_args.kwargs["limit"], 10)
        expand.assert_not_called()

    def test_wider_verified_default_preserves_explicit_cutoffs_and_other_modes(self) -> None:
        candidates = [Chunk(document="paper.pdf", page=2, chunk_index=index,
                            text=f"Result {index}.", section="results") for index in range(10)]

        def retain(query: str, chunks: list[Chunk], limit: int) -> list[Chunk]:
            return chunks[:limit]

        configurations: list[tuple[Literal["plain", "verified"], int | None, bool, bool, bool]] = [
            ("verified", 3, True, False, False),
            ("plain", None, True, False, False),
            ("verified", None, False, False, False),
            ("verified", None, True, True, False),
            ("verified", None, True, False, True),
        ]
        for mode, limit, reranked, overview, reserve in configurations:
            with self.subTest(mode=mode, limit=limit, reranked=reranked,
                              overview=overview, reserve=reserve), \
                    patch("app.rag.search_chunks", return_value=candidates) as search, \
                    patch("app.rag.rerank_chunks", side_effect=retain) as rerank, \
                    patch("app.rag.grounded_answer", return_value=INSUFFICIENT_EVIDENCE), \
                    patch("app.rag.generate", return_value="Answer"):
                answer_question("Question?", document="paper.pdf", answer_mode=mode,
                                limit=limit, use_reranking=reranked, overview=overview,
                                reserve_vector_candidate=reserve)
            if not reranked:
                self.assertEqual(search.call_args.kwargs["limit"], 3)
            else:
                self.assertEqual(rerank.call_args.kwargs["limit"], 3)

    def test_verified_mode_uses_selected_sources_without_free_text_regeneration(self) -> None:
        source = Chunk(document="paper.pdf", page=10, chunk_index=1,
                       text="A cited study.", section="references")
        with patch("app.rag.search_chunks", return_value=[source]), \
                patch("app.rag.rerank_chunks", return_value=[source]), \
                patch("app.rag.grounded_answer", return_value="Checked answer") as grounded, \
                patch("app.rag.generate") as generate:
            result = answer_question("Question", answer_mode="verified")
        grounded.assert_called_once_with("Question", result["sources"], claim_evidence=[])
        generate.assert_not_called()
        self.assertEqual(result["answer"], "Checked answer")
        self.assertEqual(result["outcome"], "answered")

    def test_verified_source_present_refusal_has_insufficient_evidence_outcome(self) -> None:
        source = Chunk(document="paper.pdf", page=10, chunk_index=1,
                       text="A cited study.", section="references")
        with patch("app.rag.search_chunks", return_value=[source]), \
                patch("app.rag.rerank_chunks", return_value=[source]), \
                patch("app.rag.grounded_answer", return_value=INSUFFICIENT_EVIDENCE):
            result = answer_question("Question", answer_mode="verified")
        self.assertEqual(result["sources"], [{
            "document": "paper.pdf", "page": 10, "chunk_index": 1,
            "text": "A cited study.", "section": "references",
        }])
        self.assertEqual(result["answer"], INSUFFICIENT_EVIDENCE)
        self.assertEqual(result["outcome"], "insufficient_evidence")

    def test_plain_refusal_text_does_not_infer_an_outcome(self) -> None:
        selected = Chunk(document="paper.pdf", page=1, chunk_index=0, text="Evidence")
        with patch("app.rag.search_chunks", return_value=[selected]), \
                patch("app.rag.rerank_chunks", return_value=[selected]), \
                patch("app.rag.generate", return_value=INSUFFICIENT_EVIDENCE):
            result = answer_question("Question", answer_mode="plain")
        self.assertEqual(result["answer"], INSUFFICIENT_EVIDENCE)
        self.assertNotIn("outcome", result)

    def test_reference_sources_are_labelled_and_retained(self) -> None:
        reference = Chunk(document="paper.pdf", page=10, chunk_index=1,
                          text="A cited intervention study.", section="references")
        with patch("app.rag.search_chunks", return_value=[reference]), \
                patch("app.rag.rerank_chunks", return_value=[reference]), \
                patch("app.rag.generate", return_value="Cited work") as generate:
            result = answer_question("What does the cited study report?")
        self.assertEqual(result["sources"][0]["section"], "references")
        prompt = generate.call_args.args[0]
        self.assertIn("[paper.pdf, page 10, section references]", prompt)
        self.assertIn("A cited intervention study.", prompt)
        self.assertIn("require explicit evidence", prompt)

    def test_default_uses_reranking_and_passes_selected_context_to_generator(self) -> None:
        selected = Chunk(document="paper.pdf", page=2, chunk_index=1, text="Evidence")
        rejected = Chunk(document="paper.pdf", page=3, chunk_index=1, text="Distractor")
        with patch("app.rag.search_chunks", return_value=[rejected, selected]) as search, \
                patch("app.rag.rerank_chunks", return_value=[selected]) as rerank, \
                patch("app.rag.generate", return_value="Answer") as generate:
            result = answer_question("Question")
            search.assert_called_once_with("Question", limit=10, document=None, query_embedding=ANY)
            rerank.assert_called_once_with("Question", [rejected, selected], limit=3)
            prompt = generate.call_args.args[0]
            self.assertIn("Evidence", prompt)
            self.assertNotIn("Distractor", prompt)
            self.assertEqual(result["sources"][0]["page"], 2)

    def test_expanded_default_keeps_six_seeds_and_explicit_limit_is_respected(self) -> None:
        candidates = [Chunk(document="paper.pdf", page=1, chunk_index=i, text=f"Evidence {i}")
                      for i in range(10)]
        for requested, expected in [(None, 6), (3, 3)]:
            with self.subTest(limit=requested), \
                    patch("app.rag.search_chunks", return_value=candidates) as search, \
                    patch("app.rag.rerank_chunks", side_effect=lambda q, cs, limit: cs[:limit]) as rerank, \
                    patch("app.rag.expand_chunks", return_value=[]) as expand, \
                    patch("app.rag.generate", return_value="Answer"):
                answer_question("Question", limit=requested, expand_context=True)
            search.assert_called_once_with("Question", limit=10, document=None, query_embedding=ANY)
            rerank.assert_called_once_with("Question", candidates, limit=expected)
            expand.assert_called_once_with(candidates[:expected])

    def test_invalid_limit_fails_before_services(self) -> None:
        with patch("app.rag.search_chunks") as search:
            for limit in [0, -1]:
                with self.assertRaises(ValueError):
                    answer_question("Question", limit=limit)
            search.assert_not_called()

    def test_vector_reserve_adds_first_unselected_vector_candidate_to_verified_sources(self) -> None:
        candidates = [
            Chunk(document="paper.pdf", page=1, chunk_index=i, text=f"Evidence {i}")
            for i in range(5)
        ]
        reranked = [candidates[2], candidates[0], candidates[4]]
        with patch("app.rag.search_chunks", return_value=candidates) as search, \
                patch("app.rag.rerank_chunks", return_value=reranked) as rerank, \
                patch("app.rag.grounded_answer", return_value="Checked") as grounded:
            result = answer_question("Question", answer_mode="verified", reserve_vector_candidate=True)

        search.assert_called_once_with("Question", limit=10, document=None, query_embedding=ANY)
        rerank.assert_called_once_with("Question", candidates, limit=3)
        self.assertEqual([source["chunk_index"] for source in result["sources"]], [2, 0, 4, 1])
        grounded.assert_called_once_with("Question", result["sources"], claim_evidence=[])

    def test_vector_reserve_rejects_incompatible_modes_before_search(self) -> None:
        with patch("app.rag.search_chunks") as search:
            with self.assertRaisesRegex(ValueError, "unexpanded reranking"):
                answer_question("Question", reserve_vector_candidate=True, use_reranking=False)
            with self.assertRaisesRegex(ValueError, "unexpanded reranking"):
                answer_question("Question", reserve_vector_candidate=True, expand_context=True)
            with self.assertRaisesRegex(ValueError, "limit below 10"):
                answer_question("Question", limit=10, reserve_vector_candidate=True)
            search.assert_not_called()

    def test_vector_reserve_fails_when_corpus_has_no_extra_candidate(self) -> None:
        only_chunk = Chunk(document="paper.pdf", page=1, chunk_index=0, text="Evidence")
        with self.assertRaisesRegex(ValueError, "unselected vector candidate"):
            with_vector_reserve([only_chunk], [only_chunk])

    def test_vector_mode_uses_same_generation_path_without_reranking(self) -> None:
        selected = Chunk(document="paper.pdf", page=1, chunk_index=0, text="Evidence")
        with patch("app.rag.search_chunks", return_value=[selected]) as search, \
                patch("app.rag.rerank_chunks") as rerank, \
                patch("app.rag.expand_chunks") as expand, \
                patch("app.rag.generate", return_value="Not enough information") as generate:
            result = answer_question("Question", use_reranking=False)
            search.assert_called_once_with("Question", limit=3, document=None, query_embedding=ANY)
            rerank.assert_not_called()
            expand.assert_not_called()
            generate.assert_called_once()
            self.assertEqual(result["answer"], "Not enough information")

    def test_selected_document_filters_candidates_for_both_retrieval_modes(self) -> None:
        selected = Chunk(document="paper.pdf", page=1, chunk_index=0, text="Evidence")
        for use_reranking, candidate_limit in [(True, 10), (False, 3)]:
            with self.subTest(use_reranking=use_reranking), \
                    patch("app.rag.search_chunks", return_value=[selected]) as search, \
                    patch("app.rag.rerank_chunks", return_value=[selected]), \
                    patch("app.rag.generate", return_value="Answer"):
                result = answer_question(
                    "Question", document="paper.pdf", use_reranking=use_reranking,
                )
            search.assert_called_once_with("Question", limit=candidate_limit, document="paper.pdf", query_embedding=ANY)
            self.assertEqual([source["document"] for source in result["sources"]], ["paper.pdf"])

    def test_no_matching_document_returns_empty_evidence_without_generation(self) -> None:
        with patch("app.rag.search_chunks", return_value=[]) as search, \
                patch("app.rag.rerank_chunks") as rerank, \
                patch("app.rag.generate") as generate, \
                patch("app.rag.grounded_answer") as grounded:
            result = answer_question("Question", document="missing.pdf")
        search.assert_called_once_with("Question", limit=10, document="missing.pdf", query_embedding=ANY)
        rerank.assert_not_called()
        generate.assert_not_called()
        grounded.assert_not_called()
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["answer"], INSUFFICIENT_EVIDENCE)
        self.assertEqual(result["outcome"], "insufficient_evidence")

    def test_expanded_sources_are_the_exact_evidence_sent_to_generator(self) -> None:
        selected = Chunk(document="paper.pdf", page=2, chunk_index=1, text="Seed")
        expanded = [{
            "document": "paper.pdf",
            "page": 2,
            "chunk_index": 0,
            "text": "Previous. Seed. Following.",
        }]
        with patch("app.rag.search_chunks", return_value=[selected]), \
                patch("app.rag.rerank_chunks", return_value=[selected]), \
                patch("app.rag.expand_chunks", return_value=expanded) as expand, \
                patch("app.rag.generate", return_value="Answer") as generate:
            result = answer_question("Question", expand_context=True)

        expand.assert_called_once_with([selected])
        prompt = generate.call_args.args[0]
        self.assertIn("[paper.pdf, page 2, section unknown]\nPrevious. Seed. Following.", prompt)
        self.assertEqual(result["sources"], expanded)

    def test_unexpanded_path_preserves_ranked_chunks_and_does_not_lookup_neighbors(self) -> None:
        selected = Chunk(document="paper.pdf", page=2, chunk_index=7, text="Evidence")
        with patch("app.rag.search_chunks", return_value=[selected]), \
                patch("app.rag.rerank_chunks", return_value=[selected]), \
                patch("app.rag.expand_chunks") as expand, \
                patch("app.rag.generate", return_value="Answer") as generate:
            result = answer_question("Question")

        expand.assert_not_called()
        self.assertIn("[paper.pdf, page 2, section unknown]\nEvidence", generate.call_args.args[0])
        self.assertEqual(result["sources"], [{
            "document": "paper.pdf",
            "page": 2,
            "chunk_index": 7,
            "text": "Evidence",
            "section": "unknown",
        }])

    def test_paper_overview_uses_summary_sections_and_finding_instructions(self) -> None:
        summary = Chunk(document="paper.pdf", page=4, chunk_index=2,
                        text="The intervention reduced the outcome.", section="conclusion")
        with patch("app.rag.search_chunks", return_value=[summary]) as search, \
                patch("app.rag.rerank_chunks", return_value=[summary]), \
                patch("app.rag.generate", return_value="Reduced outcome") as generate:
            result = answer_question("Main findings?", document="paper.pdf", overview=True)
        search.assert_called_once_with(
            "Main findings?", limit=10, document="paper.pdf", sections=("conclusion",), query_embedding=ANY,
        )
        self.assertEqual(result["sources"][0]["document"], "paper.pdf")
        self.assertIn("A list of measurements, methods", generate.call_args.args[0])

    def test_paper_overview_falls_back_to_results_when_summary_sections_absent(self) -> None:
        result_chunk = Chunk(document="paper.pdf", page=3, chunk_index=1,
                             text="The intervention reduced the outcome.", section="results")
        with patch("app.rag.search_chunks", side_effect=[[], [], [], [result_chunk]]) as search, \
                patch("app.rag.rerank_chunks", return_value=[result_chunk]), \
                patch("app.rag.generate", return_value="Reduced outcome"):
            result = answer_question("Main findings?", document="paper.pdf", overview=True)
        self.assertEqual(search.call_args_list, [
            call("Main findings?", limit=10, document="paper.pdf", sections=sections, query_embedding=ANY)
            for sections in OVERVIEW_SECTION_PRIORITY
        ])
        self.assertEqual(result["answer"], "Reduced outcome")

    def test_paper_overview_falls_back_to_document_when_sections_are_unknown(self) -> None:
        unknown = Chunk(document="paper.pdf", page=2, chunk_index=1,
                        text="The intervention reduced the outcome.", section="unknown")
        with patch("app.rag.search_chunks", side_effect=[[], [], [], [], [unknown]]) as search, \
                patch("app.rag.rerank_chunks", return_value=[unknown]), \
                patch("app.rag.generate", return_value="Reduced outcome"):
            result = answer_question("Main findings?", document="paper.pdf", overview=True)
        self.assertEqual(search.call_args_list[-1], call(
            "Main findings?", limit=10, document="paper.pdf", query_embedding=ANY,
        ))
        self.assertEqual(result["sources"][0]["section"], "unknown")
        self.assertEqual(result["answer"], "Reduced outcome")

    def test_every_paper_is_answered_independently_and_labelled(self) -> None:
        def scoped_answer(question: str, *, document: str, answer_mode: str,
                          overview: bool, query_embedding: QuestionEmbedding) -> dict[str, object]:
            return {"answer": f"Finding for {document}", "outcome": "answered", "sources": [{
                "document": document, "page": 1, "chunk_index": 0,
                "text": f"Evidence for {document}",
            }], "claim_evidence": [{
                "text": f"Finding for {document}", "attribution": "this_document_authors",
                "citations": [{"source_index": 0, "quote": f"Evidence for {document}"}],
            }]}

        for overview in (True, False):
            with self.subTest(overview=overview), \
                    patch("app.rag.list_documents", return_value=["a.pdf", "b.pdf"]), \
                    patch("app.rag.answer_question", side_effect=scoped_answer) as answer:
                result = answer_each_document(
                    "Main findings?", answer_mode="verified", overview=overview,
                )
            self.assertEqual(answer.call_args_list, [
                call("Main findings?", document="a.pdf", answer_mode="verified", overview=overview, query_embedding=ANY),
                call("Main findings?", document="b.pdf", answer_mode="verified", overview=overview, query_embedding=ANY),
            ])
            self.assertIn("a.pdf:\nFinding for a.pdf", result["answer"])
            self.assertIn("b.pdf:\nFinding for b.pdf", result["answer"])
            self.assertEqual([source["document"] for source in result["sources"]], ["a.pdf", "b.pdf"])
            self.assertEqual([claim["citations"][0]["source_index"] for claim in result["claim_evidence"]], [0, 1])
            self.assertIs(answer.call_args_list[0].kwargs["query_embedding"], answer.call_args_list[1].kwargs["query_embedding"])

    def test_each_paper_aggregates_verified_outcomes(self) -> None:
        for outcomes, expected in [
            (["answered", "insufficient_evidence"], "partial"),
            (["answered", "answered"], "answered"),
            (["insufficient_evidence", "insufficient_evidence"], "insufficient_evidence"),
        ]:
            def scoped_answer(question: str, *, document: str, answer_mode: str,
                              overview: bool, query_embedding: QuestionEmbedding) -> dict[str, object]:
                outcome = outcomes[0 if document == "a.pdf" else 1]
                return {
                    "answer": f"Result for {document}", "outcome": outcome,
                    "sources": [{"document": document, "page": 1, "chunk_index": 0, "text": "Evidence"}],
                    "claim_evidence": [],
                }

            with self.subTest(outcomes=outcomes), \
                    patch("app.rag.list_documents", return_value=["a.pdf", "b.pdf"]), \
                    patch("app.rag.answer_question", side_effect=scoped_answer):
                result = answer_each_document("Question", answer_mode="verified", overview=False)
            self.assertEqual(result["outcome"], expected)

    def test_overview_fallbacks_make_one_embedding_call(self) -> None:
        selected = Chunk(document="paper.pdf", page=1, chunk_index=0, text="Evidence", section="unknown")
        db = MagicMock()
        db.scalar.side_effect = [None, 1, None] * 5
        db.scalars.side_effect = [[], [], [], [], [selected]]
        with patch("app.retrieval.search.SessionLocal", return_value=db), \
                patch("app.retrieval.search.embed_text", return_value=[0.0] * 768) as embed, \
                patch("app.rag.generate", return_value="Answer"):
            result = answer_question("Question", document="paper.pdf", overview=True, use_reranking=False)
        embed.assert_called_once_with("Question")
        self.assertEqual(db.scalars.call_count, 5)
        self.assertEqual(result["sources"][0]["section"], "unknown")

    def test_library_requests_share_one_vector_but_do_not_cache_between_requests(self) -> None:
        chunks = [Chunk(document=name, page=1, chunk_index=0, text=f"Evidence {name}")
                  for name in ("a.pdf", "b.pdf")]
        db = MagicMock()
        db.scalar.side_effect = [None, 1, None] * 4
        db.scalars.side_effect = [[chunks[0]], [chunks[1]]] * 2
        with patch("app.rag.list_documents", return_value=["a.pdf", "b.pdf"]), \
                patch("app.retrieval.search.SessionLocal", return_value=db), \
                patch("app.retrieval.search.embed_text", return_value=[0.0] * 768) as embed, \
                patch("app.rag.rerank_chunks", side_effect=lambda q, candidates, limit: candidates[:limit]), \
                patch("app.rag.grounded_answer", return_value="Checked"):
            first = answer_each_document("Question", overview=False, answer_mode="verified")
            self.assertEqual(embed.call_count, 1)
            second = answer_each_document("Question", overview=False, answer_mode="verified")
            self.assertEqual(embed.call_count, 2)
        self.assertEqual(first, second)
        self.assertEqual([s["document"] for s in first["sources"]], ["a.pdf", "b.pdf"])

    def test_empty_library_skips_embedding_and_models(self) -> None:
        with patch("app.rag.list_documents", return_value=[]), \
                patch("app.retrieval.search.embed_text") as embed, \
                patch("app.rag.grounded_answer") as grounded:
            result = answer_each_document("Question", overview=True, answer_mode="verified")
        embed.assert_not_called()
        grounded.assert_not_called()
        self.assertEqual(result, {
            "answer": INSUFFICIENT_EVIDENCE, "sources": [], "outcome": "insufficient_evidence",
        })


if __name__ == "__main__":
    unittest.main()
