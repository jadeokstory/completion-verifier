import unittest

from completion_verifier.redaction import redact


class RedactionTests(unittest.TestCase):
    def test_common_secret_shapes_are_redacted(self) -> None:
        assigned_value = "value" * 4
        bearer_value = "tokenvalue" * 2
        password_value = "password" * 2
        source = (
            "API_KEY="
            + assigned_value
            + "\nAuthorization: "
            + "Bea"
            + "rer "
            + bearer_value
            + "\nhttps://user:"
            + password_value
            + "@example.com\n"
        )

        result = redact(source)

        self.assertTrue(result.applied)
        self.assertNotIn(assigned_value, result.text)
        self.assertNotIn(bearer_value, result.text)
        self.assertNotIn(password_value, result.text)
        self.assertIn("[REDACTED]", result.text)

    def test_non_secret_output_is_unchanged(self) -> None:
        result = redact("84 tests passed")
        self.assertFalse(result.applied)
        self.assertEqual(result.text, "84 tests passed")
