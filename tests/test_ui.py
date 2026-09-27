import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class BrowserUiTests(unittest.TestCase):
    def test_home_serves_labeled_query_form_and_result_regions(self) -> None:
        response = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)).get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        for fragment in [
            '<form id="query-form">',
            '<label for="document">',
            '<label for="question">',
            'id="request-error" class="request-error" role="alert"',
            'id="source-list"',
            'src="/static/app.js?v=7"',
            'Each paper (overview)',
            'Each paper (targeted search)',
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, response.text)
        self.assertNotIn('class="step"', response.text)

    def test_browser_assets_and_local_api_docs_are_served(self) -> None:
        client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))
        script = client.get("/static/app.js?v=7")
        stylesheet = client.get("/static/styles.css?v=3")
        docs = client.get("/docs")
        self.assertEqual(script.status_code, 200)
        self.assertIn("javascript", script.headers["content-type"])
        self.assertEqual(stylesheet.status_code, 200)
        self.assertIn("text/css", stylesheet.headers["content-type"])
        self.assertEqual(docs.status_code, 200)
        self.assertIn("/openapi.json", docs.text)
        self.assertNotIn("<script", docs.text)
        self.assertNotIn("cdn.", docs.text)
        self.assertEqual(client.get("/redoc").status_code, 404)
        self.assertEqual(client.get("/docs/oauth2-redirect").status_code, 404)
        self.assertEqual(client.get("/openapi.json").status_code, 200)

        with patch("app.main.list_documents", return_value=["paper.pdf"]):
            self.assertEqual(client.get("/documents").json(), ["paper.pdf"])
        with patch("app.main.answer_question", return_value={"answer": "Supported answer", "sources": []}):
            response = client.post("/query", json={"question": "What happened?"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "Supported answer", "sources": []})


if __name__ == "__main__":
    unittest.main()
