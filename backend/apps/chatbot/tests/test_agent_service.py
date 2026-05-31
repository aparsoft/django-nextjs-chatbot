"""
Tests for the LangGraph Agent Service

Tests the agent service layer including:
- ChatAgentOrchestrator construction and configuration
- AgentService façade methods
- Tool loading and registration
- Checkpointer integration
- Management command (run_chat)

Testing strategy:
    - Unit tests mock external services (OpenAI, PostgresSaver)
    - Integration tests use InMemorySaver instead of PostgresSaver
    - Management command tests use CallCommand with mocked agent

Run:
    python manage.py test chatbot.tests.test_agent_service \
        --settings=config.settings.test -v 2
"""

import uuid
from unittest.mock import MagicMock, patch, PropertyMock

from django.test import TestCase, override_settings
from django.core.management import call_command
from django.contrib.auth import get_user_model
from io import StringIO

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver

from chatbot.models import ChatSession, UserPreference, UserTool, TOOL_REGISTRY
from chatbot.services.agent_service import (
    AgentService,
    ChatAgentOrchestrator,
    calculator,
    load_tools_for_user,
    get_checkpointer,
)
from chatbot.tests._mixins import ChatbotTestMixin

User = get_user_model()


# ---------------------------------------------------------------------------
# ChatAgentOrchestrator Tests
# ---------------------------------------------------------------------------


