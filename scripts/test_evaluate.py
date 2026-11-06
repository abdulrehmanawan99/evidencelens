"""Evaluation regressions; no application database or provider calls."""
import unittest
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import evaluate

from evaluate import score_evidence


class EvidenceScoreTests(unittest.TestCase):
    def setUp(self):
        self.passages = {"p1": "The total was 42 units. Earlier forecasts were provisional."}
        self.expected = [{"text": "The total was 42 units", "relation": "supports"}]

    def test_retrieved_fact_is_not_credit_for_an_unrelated_returned_quote(self):
        findings = [{"passage_id": "p1", "quote": "Earlier forecasts were provisional.", "relation": "supports"}]
        score = score_evidence(findings, self.passages, self.expected)
        self.assertTrue(score["citations_valid"])
        self.assertEqual(score["retrieval_recalled"], 1)
        self.assertEqual(score["evidence_matched"], 0)

    def test_exact_returned_quote_and_relation_receive_credit(self):
        findings = [{"passage_id": "p1", "quote": "The total was 42 units.", "relation": "supports"}]
        score = score_evidence(findings, self.passages, self.expected)
        self.assertTrue(score["citations_valid"])
        self.assertEqual(score["evidence_matched"], 1)
        findings[0]["relation"] = "conflicts"
        self.assertEqual(score_evidence(findings, self.passages, self.expected)["evidence_matched"], 0)

    def test_invalid_or_out_of_context_quotes_never_receive_credit(self):
        for passage_id, quote in (("p2", "The total was 42 units."), ("p1", "The total was 42 units, final."), ("p1", "")):
            with self.subTest(passage_id=passage_id, quote=quote):
                findings = [{"passage_id": passage_id, "quote": quote, "relation": "supports"}]
                score = score_evidence(findings, self.passages, self.expected)
                self.assertFalse(score["citations_valid"])
                self.assertEqual(score["evidence_matched"], 0)

    def test_no_evidence_case_has_zero_recall_counts(self):
        score = score_evidence([], self.passages, [])
        self.assertTrue(score["citations_valid"])
        self.assertEqual(score["evidence_matched"], 0)
        self.assertEqual(score["relevant_passages"], 0)


class BoundedEvaluationTests(unittest.TestCase):
    def test_first_failed_live_case_stops_other_cases_and_persists_report(self):
        investigated = []
        def response(request, timeout=30):
            path = request.full_url.split("/api/v1", 1)[1]
            if path == "/provider-status":
                value = {"mode": "openai_compatible", "configured": True, "provider": "test-model", "embedding": {"provider": "local_lexical"}}
            elif path.startswith("/sample"):
                value = {"id": "evaluation-only"}
            elif path.endswith("/documents"):
                value = {"items": [{"state": "ready"}]}
            elif path.endswith("/investigations"):
                investigated.append(path)
                value = {"id": "run", "job": {"id": "job", "state": "failed", "error_code": "provider_rate_limited"}}
            elif request.get_method() == "DELETE":
                value = {"id": "cleanup", "state": "succeeded"}
            else:
                self.fail("Unexpected API action: " + path)
            return BytesIO(json.dumps(value).encode())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            args = ["evaluate.py", "--suite", "live", "--format", "txt", "--output", str(output)]
            with patch("sys.argv", args), patch.object(evaluate, "urlopen", response), redirect_stdout(StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    evaluate.main()
            report = json.loads(output.read_text())
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(len(investigated), 1)
        self.assertEqual(len(report["results"]), 1)
        self.assertEqual(report["results"][0]["error"], "provider_rate_limited")
        self.assertIn("not attempted", report["stopped_reason"])


if __name__ == "__main__":
    unittest.main()
