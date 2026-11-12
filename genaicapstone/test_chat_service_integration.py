"""Integration tests for the two-layer screening in process_chat().

External boundaries (SQL session storage, Azure OpenAI, and Foundry) are mocked;
the real process_chat() function and deterministic screening rules are exercised.
"""

import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# The SQL driver is an infrastructure dependency. Keep it out of these
# control-flow tests by providing only the import symbol used by db.py.
if "mssql_python" not in sys.modules:
    try:
        import mssql_python  # noqa: F401
    except ImportError:
        mssql_python = types.ModuleType("mssql_python")
        mssql_python.connect = MagicMock(name="unused_sql_connect")
        sys.modules["mssql_python"] = mssql_python

# Foundry SDKs are also external infrastructure dependencies. These tests
# replace open_foundry_client/send_chat_turn and never instantiate this client.
try:
    import azure.ai.projects  # noqa: F401
except ImportError:
    azure = types.ModuleType("azure")
    azure.__path__ = []
    azure_ai = types.ModuleType("azure.ai")
    azure_ai.__path__ = []
    azure_projects = types.ModuleType("azure.ai.projects")
    azure_projects.AIProjectClient = MagicMock(name="unused_AIProjectClient")
    azure_identity = types.ModuleType("azure.identity")
    azure_identity.ClientSecretCredential = MagicMock(
        name="unused_ClientSecretCredential"
    )
    sys.modules.setdefault("azure", azure)
    sys.modules.setdefault("azure.ai", azure_ai)
    sys.modules.setdefault("azure.ai.projects", azure_projects)
    sys.modules.setdefault("azure.identity", azure_identity)

from app.services import chat_service
from app.services.semantic_emergency_service import SemanticSafetyResult