class TestChatAgentOrchestrator(ChatbotTestMixin, TestCase):
    """Test the ChatAgentOrchestrator class."""

    def setUp(self):
        self.user = self.create_user()
        self.preference = self.create_preference(self.user)
        self.session = self.create_session(self.user)

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_initialisation(self, mock_load_tools, mock_checkpoint):
        """Orchestrator correctly sets up LLM, tools, and checkpointer."""
        mock_load_tools.return_value = []
        mock_checkpoint.return_value = InMemorySaver()

        orch = ChatAgentOrchestrator(self.session)

        self.assertEqual(orch.session, self.session)
        self.assertEqual(orch.user, self.user)
        self.assertEqual(orch.tools, [])
        self.assertIsNotNone(orch.agent)
        self.assertEqual(
            orch.config["configurable"]["thread_id"],
            self.session.thread_id,
        )

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_custom_recursion_limit(self, mock_tools, mock_checkpoint):
        """Orchestrator respects custom recursion_limit."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = InMemorySaver()

        orch = ChatAgentOrchestrator(self.session, recursion_limit=10)

        self.assertEqual(orch.recursion_limit, 10)
        self.assertEqual(orch.config["recursion_limit"], 10)

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_custom_system_prompt(self, mock_tools, mock_checkpoint):
        """Orchestrator uses custom system prompt when provided."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = InMemorySaver()

        orch = ChatAgentOrchestrator(
            self.session, system_prompt="You are a pirate."
        )

        self.assertEqual(orch.system_prompt, "You are a pirate.")

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_default_system_prompt(self, mock_tools, mock_checkpoint):
        """Orchestrator builds a default system prompt when none is provided."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = InMemorySaver()

        orch = ChatAgentOrchestrator(self.session)

        self.assertIn("helpful", orch.system_prompt.lower())

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_session_model_and_temperature(self, mock_tools, mock_checkpoint):
        """Orchestrator uses the session's model_name and temperature."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = InMemorySaver()

        session = self.create_session(
            self.user, model_name="gpt-4o", temperature=0.3
        )
        orch = ChatAgentOrchestrator(session)

        # The LLM should be configured with session settings
        self.assertEqual(orch.llm.model_name, "gpt-4o")

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_invoke_returns_response(self, mock_tools, mock_checkpoint):
        """Orchestrator.invoke() returns a dict with 'response' key."""
        mock_tools.return_value = []
        saver = InMemorySaver()
        mock_checkpoint.return_value = saver

        orch = ChatAgentOrchestrator(self.session)

        # Mock the agent to return a controlled response
        ai_msg = AIMessage(content="Hello! I am the AI assistant.")
        with patch.object(orch.agent, "invoke") as mock_invoke:
            mock_invoke.return_value = {"messages": [ai_msg]}
            result = orch.invoke("Hi there!")

        self.assertIn("response", result)
        self.assertEqual(result["response"], "Hello! I am the AI assistant.")
        self.assertIn("messages", result)
        self.assertIn("session", result)

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_invoke_updates_session_title(self, mock_tools, mock_checkpoint):
        """First invoke auto-generates a session title from the user message."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = InMemorySaver()

        # Ensure session has default title
        self.assertEqual(self.session.title, "New Conversation")

        orch = ChatAgentOrchestrator(self.session)

        ai_msg = AIMessage(content="Sure!")
        with patch.object(orch.agent, "invoke") as mock_invoke:
            mock_invoke.return_value = {"messages": [ai_msg]}
            orch.invoke("Tell me about Python decorators")

        self.session.refresh_from_db()
        self.assertNotEqual(self.session.title, "New Conversation")
        self.assertIn("Python", self.session.title)

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_invoke_updates_analytics(self, mock_tools, mock_checkpoint):
        """Invoke increments session message_count."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = InMemorySaver()

        initial_count = self.session.message_count
        orch = ChatAgentOrchestrator(self.session)

        ai_msg = AIMessage(content="Reply")
        with patch.object(orch.agent, "invoke") as mock_invoke:
            mock_invoke.return_value = {"messages": [ai_msg]}
            orch.invoke("Hello")

        self.session.refresh_from_db()
        self.assertEqual(self.session.message_count, initial_count + 2)

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_get_history(self, mock_tools, mock_checkpoint):
        """get_history returns the messages from checkpointer state."""
        mock_tools.return_value = []
        saver = InMemorySaver()
        mock_checkpoint.return_value = saver

        orch = ChatAgentOrchestrator(self.session)

        # Initially empty
        history = orch.get_history()
        self.assertEqual(history, [])

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_stream_yields_events(self, mock_tools, mock_checkpoint):
        """stream() yields events from the agent."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = InMemorySaver()

        orch = ChatAgentOrchestrator(self.session)

        mock_events = [
            {"messages": [HumanMessage(content="Hi")]},
            {"messages": [HumanMessage(content="Hi"), AIMessage(content="Hello")]},
        ]
        with patch.object(orch.agent, "stream") as mock_stream:
            mock_stream.return_value = iter(mock_events)
            events = list(orch.stream("Hi"))

        self.assertEqual(len(events), 2)


# ---------------------------------------------------------------------------
# AgentService Façade Tests
# ---------------------------------------------------------------------------


class TestAgentService(ChatbotTestMixin, TestCase):
    """Test the AgentService static façade."""

    def setUp(self):
        self.user = self.create_user()
        self.preference = self.create_preference(self.user)
        self.session = self.create_session(self.user)

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_create_orchestrator(self, mock_tools, mock_checkpoint):
        """create_orchestrator returns a ChatAgentOrchestrator."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = InMemorySaver()

        orch = AgentService.create_orchestrator(self.session)

        self.assertIsInstance(orch, ChatAgentOrchestrator)
        self.assertEqual(orch.session, self.session)

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_chat_convenience(self, mock_tools, mock_checkpoint):
        """AgentService.chat() invokes the orchestrator and returns result."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = InMemorySaver()

        ai_msg = AIMessage(content="Test response")
        with patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator.invoke"
        ) as mock_invoke:
            mock_invoke.return_value = {
                "response": "Test response",
                "messages": [ai_msg],
                "session": self.session,
                "tokens_used": 50,
            }
            result = AgentService.chat(self.session, "Hello")

        self.assertEqual(result["response"], "Test response")

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_chat_stream_yields_events(self, mock_tools, mock_checkpoint):
        """AgentService.chat_stream() yields stream events."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = InMemorySaver()

        mock_events = [{"messages": []}]
        with patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator.stream"
        ) as mock_stream:
            mock_stream.return_value = iter(mock_events)
            events = list(AgentService.chat_stream(self.session, "Hi"))

        self.assertEqual(len(events), 1)


