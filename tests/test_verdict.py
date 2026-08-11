import unittest

from completion_verifier.verdict import Verdict, overall_verdict


class VerdictTests(unittest.TestCase):
    def test_all_pass_is_pass(self) -> None:
        self.assertEqual(overall_verdict([Verdict.PASS, Verdict.PASS]), Verdict.PASS)

    def test_precedence_is_fail_blocked_unproven_pass(self) -> None:
        self.assertEqual(
            overall_verdict([Verdict.UNPROVEN, Verdict.BLOCKED]), Verdict.BLOCKED
        )
        self.assertEqual(
            overall_verdict([Verdict.BLOCKED, Verdict.FAIL]), Verdict.FAIL
        )

    def test_empty_verdicts_are_invalid(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one verdict"):
            overall_verdict([])
