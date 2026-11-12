import json
import os
import unittest
from unittest.mock import MagicMock, patch

from app.services.semantic_emergency_service import screen_semantic_emergency


class SemanticEmergencyTests(unittest.TestCase):

    def setUp(self):
        self.env = patch.dict(os.environ, {
            "SEMANTIC_EMERGENCY_SCREENING_ENABLED": "true",
            "AZURE_OPENAI_EMERGENCY_DEPLOYMENT": "emergency-screening",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def mock_client(self, payload):
        client = MagicMock()
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=json.dumps(payload)))
        ]
        return client

    def test_disabled_returns_none(self):
        with patch.dict(os.environ, {
            "SEMANTIC_EMERGENCY_SCREENING_ENABLED": "false"
        }):
            self.assertIsNone(
                screen_semantic_emergency("I feel unwell")
            )

    def test_potential_emergency(self):
        client = self.mock_client({
            "status": "POTENTIAL_EMERGENCY",
            "category": "CHEST_PAIN",
        })
        with patch(
            "app.services.semantic_emergency_service._build_client",
            return_value=client,
        ):
            result = screen_semantic_emergency(
                "It feels like an elephant is sitting on my chest."
            )

        self.assertEqual(result.status, "POTENTIAL_EMERGENCY")
        self.assertIn("emergency", result.reply.lower())
        client.close.assert_called_once()

    def test_normal_message(self):
        client = self.mock_client({
            "status": "NORMAL",
            "category": "NONE",
        })
        with patch(
            "app.services.semantic_emergency_service._build_client",
            return_value=client,
        ):
            result = screen_semantic_emergency(
                "I need to book a check-up."
            )

        self.assertEqual(result.status, "NORMAL")

    def test_invalid_output_fails_closed(self):
        client = self.mock_client({
            "status": "MAYBE",
            "category": "NONE",
        })
        with patch(
            "app.services.semantic_emergency_service._build_client",
            return_value=client,
        ):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")

    def test_missing_deployment_fails_closed(self):
        with patch.dict(os.environ, {
            "AZURE_OPENAI_EMERGENCY_DEPLOYMENT": ""
        }):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")

    def test_provider_error_fails_closed(self):
        with patch(
            "app.services.semantic_emergency_service._build_client",
            side_effect=RuntimeError("not configured"),
        ):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")

    def test_missing_endpoint_or_api_key_fails_closed(self):
        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "",
            "AZURE_OPENAI_API_KEY": "",
        }, clear=False):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")

    def test_normal_status_with_emergency_category_fails_closed(self):
        client = self.mock_client({
            "status": "NORMAL",
            "category": "CHEST_PAIN",
        })
        with patch(
            "app.services.semantic_emergency_service._build_client",
            return_value=client,
        ):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")
        client.close.assert_called_once()

    def test_potential_emergency_with_none_category_fails_closed(self):
        client = self.mock_client({
            "status": "POTENTIAL_EMERGENCY",
            "category": "NONE",
        })
        with patch(
            "app.services.semantic_emergency_service._build_client",
            return_value=client,
        ):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")
        client.close.assert_called_once()

    def test_malformed_json_fails_closed_and_closes_client(self):
        client = MagicMock()
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="not valid json"))
        ]
        with patch(
            "app.services.semantic_emergency_service._build_client",
            return_value=client,
        ):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")
        client.close.assert_called_once()

    def test_empty_model_response_fails_closed_and_closes_client(self):
        client = MagicMock()
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=None))
        ]
        with patch(
            "app.services.semantic_emergency_service._build_client",
            return_value=client,
        ):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")
        client.close.assert_called_once()

    def test_provider_timeout_fails_closed_and_closes_client(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = TimeoutError("request timed out")
        with patch(
            "app.services.semantic_emergency_service._build_client",
            return_value=client,
        ):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")
        client.close.assert_called_once()

    def test_provider_authentication_error_fails_closed_and_closes_client(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError(
            "provider authentication failed"
        )
        with patch(
            "app.services.semantic_emergency_service._build_client",
            return_value=client,
        ):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")
        client.close.assert_called_once()

    def test_malformed_json_fails_closed_and_closes_client(self):
        client = MagicMock()
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="not valid json"))
        ]
        with patch(
            "app.services.semantic_emergency_service._build_client",
            return_value=client,
        ):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")
        client.close.assert_called_once()

    def test_empty_model_response_fails_closed_and_closes_client(self):
        client = MagicMock()
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=None))
        ]
        with patch(
            "app.services.semantic_emergency_service._build_client",
            return_value=client,
        ):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")
        client.close.assert_called_once()

    def test_provider_timeout_fails_closed_and_closes_client(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = TimeoutError("request timed out")
        with patch(
            "app.services.semantic_emergency_service._build_client",
            return_value=client,
        ):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")
        client.close.assert_called_once()

    def test_provider_authentication_error_fails_closed_and_closes_client(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = RuntimeError(
            "provider authentication failed"
        )
        with patch(
            "app.services.semantic_emergency_service._build_client",
            return_value=client,
        ):
            result = screen_semantic_emergency("I feel strange.")

        self.assertEqual(result.status, "UNCERTAIN")
        client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