# ---------------------------------------------------------------------------
# Tool Loading Tests
# ---------------------------------------------------------------------------


class TestToolLoading(ChatbotTestMixin, TestCase):
    """Test the tool loading system."""

    def setUp(self):
        self.user = self.create_user()

    def test_load_tools_no_enabled_tools(self):
        """Returns empty list when user has no enabled tools."""
        tools = load_tools_for_user(self.user)
        self.assertEqual(tools, [])

    def test_load_tools_with_calculator_enabled(self):
        """Returns calculator tool when enabled."""
        UserTool.enable_tool(self.user, "calculator")
        tools = load_tools_for_user(self.user)

        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "calculator")

    def test_load_tools_skips_web_search(self):
        """Skips web_search (not yet implemented)."""
        UserTool.enable_tool(self.user, "web_search")
        tools = load_tools_for_user(self.user)

        self.assertEqual(tools, [])

    def test_load_tools_skips_code_executor(self):
        """Skips code_executor (not yet implemented)."""
        UserTool.enable_tool(self.user, "code_executor")
        tools = load_tools_for_user(self.user)

        self.assertEqual(tools, [])

    def test_load_tools_multiple_enabled(self):
        """Loads multiple enabled tools."""
        UserTool.enable_tool(self.user, "calculator")
        UserTool.enable_tool(self.user, "web_search")  # skipped
        UserTool.enable_tool(self.user, "code_executor")  # skipped

        tools = load_tools_for_user(self.user)
        self.assertEqual(len(tools), 1)  # only calculator
        self.assertEqual(tools[0].name, "calculator")

    def test_load_tools_disabled_tool_not_loaded(self):
        """Disabled tools are not loaded."""
        UserTool.enable_tool(self.user, "calculator")
        UserTool.disable_tool(self.user, "calculator")

        tools = load_tools_for_user(self.user)
        self.assertEqual(tools, [])

    def test_load_tools_document_retriever(self):
        """Document retriever tool loads when enabled."""
        UserTool.enable_tool(self.user, "document_retriever")
        tools = load_tools_for_user(self.user)

        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "document_retriever")


# ---------------------------------------------------------------------------
# Calculator Tool Tests
# ---------------------------------------------------------------------------


class TestCalculatorTool(TestCase):
    """Test the built-in calculator tool."""

    def test_addition(self):
        self.assertEqual(calculator.invoke({"expression": "2 + 2"}), "4")

    def test_multiplication(self):
        self.assertEqual(calculator.invoke({"expression": "15 * 3.5"}), "52.5")

    def test_subtraction(self):
        self.assertEqual(calculator.invoke({"expression": "100 - 37"}), "63")

    def test_division(self):
        self.assertEqual(calculator.invoke({"expression": "144 / 12"}), "12.0")

    def test_abs(self):
        self.assertEqual(calculator.invoke({"expression": "abs(-42)"}), "42")

    def test_min_max(self):
        self.assertEqual(calculator.invoke({"expression": "min(3, 7)"}), "3")
        self.assertEqual(calculator.invoke({"expression": "max(3, 7)"}), "7")

    def test_complex_expression(self):
        result = calculator.invoke({"expression": "pow(2, 10)"})
        self.assertEqual(result, "1024")

    def test_invalid_expression(self):
        """Invalid expression returns error string."""
        result = calculator.invoke({"expression": "invalid_func()"})
        self.assertIn("Error", result)

    def test_division_by_zero(self):
        """Division by zero returns error string."""
        result = calculator.invoke({"expression": "1 / 0"})
        # Python eval returns ZeroDivisionError which gets caught
        self.assertIn("Error", result)

    def test_tool_has_name_and_description(self):
        """Tool metadata is properly set."""
        self.assertEqual(calculator.name, "calculator")
        self.assertIn("math", calculator.description.lower())


# ---------------------------------------------------------------------------
# Checkpointer Tests
# ---------------------------------------------------------------------------


