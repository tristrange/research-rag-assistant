import unittest

from fastapi.testclient import TestClient

from app.main import app


class BrowserUiTests(unittest.TestCase):
    def test_home_serves_labeled_query_form_and_result_regions(self) -> None:
        response = TestClient(app).get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        for fragment in [
            '<form id="query-form">',
            '<label for="document">',
            '<label for="question">',
            '<label for="answer-mode">',
            'id="request-error" class="request-error" role="alert"',
            'id="source-list"',
            'src="/static/app.js"',
        ]:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, response.text)

    def test_browser_assets_and_api_docs_are_served(self) -> None:
        client = TestClient(app)
        script = client.get("/static/app.js")
        stylesheet = client.get("/static/styles.css")
        docs = client.get("/docs")
        self.assertEqual(script.status_code, 200)
        self.assertIn("javascript", script.headers["content-type"])
        self.assertEqual(stylesheet.status_code, 200)
        self.assertIn("text/css", stylesheet.headers["content-type"])
        self.assertEqual(docs.status_code, 200)


if __name__ == "__main__":
    unittest.main()
