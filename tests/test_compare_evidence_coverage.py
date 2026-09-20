from contextlib import redirect_stderr
from hashlib import sha256
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.compare_evidence_coverage import main


class CoverageRunnerTests(unittest.TestCase):
    def test_unanswerable_only_benchmark_rejected_before_services_or_output(self) -> None:
        manifest = json.loads(Path("benchmarks/housing-temperature-2025.json").read_text())
        manifest["cases"] = [case for case in manifest["cases"] if not case["answerable"]]
        manifest["metadata"]["paper_sha256"] = sha256(b"paper").hexdigest()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            benchmark = root / "benchmark.json"
            benchmark.write_text(json.dumps(manifest))
            paper = root / "housing-temperature.pdf"
            paper.write_bytes(b"paper")
            output = root / "coverage.json"
            with (
                patch("sys.argv", ["compare_evidence_coverage", "--benchmark", str(benchmark),
                                   "--pdf", str(paper), "--output", str(output)]),
                patch("scripts.compare_evidence_coverage.extract_pages") as extract,
                patch("scripts.compare_evidence_coverage.snapshot") as snapshot,
                patch("scripts.compare_evidence_coverage.compare_case") as compare,
                patch("scripts.compare_evidence_coverage.reserve_output") as reserve,
                redirect_stderr(io.StringIO()) as stderr,
                self.assertRaises(SystemExit) as error,
            ):
                main()
            self.assertEqual(error.exception.code, 2)
            self.assertIn("requires at least one answerable case", stderr.getvalue())
            extract.assert_not_called()
            snapshot.assert_not_called()
            compare.assert_not_called()
            reserve.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
