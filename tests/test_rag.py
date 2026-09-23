import unittest
from unittest.mock import call, patch

from app.db.models import Chunk
from app.grounding import INSUFFICIENT_EVIDENCE
from app.rag import OVERVIEW_SECTION_PRIORITY, answer_each_document, answer_question
from app.retrieval.rerank import with_vector_reserve


class RagTests(unittest.TestCase):
    def test_verified_mode_uses_selected_sources_without_free_text_regeneration(self) -> None:
        source = Chunk(document="paper.pdf", page=10, chunk_index=1,
                       text="A cited study.", section="references")
        with patch("app.rag.search_chunks", return_value=[source]), \
                patch("app.rag.rerank_chunks", return_value=[source]), \
                patch("app.rag.grounded_answer", return_value="Checked answer") as grounded, \
                patch("app.rag.generate") as generate:
            result = answer_question("Question", answer_mode="verified")
        grounded.assert_called_once_with("Question", result["sources"])
        generate.assert_not_called()
        self.assertEqual(result["answer"], "Checked answer")

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
            search.assert_called_once_with("Question", limit=10, document=None)
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
            search.assert_called_once_with("Question", limit=10, document=None)
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

        search.assert_called_once_with("Question", limit=10, document=None)
        rerank.assert_called_once_with("Question", candidates, limit=3)
        self.assertEqual([source["chunk_index"] for source in result["sources"]], [2, 0, 4, 1])
        grounded.assert_called_once_with("Question", result["sources"])

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
            search.assert_called_once_with("Question", limit=3, document=None)
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
            search.assert_called_once_with("Question", limit=candidate_limit, document="paper.pdf")
            self.assertEqual([source["document"] for source in result["sources"]], ["paper.pdf"])

    def test_no_matching_document_returns_empty_evidence_without_generation(self) -> None:
        with patch("app.rag.search_chunks", return_value=[]) as search, \
                patch("app.rag.rerank_chunks") as rerank, \
                patch("app.rag.generate") as generate, \
                patch("app.rag.grounded_answer") as grounded:
            result = answer_question("Question", document="missing.pdf")
        search.assert_called_once_with("Question", limit=10, document="missing.pdf")
        rerank.assert_not_called()
        generate.assert_not_called()
        grounded.assert_not_called()
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["answer"], INSUFFICIENT_EVIDENCE)

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
            "Main findings?", limit=10, document="paper.pdf", sections=("conclusion",),
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
            call("Main findings?", limit=10, document="paper.pdf", sections=sections)
            for sections in OVERVIEW_SECTION_PRIORITY
        ])
        self.assertEqual(result["answer"], "Reduced outcome")

    def test_every_paper_is_answered_independently_and_labelled(self) -> None:
        def scoped_answer(question: str, *, document: str, answer_mode: str,
                          overview: bool) -> dict[str, object]:
            return {"answer": f"Finding for {document}", "sources": [{
                "document": document, "page": 1, "chunk_index": 0,
                "text": f"Evidence for {document}",
            }]}

        with patch("app.rag.list_documents", return_value=["a.pdf", "b.pdf"]), \
                patch("app.rag.answer_question", side_effect=scoped_answer) as answer:
            result = answer_each_document("Main findings?", answer_mode="verified")
        self.assertEqual(answer.call_args_list, [
            call("Main findings?", document="a.pdf", answer_mode="verified", overview=True),
            call("Main findings?", document="b.pdf", answer_mode="verified", overview=True),
        ])
        self.assertIn("a.pdf:\nFinding for a.pdf", result["answer"])
        self.assertIn("b.pdf:\nFinding for b.pdf", result["answer"])
        self.assertEqual([source["document"] for source in result["sources"]], ["a.pdf", "b.pdf"])


if __name__ == "__main__":
    unittest.main()
