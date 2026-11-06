"""Evaluation regressions; no application database or provider calls."""
import unittest

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


if __name__ == "__main__":
    unittest.main()
