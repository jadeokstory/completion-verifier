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

    def test_aws_credentials_and_database_urls_are_redacted(self) -> None:
        aws_secret = "FAKE" + "awsSecretValue" + "1234567890"
        database_password = "FAKE" + "dbPassword"
        source = (
            "AWS_SECRET_ACCESS_KEY="
            + aws_secret
            + "\nDATABASE_URL=postgres://user:"
            + database_password
            + "@localhost/db\n"
        )

        result = redact(source)

        self.assertTrue(result.applied)
        self.assertNotIn(aws_secret, result.text)
        self.assertNotIn(database_password, result.text)
        self.assertEqual(result.text.count("[REDACTED]"), 2)

    def test_non_http_uri_password_is_redacted(self) -> None:
        password = "credential" * 2
        result = redact(f"postgres://user:{password}@localhost/db")

        self.assertTrue(result.applied)
        self.assertNotIn(password, result.text)
        self.assertEqual(
            result.text, "postgres://user:[REDACTED]@localhost/db"
        )

    def test_quoted_json_credentials_are_redacted(self) -> None:
        password = "quoted-secret-value"
        token = "quoted-access-token"
        result = redact(
            '{"password": "'
            + password
            + '", "access_token": "'
            + token
            + '"}'
        )

        self.assertTrue(result.applied)
        self.assertNotIn(password, result.text)
        self.assertNotIn(token, result.text)
        self.assertEqual(result.text.count("[REDACTED]"), 2)

    def test_basic_authorization_is_redacted(self) -> None:
        credentials = "dXNlcjpwYXNzd29yZA=="
        result = redact("Authorization: Basic " + credentials)

        self.assertTrue(result.applied)
        self.assertNotIn(credentials, result.text)

    def test_multiline_private_key_is_redacted(self) -> None:
        key_body = "synthetic-key-material"
        begin = "-----BE" + "GIN PRIVATE KEY-----"
        end = "-----E" + "ND PRIVATE KEY-----"
        source = "before\n" + begin + "\n" + key_body + "\n" + end + "\nafter"
        result = redact(source)

        self.assertTrue(result.applied)
        self.assertNotIn(key_body, result.text)
        self.assertEqual(result.text, "before\n[REDACTED]\nafter")
