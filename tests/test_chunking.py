import unittest

from app.ingestion.chunking import chunk_pages
from app.types import PageData


def page(text: str, document: str = "paper.pdf", number: int = 7) -> PageData:
    return {"document": document, "page": number, "text": text}


class ChunkingTests(unittest.TestCase):
    def test_preserves_numerical_context_and_avoids_decimal_sentence_split(self) -> None:
        text = (
            "Food-restricted mice lost 1.2 g (− 3.9%) body weight\n"
            "on average after 3 days, compared to controls. The next result followed."
        )

        chunks = chunk_pages([page(text)], chunk_size=65, overlap=10)

        self.assertIn("− 3.9%) body weight", "".join(chunk["text"] for chunk in chunks))
        self.assertTrue(all(not chunk["text"].startswith("9%)") for chunk in chunks))
        self.assertTrue(all(len(chunk["text"]) <= 65 for chunk in chunks))
        self.assertTrue(chunks[0]["text"].startswith("Food-restricted"))
        self.assertTrue(any(chunk["text"].endswith("controls.") for chunk in chunks))

    def test_keeps_a_numerical_sentence_whole_when_it_fits(self) -> None:
        sentence = "Mice lost 1.2 g (− 3.9%) body weight."
        chunks = chunk_pages([page(sentence + " More results followed.")], len(sentence), 0)

        self.assertEqual(chunks[0]["text"], sentence)

    def test_zero_overlap_reconstructs_page_without_repeated_text(self) -> None:
        text = "First sentence. Second sentence has more words. Third sentence."
        chunks = chunk_pages([page(text)], chunk_size=21, overlap=0)

        self.assertEqual("".join(chunk["text"] for chunk in chunks), text)

    def test_small_overlap_does_not_split_numeric_or_figure_context(self) -> None:
        text = "Weight changed by − 3.9%) body weight. See Fig. 3 for the result. More text follows."
        chunks = chunk_pages([page(text)], chunk_size=29, overlap=2)

        self.assertTrue(all(not chunk["text"].startswith("9%)") for chunk in chunks))
        self.assertTrue(all(not chunk["text"].startswith("3 for the result") for chunk in chunks))

    def test_page_chunk_indices_restart_and_size_one_makes_progress(self) -> None:
        chunks = chunk_pages([page("abcdef", number=1), page("gh", number=2)], chunk_size=1, overlap=0)

        self.assertEqual([chunk["chunk_index"] for chunk in chunks], [0, 1, 2, 3, 4, 5, 0, 1])
        self.assertEqual("".join(chunk["text"] for chunk in chunks), "abcdefgh")

    def test_preserves_exact_substrings_coverage_overlap_and_page_metadata(self) -> None:
        text = "Alpha first sentence.\nBeta second sentence has more words. Gamma third."
        chunks = chunk_pages([page(text, "source.pdf", 12)], chunk_size=29, overlap=8)

        self.assertTrue(chunks)
        self.assertTrue(all(chunk["text"] in text for chunk in chunks))
        # The raw slices cover the source continuously; overlap may repeat text.
        covered_end = 0
        previous_start = -1
        has_overlap = False
        for chunk in chunks:
            fragment = chunk["text"]
            position = text.find(fragment, previous_start + 1)
            self.assertGreaterEqual(position, 0)
            self.assertLessEqual(position, covered_end)
            has_overlap = has_overlap or position < covered_end
            new_end = position + len(fragment)
            self.assertGreater(new_end, covered_end)
            covered_end = new_end
            previous_start = position
        self.assertEqual(covered_end, len(text))
        self.assertEqual([chunk["chunk_index"] for chunk in chunks], list(range(len(chunks))))
        self.assertTrue(all(chunk["document"] == "source.pdf" and chunk["page"] == 12 for chunk in chunks))
        self.assertTrue(has_overlap)

    def test_breaks_long_sentences_at_whitespace_and_long_tokens_at_size_limit(self) -> None:
        sentence = "word " * 20 + "finish"
        token = "x" * 53

        sentence_chunks = chunk_pages([page(sentence)], chunk_size=17, overlap=3)
        token_chunks = chunk_pages([page(token)], chunk_size=10, overlap=2)

        self.assertTrue(all(len(chunk["text"]) <= 17 for chunk in sentence_chunks))
        self.assertTrue(sentence.startswith(sentence_chunks[0]["text"]))
        self.assertTrue(all(len(chunk["text"]) <= 10 for chunk in token_chunks))
        self.assertTrue(all(chunk["text"] and set(chunk["text"]) == {"x"} for chunk in token_chunks))
        self.assertLess(max(chunk["chunk_index"] for chunk in token_chunks), len(token))

    def test_rejects_invalid_chunk_settings(self) -> None:
        for chunk_size, overlap in [(0, 0), (-1, 0), (10, -1), (10, 10), (10, 11)]:
            with self.subTest(chunk_size=chunk_size, overlap=overlap):
                with self.assertRaises(ValueError):
                    chunk_pages([page("some text")], chunk_size=chunk_size, overlap=overlap)

    def test_skips_empty_or_whitespace_only_pages(self) -> None:
        for text in ("", "  \n\t  "):
            with self.subTest(text=repr(text)):
                self.assertEqual(chunk_pages([page(text)]), [])

    def test_empty_page_list_returns_no_chunks(self) -> None:
        self.assertEqual(chunk_pages([]), [])


if __name__ == "__main__":
    unittest.main()