class ProcessChatSafetyIntegrationTests(unittest.TestCase):
    CUSTOMER = {"customer_id": "customer-123"}
    SESSION_ID = "session-123"
    APPOINTMENT_MESSAGE = "I'd like to book a routine check-up appointment."

    def setUp(self):
        self.connection = MagicMock(name="sql_connection")
        self.session_context = {}
        self.chat_session_context_manager = MagicMock(
            name="open_chat_session_context"
        )
        self.chat_session_context_manager.__enter__.return_value = (
            self.connection,
            self.session_context,
        )

    def _open_chat_session_patch(self):
        return patch.object(
            chat_service,
            "open_chat_session",
            return_value=self.chat_session_context_manager,
        )

    def _foundry_mocks(self):
        client = MagicMock(name="foundry_client")
        client.conversations.create.return_value.id = "conversation-123"
        client_context_manager = MagicMock(name="foundry_context_manager")
        client_context_manager.__enter__.return_value = client
        return client, client_context_manager

    def _assert_foundry_was_not_started(self, workflow_mock, foundry_mock):
        workflow_mock.assert_not_called()
        foundry_mock.assert_not_called()

    def test_deterministic_emergency_short_circuits_both_later_layers(self):
        """A rule-based emergency wins; semantic screening and Foundry are skipped."""
        with (
            self._open_chat_session_patch(),
            patch.object(
                chat_service,
                "screen_semantic_emergency",
            ) as semantic_screening,
            patch.object(chat_service, "get_session_workflow") as workflow,
            patch.object(chat_service, "open_foundry_client") as foundry,
        ):
            result = chat_service.process_chat(
                self.CUSTOMER,
                self.SESSION_ID,
                "I have chest pain right now.",
            )

        self.assertEqual(result["safety_status"], "POTENTIAL_EMERGENCY")
        self.assertEqual(result["safety_category"], "CHEST_PAIN")
        self.assertIsNone(result["response_id"])
        self.assertEqual(result["tool_calls"], [])
        self.assertIsNone(result["current_workflow"])
        self.assertIn("emergency", result["reply"].lower())
        semantic_screening.assert_not_called()
        self._assert_foundry_was_not_started(workflow, foundry)

    def test_semantic_potential_emergency_stops_foundry_flow(self):
        """An indirect symptom not matched by regex is escalated by semantic screening."""
        message = "It feels like an elephant is sitting on my chest."
        self.assertIsNone(chat_service.screen_emergency(message))
        semantic_result = SemanticSafetyResult(
            status="POTENTIAL_EMERGENCY",
            category="CHEST_PAIN",
            reply="Seek immediate emergency medical care.",
        )

        with (
            self._open_chat_session_patch(),
            patch.object(
                chat_service,
                "screen_semantic_emergency",
                return_value=semantic_result,
            ) as semantic_screening,
            patch.object(chat_service, "get_session_workflow") as workflow,
            patch.object(chat_service, "open_foundry_client") as foundry,
        ):
            result = chat_service.process_chat(
                self.CUSTOMER,
                self.SESSION_ID,
                message,
            )

        self.assertEqual(result["safety_status"], "POTENTIAL_EMERGENCY")
        self.assertEqual(result["safety_category"], "CHEST_PAIN")
        self.assertEqual(result["reply"], semantic_result.reply)
        semantic_screening.assert_called_once_with(message)
        self._assert_foundry_was_not_started(workflow, foundry)

    def test_uncertain_semantic_classification_fails_closed(self):
        """UNCERTAIN is a safety response, never a route to Foundry."""
        message = "Something feels wrong, but I cannot explain it clearly."
        semantic_result = SemanticSafetyResult(
            status="UNCERTAIN",
            category="OTHER",
            reply="Seek urgent medical help if symptoms may be severe.",
        )

        with (
            self._open_chat_session_patch(),
            patch.object(
                chat_service,
                "screen_semantic_emergency",
                return_value=semantic_result,
            ) as semantic_screening,
            patch.object(chat_service, "get_session_workflow") as workflow,
            patch.object(chat_service, "open_foundry_client") as foundry,
        ):
            result = chat_service.process_chat(
                self.CUSTOMER,
                self.SESSION_ID,
                message,
            )

        self.assertEqual(result["safety_status"], "UNCERTAIN")
        self.assertEqual(result["safety_category"], "OTHER")
        self.assertEqual(result["reply"], semantic_result.reply)
        semantic_screening.assert_called_once_with(message)
        self._assert_foundry_was_not_started(workflow, foundry)

    def test_normal_message_runs_existing_foundry_workflow(self):
        """NORMAL passes both safety layers and executes the normal Foundry path."""
        semantic_result = SemanticSafetyResult(
            status="NORMAL",
            category="NONE",
            reply="",
        )
        client, foundry_context_manager = self._foundry_mocks()
        foundry_reply = {
            "reply": "I can help you find an appointment.",
            "response_id": "response-123",
            "tool_calls": [],
        }

        with (
            patch.dict(
                os.environ,
                {"SEMANTIC_EMERGENCY_SCREENING_ENABLED": "true"},
            ),
            self._open_chat_session_patch(),
            patch.object(
                chat_service,
                "screen_semantic_emergency",
                return_value=semantic_result,
            ) as semantic_screening,
            patch.object(
                chat_service,
                "get_session_workflow",
                return_value="BOOK",
            ) as workflow,
            patch.object(
                chat_service,
                "open_foundry_client",
                return_value=foundry_context_manager,
            ) as foundry,
            patch.object(
                chat_service,
                "save_conversation_reference",
            ) as save_conversation,
            patch.object(
                chat_service,
                "send_chat_turn",
                return_value=foundry_reply,
            ) as send_turn,
            patch.object(
                chat_service,
                "verify_session_still_active",
            ) as verify_session,
        ):
            result = chat_service.process_chat(
                self.CUSTOMER,
                self.SESSION_ID,
                self.APPOINTMENT_MESSAGE,
            )

        semantic_screening.assert_called_once_with(self.APPOINTMENT_MESSAGE)
        workflow.assert_called_once_with(
            session_id=self.SESSION_ID,
            customer_id=self.CUSTOMER["customer_id"],
        )
        foundry.assert_called_once_with()
        client.conversations.create.assert_called_once_with()
        save_conversation.assert_called_once_with(
            connection=self.connection,
            session_id=self.SESSION_ID,
            customer_id=self.CUSTOMER["customer_id"],
            conversation_id="conversation-123",
        )
        send_turn.assert_called_once_with(
            client=client,
            conversation_id="conversation-123",
            message=self.APPOINTMENT_MESSAGE,
            current_workflow="BOOK",
        )
        verify_session.assert_called_once_with(
            connection=self.connection,
            session_id=self.SESSION_ID,
            customer_id=self.CUSTOMER["customer_id"],
        )
        self.assertEqual(result["safety_status"], "NORMAL")
        self.assertIsNone(result["safety_category"])
        self.assertEqual(result["current_workflow"], "BOOK")
        self.assertEqual(result["reply"], foundry_reply["reply"])
        self.assertEqual(result["response_id"], "response-123")

    def test_semantic_screening_disabled_does_not_disable_deterministic_screen(self):
        """Disabling the optional model layer must not affect regex emergencies."""
        original_semantic_screen = chat_service.screen_semantic_emergency

        with (
            patch.dict(
                os.environ,
                {"SEMANTIC_EMERGENCY_SCREENING_ENABLED": "false"},
            ),
            self._open_chat_session_patch(),
            patch.object(
                chat_service,
                "screen_semantic_emergency",
                wraps=original_semantic_screen,
            ) as semantic_screening,
            patch.object(chat_service, "get_session_workflow") as workflow,
            patch.object(chat_service, "open_foundry_client") as foundry,
        ):
            result = chat_service.process_chat(
                self.CUSTOMER,
                self.SESSION_ID,
                "I have chest pain right now.",
            )

        self.assertEqual(result["safety_status"], "POTENTIAL_EMERGENCY")
        self.assertEqual(result["safety_category"], "CHEST_PAIN")
        semantic_screening.assert_not_called()
        self._assert_foundry_was_not_started(workflow, foundry)

    def test_semantic_screening_disabled_preserves_normal_chat(self):
        """The real semantic service returns None when disabled, then chat continues."""
        client, foundry_context_manager = self._foundry_mocks()
        foundry_reply = {
            "reply": "I can help with that appointment.",
            "response_id": "response-disabled-123",
            "tool_calls": [],
        }
        original_semantic_screen = chat_service.screen_semantic_emergency

        with (
            patch.dict(
                os.environ,
                {"SEMANTIC_EMERGENCY_SCREENING_ENABLED": "false"},
            ),
            self._open_chat_session_patch(),
            patch.object(
                chat_service,
                "screen_semantic_emergency",
                wraps=original_semantic_screen,
            ) as semantic_screening,
            patch.object(
                chat_service,
                "get_session_workflow",
                return_value=None,
            ) as workflow,
            patch.object(
                chat_service,
                "open_foundry_client",
                return_value=foundry_context_manager,
            ) as foundry,
            patch.object(
                chat_service,
                "save_conversation_reference",
            ) as save_conversation,
            patch.object(
                chat_service,
                "send_chat_turn",
                return_value=foundry_reply,
            ) as send_turn,
            patch.object(
                chat_service,
                "verify_session_still_active",
            ) as verify_session,
        ):
            result = chat_service.process_chat(
                self.CUSTOMER,
                self.SESSION_ID,
                self.APPOINTMENT_MESSAGE,
            )

        semantic_screening.assert_called_once_with(self.APPOINTMENT_MESSAGE)
        workflow.assert_called_once()
        foundry.assert_called_once()
        send_turn.assert_called_once()
        save_conversation.assert_called_once()
        verify_session.assert_called_once()
        self.assertEqual(result["safety_status"], "NORMAL")
        self.assertIsNone(result["safety_category"])
        self.assertEqual(result["reply"], foundry_reply["reply"])


if __name__ == "__main__":
    unittest.main()