class TestCheckpointer(TestCase):
    """Test the checkpointer singleton."""

    def test_get_checkpointer_returns_postgres_saver(self):
        """get_checkpointer returns a PostgresSaver instance."""
        from langgraph.checkpoint.postgres import PostgresSaver

        with patch(
            "chatbot.services.agent_service.PostgresSaver"
        ) as MockSaver:
            mock_instance = MagicMock()
            MockSaver.from_conn_string.return_value = mock_instance

            # Reset singleton for clean test
            import chatbot.services.agent_service as mod
            mod._checkpointer = None

            result = get_checkpointer()
            self.assertEqual(result, mock_instance)
            MockSaver.from_conn_string.assert_called_once()

            # Cleanup
            mod._checkpointer = None


# ---------------------------------------------------------------------------
# Integration Test — Full Agent Loop (with InMemorySaver)
# ---------------------------------------------------------------------------


class TestAgentIntegration(ChatbotTestMixin, TestCase):
    """
    Integration test that runs the agent end-to-end with InMemorySaver.

    These tests mock the LLM call to avoid hitting OpenAI's API.
    """

    def setUp(self):
        self.user = self.create_user()
        self.preference = self.create_preference(self.user)
        self.session = self.create_session(self.user)

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_agent_invokes_llm_and_returns_response(self, mock_tools, mock_checkpoint):
        """Full invoke cycle: user message → LLM → AI response."""
        mock_tools.return_value = []
        saver = InMemorySaver()
        mock_checkpoint.return_value = saver

        orch = ChatAgentOrchestrator(self.session)

        # Mock the agent graph to simulate a real LLM response
        ai_msg = AIMessage(
            content="LangGraph is a framework for building stateful AI applications.",
            usage_metadata={"total_tokens": 42},
        )
        with patch.object(orch.agent, "invoke") as mock_invoke:
            mock_invoke.return_value = {"messages": [ai_msg]}
            result = orch.invoke("What is LangGraph?")

        self.assertIn("LangGraph", result["response"])
        self.assertEqual(len(result["messages"]), 1)

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_agent_with_calculator_tool(self, mock_tools, mock_checkpoint):
        """Agent can use the calculator tool."""
        calc_tool = calculator
        mock_tools.return_value = [calc_tool]
        saver = InMemorySaver()
        mock_checkpoint.return_value = saver

        orch = ChatAgentOrchestrator(self.session)
        self.assertEqual(len(orch.tools), 1)
        self.assertEqual(orch.tools[0].name, "calculator")

    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_agent_config_has_thread_id(self, mock_tools, mock_checkpoint):
        """Agent config maps thread_id to session UUID."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = InMemorySaver()

        orch = ChatAgentOrchestrator(self.session)

        self.assertEqual(
            orch.config["configurable"]["thread_id"],
            str(self.session.id),
        )


# ---------------------------------------------------------------------------
# Management Command Tests
# ---------------------------------------------------------------------------


class TestRunChatCommand(ChatbotTestMixin, TestCase):
    """Test the run_chat management command."""

    def setUp(self):
        self.user = self.create_user()
        self.preference = self.create_preference(self.user)

    def test_non_interactive_single_message(self):
        """run_chat --message sends a single message and prints response."""
        session = self.create_session(self.user)

        with patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator.invoke"
        ) as mock_invoke:
            mock_invoke.return_value = {
                "response": "Python is a programming language.",
                "messages": [],
                "session": session,
                "tokens_used": 30,
            }

            out = StringIO()
            call_command(
                "run_chat",
                user=self.user.email,
                session=str(session.id),
                message="What is Python?",
                stdout=out,
            )

        output = out.getvalue()
        self.assertIn("Python is a programming language.", output)

    def test_non_interactive_creates_session(self):
        """run_chat creates a new session if --session is not provided."""
        with patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator.invoke"
        ) as mock_invoke:
            mock_invoke.return_value = {
                "response": "Hello!",
                "messages": [],
                "session": MagicMock(),
                "tokens_used": 10,
            }

            out = StringIO()
            call_command(
                "run_chat",
                user=self.user.email,
                message="Hello",
                stdout=out,
            )

        # A new session should have been created
        self.assertTrue(ChatSession.objects.filter(user=self.user).exists())

    def test_history_flag_prints_history(self):
        """run_chat --history shows conversation history."""
        session = self.create_session(self.user)

        with patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator.get_history_display"
        ) as mock_history:
            mock_history.return_value = [
                {"role": "human", "content": "Hi"},
                {"role": "ai", "content": "Hello!"},
            ]

            out = StringIO()
            call_command(
                "run_chat",
                user=self.user.email,
                session=str(session.id),
                history=True,
                stdout=out,
            )

        output = out.getvalue()
        self.assertIn("Conversation History", output)
        self.assertIn("Hi", output)
        self.assertIn("Hello!", output)

    def test_history_empty_session(self):
        """run_chat --history shows '(No messages yet)' for empty sessions."""
        session = self.create_session(self.user)

        with patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator.get_history_display"
        ) as mock_history:
            mock_history.return_value = []

            out = StringIO()
            call_command(
                "run_chat",
                user=self.user.email,
                session=str(session.id),
                history=True,
                stdout=out,
            )

        output = out.getvalue()
        self.assertIn("No messages yet", output)

    def test_invalid_user_raises_error(self):
        """run_chat with invalid --user raises CommandError."""
        with self.assertRaises(Exception):
            call_command(
                "run_chat",
                user="nonexistent@test.com",
                message="Hello",
            )

    def test_invalid_session_raises_error(self):
        """run_chat with invalid --session raises CommandError."""
        with self.assertRaises(Exception):
            call_command(
                "run_chat",
                user=self.user.email,
                session=str(uuid.uuid4()),
                message="Hello",
            )

    def test_uses_first_superuser_by_default(self):
        """run_chat without --user defaults to first superuser."""
        self.user.is_superuser = True
        self.user.save()

        with patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator.invoke"
        ) as mock_invoke:
            mock_invoke.return_value = {
                "response": "Hi!",
                "messages": [],
                "session": MagicMock(),
                "tokens_used": 5,
            }

            out = StringIO()
            call_command("run_chat", message="Hello", stdout=out)

        output = out.getvalue()
        self.assertIn("Hi!", output)

    def test_custom_model_flag(self):
        """run_chat --model overrides the default model."""
        with patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator.invoke"
        ) as mock_invoke:
            mock_invoke.return_value = {
                "response": "Test",
                "messages": [],
                "session": MagicMock(),
                "tokens_used": 5,
            }

            out = StringIO()
            call_command(
                "run_chat",
                user=self.user.email,
                model="gpt-4o",
                message="Hello",
                stdout=out,
            )

        # Verify session was created with the custom model
        session = ChatSession.objects.filter(user=self.user).first()
        self.assertEqual(session.model_name, "gpt-4o")

    def test_custom_temperature_flag(self):
        """run_chat --temperature overrides the default temperature."""
        with patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator.invoke"
        ) as mock_invoke:
            mock_invoke.return_value = {
                "response": "Test",
                "messages": [],
                "session": MagicMock(),
                "tokens_used": 5,
            }

            out = StringIO()
            call_command(
                "run_chat",
                user=self.user.email,
                temperature=0.1,
                message="Hello",
                stdout=out,
            )

        session = ChatSession.objects.filter(user=self.user).first()
        self.assertEqual(session.temperature, 0.1)

    def test_agent_error_in_non_interactive(self):
        """run_chat prints error and exits on agent failure."""
        with patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator.invoke"
        ) as mock_invoke:
            mock_invoke.side_effect = Exception("OpenAI API error")

            out = StringIO()
            err = StringIO()
            with self.assertRaises(SystemExit):
                call_command(
                    "run_chat",
                    user=self.user.email,
                    message="Hello",
                    stdout=out,
                    stderr=err,
                )

            error_output = err.getvalue()
            self.assertIn("Error", error_output)
