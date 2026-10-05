"""Real-browser smoke tests. Run separately; no PDFs or model services needed."""

import socket
import time
import unittest
from contextlib import ExitStack
from threading import Thread
from unittest.mock import patch

import httpx
import uvicorn
from playwright.sync_api import Browser, expect, sync_playwright

from app.llm.ollama import OLLAMA_URL
from app.main import app
from app.service_checks import ServiceCheck, ServiceStatus
from app.types import AnswerResult


ANSWER: AnswerResult = {
    "answer": "**Results** showed *improvement* (paper.pdf, page 2).\n<img src=x>",
    "sources": [{
        "document": "paper.pdf", "page": 2, "chunk_index": 0,
        "text": "The synthetic result improved. <script>throw new Error('unsafe')</script>",
        "section": "results",
    }],
    "claim_evidence": [{
        "text": "The synthetic result improved.",
        "attribution": "this_document_authors",
        "citations": [{"source_index": 0, "quote": "The synthetic result improved."}],
    }],
    "outcome": "answered",
}


class BrowserSmokeTests(unittest.TestCase):
    browser: Browser
    base_url: str

    @classmethod
    def setUpClass(cls) -> None:
        # Bind an ephemeral loopback port; never use or stop the user's server.
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        cls.addClassCleanup(listener.close)
        cls.base_url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)

        def stop_server() -> None:
            server.should_exit = True
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("Browser-test server did not stop")

        thread.start()
        cls.addClassCleanup(stop_server)
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("Browser-test server did not start")
            time.sleep(0.01)

        playwright = sync_playwright().start()
        cls.addClassCleanup(playwright.stop)
        # Missing browser binaries are a failure, not a silently skipped CI check.
        cls.browser = playwright.chromium.launch()
        cls.addClassCleanup(cls.browser.close)

    def setUp(self) -> None:
        patches = self.enterContext(ExitStack())
        self.documents = patches.enter_context(patch(
            "app.main.list_documents", return_value=["paper.pdf", "other.pdf"],
        ))
        patches.enter_context(patch("app.main.service_status", return_value=ServiceStatus(
            available=True,
            checks=[ServiceCheck(name=name, status="ok", message="Synthetic check passed.")
                    for name in ("database", "ollama", "answer_model", "embedding_model")],
        )))
        self.answer = patches.enter_context(patch("app.main.answer_question", return_value=ANSWER))
        self.each_answer = patches.enter_context(patch("app.main.answer_each_document", return_value=ANSWER))
        context = self.browser.new_context()
        self.addCleanup(context.close)
        # Exercise the actual button and rendered text without changing the host clipboard.
        context.add_init_script("""
            Object.defineProperty(navigator, "clipboard", {value: {
                writeText: async (text) => { window.copiedAnswer = text; }
            }});
        """)
        self.page = context.new_page()
        self.page.set_default_timeout(5000)
        self.page_errors: list[str] = []
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.goto(self.base_url)
        expect(self.page.locator("#document")).to_be_enabled()
        expect(self.page.locator("#service-status")).to_contain_text("Service checks passed")

    def tearDown(self) -> None:
        self.assertEqual(self.page_errors, [], "Unexpected browser JavaScript error")

    def test_question_evidence_links_and_clipboard(self) -> None:
        page = self.page
        expect(page.locator("#ask-button")).to_be_disabled()
        page.locator("#document").select_option("paper.pdf")
        page.locator("#question").fill("What happened?")
        page.locator("#ask-button").click()
        expect(page.locator("#request-status")).to_have_text("Answer ready.")
        self.answer.assert_called_once_with("What happened?", answer_mode="verified", document="paper.pdf")
        self.each_answer.assert_not_called()
        expect(page.locator("#answer-text strong")).to_have_text("Results")
        expect(page.locator("#answer-text em")).to_have_text("improvement")
        expect(page.locator("#answer-text img")).to_have_count(0)
        expect(page.locator("#answer-text")).to_contain_text("<img src=x>")
        expect(page.locator("#source-list script")).to_have_count(0)
        expect(page.locator("#evidence-panel")).to_be_visible()
        page.locator("#evidence-list summary").click()
        expect(page.locator("#evidence-list blockquote")).to_have_text("The synthetic result improved.")
        page.locator("#answer-text a").click()
        expect(page.locator("#source-list details")).to_have_attribute("open", "")
        expect(page.locator("#source-list .source-excerpt")).to_be_visible()
        page.locator("#copy-answer-button").click()
        expect(page.locator("#copy-status")).to_have_text("Answer copied.")
        self.assertEqual(page.evaluate("window.copiedAnswer"),
                         "Results showed improvement (paper.pdf, page 2).\n<img src=x>")

    def test_refusal_overview_and_refresh_on_narrow_viewport(self) -> None:
        page = self.page
        page.set_viewport_size({"width": 390, "height": 844})
        self.answer.return_value = {
            "answer": "I do not have enough evidence in the provided sources to answer this question.",
            "sources": ANSWER["sources"], "claim_evidence": [], "outcome": "insufficient_evidence",
        }
        page.locator("#question").fill("What were the main findings?")
        page.locator("#ask-button").click()
        expect(page.locator("#request-status")).to_have_text("Not enough evidence to answer.")
        expect(page.locator("#answer-guidance")).to_contain_text("Each paper (overview)")
        expect(page.locator("#evidence-panel")).to_be_hidden()
        expect(page.locator("#sources-panel")).to_be_visible()
        self.answer.assert_called_once_with("What were the main findings?", answer_mode="verified", document=None)

        self.each_answer.return_value = {**ANSWER, "outcome": "partial"}
        page.locator("#document").select_option("__each__")
        expect(page.locator("#scope-help")).to_contain_text("Use for main findings")
        self.documents.return_value = ["paper.pdf", "other.pdf", "new.pdf"]
        page.locator("#refresh-papers-button").click()
        expect(page.locator('#document option[value="new.pdf"]')).to_have_count(1)
        expect(page.locator("#document")).to_have_value("__each__")
        expect(page.locator("#question")).to_have_value("What were the main findings?")
        page.locator("#ask-button").click()
        expect(page.locator("#request-status")).to_have_text("Some papers could not be answered.")
        self.each_answer.assert_called_once_with("What were the main findings?", answer_mode="verified", overview=True)
        expect(page.locator("#answer-guidance")).to_contain_text("At least one paper")

    def test_dependency_error_allows_retry(self) -> None:
        self.answer.side_effect = [
            httpx.ConnectError("Synthetic offline model", request=httpx.Request("POST", OLLAMA_URL)),
            ANSWER,
        ]
        page = self.page
        page.locator("#question").fill("What happened?")
        page.locator("#ask-button").click()
        expect(page.locator("#request-error")).to_contain_text("Could not communicate with Ollama")
        expect(page.locator("#answer-panel")).to_be_hidden()
        expect(page.locator("#ask-button")).to_be_enabled()
        page.locator("#ask-button").click()
        expect(page.locator("#request-status")).to_have_text("Answer ready.")
        expect(page.locator("#request-error")).to_be_hidden()
        self.assertEqual(self.answer.call_count, 2)


if __name__ == "__main__":
    unittest.main()
