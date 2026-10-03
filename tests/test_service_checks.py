import unittest
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.db.database import Base
from app.db.models import DocumentIndex
from app.main import app
from app.service_checks import (
    CHECK_TIMEOUT_SECONDS, OLLAMA_TAGS_URL, ServiceCheck, ServiceStatus,
    check_database, check_ollama, model_tag, service_status,
)


class ServiceCheckTests(unittest.TestCase):
    def test_database_probe_checks_schema_without_reading_or_changing_papers(self) -> None:
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        with patch("app.service_checks.create_engine", return_value=engine) as factory:
            check = check_database()
        self.assertEqual(check.status, "ok")
        self.assertEqual(factory.call_args.kwargs["poolclass"], NullPool)
        self.assertEqual(factory.call_args.kwargs["connect_args"]["connect_timeout"], CHECK_TIMEOUT_SECONDS)
        self.assertIn("statement_timeout=3000", factory.call_args.kwargs["connect_args"]["options"])

    def test_missing_schema_reports_setup_guidance_and_disposes_probe(self) -> None:
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with patch("app.service_checks.create_engine", return_value=engine), patch.object(engine, "dispose", wraps=engine.dispose) as dispose:
            check = check_database()
        self.assertEqual(check.status, "error")
        self.assertIn("scripts.init_db", check.message)
        self.assertNotIn("SELECT", check.message)
        dispose.assert_called_once_with()

    def test_schema_probe_requires_the_provenance_table(self) -> None:
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        DocumentIndex.__table__.drop(engine)
        with patch("app.service_checks.create_engine", return_value=engine):
            check = check_database()
        self.assertEqual(check.status, "error")
        self.assertIn("scripts.init_db", check.message)

    def test_unreachable_database_is_redacted_and_does_not_skip_ollama_checks(self) -> None:
        from sqlalchemy.exc import OperationalError
        engine = MagicMock()
        engine.connect.side_effect = OperationalError("private SQL", {}, Exception("secret-password"))
        model_checks = [ServiceCheck(name="ollama", status="ok", message="Accessible")]
        with patch("app.service_checks.create_engine", return_value=engine), \
                patch("app.service_checks.check_ollama", return_value=model_checks) as ollama:
            result = service_status()
        self.assertFalse(result.available)
        self.assertNotIn("secret-password", result.model_dump_json())
        self.assertNotIn("private SQL", result.model_dump_json())
        ollama.assert_called_once_with()
        engine.dispose.assert_called_once_with()

    def test_installed_models_include_implicit_latest_tags_without_inference(self) -> None:
        response = httpx.Response(200, request=httpx.Request("GET", OLLAMA_TAGS_URL), json={
            "models": [{"name": "gpt-oss:20b"}, {"name": "nomic-embed-text:latest"}],
        })
        with patch("app.service_checks.httpx.get", return_value=response) as get, \
                patch("app.service_checks.GROUNDING_MODEL", "gpt-oss:20b"), \
                patch("app.service_checks.httpx.post") as inference:
            checks = check_ollama()
        self.assertEqual([check.status for check in checks], ["ok", "ok", "ok"])
        get.assert_called_once_with(OLLAMA_TAGS_URL, timeout=CHECK_TIMEOUT_SECONDS)
        inference.assert_not_called()
        self.assertEqual(model_tag("registry:5000/models/custom"), "registry:5000/models/custom:latest")

    def test_missing_models_use_exact_configured_tags_and_pull_guidance(self) -> None:
        response = httpx.Response(200, request=httpx.Request("GET", OLLAMA_TAGS_URL), json={
            "models": [{"name": "gpt-oss:120b"}],
        })
        with patch("app.service_checks.httpx.get", return_value=response), \
                patch("app.service_checks.GROUNDING_MODEL", "gpt-oss:20b"):
            checks = check_ollama()
        self.assertEqual([check.status for check in checks], ["ok", "error", "error"])
        self.assertIn("ollama pull gpt-oss:20b", checks[1].message)
        self.assertIn("ollama pull nomic-embed-text", checks[2].message)

    def test_unavailable_or_malformed_ollama_metadata_leaves_model_status_unknown(self) -> None:
        request = httpx.Request("GET", OLLAMA_TAGS_URL)
        cases: list[httpx.Response | Exception] = [
            httpx.ConnectError("private host info", request=request),
            httpx.ReadTimeout("private host info", request=request),
            httpx.Response(500, request=request, text="private response body"),
            httpx.Response(200, request=request, text="not JSON"),
            httpx.Response(200, request=request, json={"models": "bad"}),
            httpx.Response(200, request=request, json={"models": [None]}),
        ]
        for case in cases:
            with self.subTest(case=case), patch("app.service_checks.httpx.get") as get:
                if isinstance(case, Exception):
                    get.side_effect = case
                else:
                    get.return_value = case
                checks = check_ollama()
            self.assertEqual([check.status for check in checks], ["error", "unknown", "unknown"])
            self.assertNotIn("private", " ".join(check.message for check in checks))

    def test_status_endpoint_returns_diagnostics_and_preserves_local_access_boundary(self) -> None:
        result = ServiceStatus(available=False, checks=[
            ServiceCheck(name="database", status="error", message="Check PostgreSQL"),
        ])
        client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))
        with patch("app.main.service_status", return_value=result) as check:
            response = client.get("/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result.model_dump())
        check.assert_called_once_with()
        remote = TestClient(app, base_url="http://127.0.0.1", client=("192.0.2.1", 50000))
        with patch("app.main.service_status") as check:
            self.assertEqual(remote.get("/status").status_code, 403)
            self.assertEqual(client.get("/status", headers={"Host": "attacker.example"}).status_code, 400)
        check.assert_not_called()
