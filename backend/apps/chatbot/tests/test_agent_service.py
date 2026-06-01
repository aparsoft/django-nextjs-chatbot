"""
Tests for the LangGraph Agent Service

Tests the agent service layer including:
- ChatAgentOrchestrator construction and configuration
- AgentService façade methods
- SummarizationMiddleware
- Tool loading and registration
- Checkpointer singleton
- Management command (run_chat)

Testing strategy (per TESTING.md rules):
    - NO external calls — all LLM / PostgresSaver calls are mocked
    - ChatbotTestMixin factory helpers for user/session creation
    - Independent tests — any file can run in isolation
    - Unique IDs via _next_id() counter

Run:
    cd backend
    python manage.py test chatbot.tests.test_agent_service \
        --settings=config.settings.test -v 2

    # Fast re-run
    python manage.py test chatbot.tests.test_agent_service \
        --settings=config.settings.test -v 2 --keepdb
"""

import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth import get_user_model
from io import StringIO

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from chatbot.models import ChatSession, UserPreference, UserTool, TOOL_REGISTRY
from chatbot.services.agent_service import (
    AgentService,
    ChatAgentOrchestrator,
    SummarizationMiddleware,
    calculator,
    load_tools_for_user,
    get_checkpointer,
)
from chatbot.tests._mixins import ChatbotTestMixin

User = get_user_model()


# ---------------------------------------------------------------------------
# SummarizationMiddleware Tests
# ---------------------------------------------------------------------------


class TestSummarizationMiddleware(ChatbotTestMixin, TestCase):
    """Test the SummarizationMiddleware for conversation compression."""

    def setUp(self):
        self.user = self.create_user()
        self.preference = self.create_preference(self.user)
        self.session = self.create_session(self.user)

    def test_middleware_creation(self):
        """Middleware can be created with a session."""
        mw = SummarizationMiddleware(self.session)
        self.assertIsNotNone(mw)
        self.assertIsInstance(mw._config, dict)

    def test_middleware_before_model_short_history(self):
        """before_model returns state unchanged when messages are short."""
        mw = SummarizationMiddleware(self.session)

        state = {
            "messages": [
                HumanMessage(content="Hi"),
                AIMessage(content="Hello!"),
            ]
        }
        result = mw.before_model(state)

        # Messages should be unchanged — too short to summarize
        self.assertEqual(len(result["messages"]), 2)

    def test_middleware_before_model_respects_disabled(self):
        """before_model skips summarization when disabled."""
        self.session.enable_summarization = False
        self.session.save()

        mw = SummarizationMiddleware(self.session)

        state = {"messages": [HumanMessage(content="Hi")]}
        result = mw.before_model(state)

        self.assertEqual(len(result["messages"]), 1)

    def test_middleware_reads_session_config(self):
        """Middleware reads config from session and user preferences."""
        mw = SummarizationMiddleware(self.session)

        config = mw._config
        self.assertIn("enabled", config)
        self.assertIn("threshold", config)
        self.assertIn("style", config)

    @patch("chatbot.services.agent_service.SummarizationService")
    def test_middleware_triggers_compression(self, MockSummary):
        """before_model compresses messages when threshold exceeded."""
        MockSummary.get_session_config.return_value = {
            "enabled": True,
            "threshold": 10,
            "keep_recent": 2,
            "model_name": "gpt-4o-mini",
            "max_summary_tokens": 128,
            "style": "concise",
        }
        MockSummary.should_summarize.return_value = True
        MockSummary.compress_messages.return_value = [
            SystemMessage(content="[Conversation Summary]\nTest summary"),
            AIMessage(content="Recent message"),
        ]

        mw = SummarizationMiddleware(self.session)
        state = {"messages": [HumanMessage(content="Long message")] * 20}
        result = mw.before_model(state)

        MockSummary.should_summarize.assert_called_once()
        MockSummary.compress_messages.assert_called_once()
        self.assertEqual(len(result["messages"]), 2)


# ---------------------------------------------------------------------------
# ChatAgentOrchestrator Tests
# ---------------------------------------------------------------------------


class TestChatAgentOrchestrator(ChatbotTestMixin, TestCase):
    """Test the ChatAgentOrchestrator class."""

    def setUp(self):
        self.user = self.create_user()
        self.preference = self.create_preference(self.user)
        self.session = self.create_session(self.user)

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_initialisation(
        self, mock_load_tools, mock_checkpoint, mock_create_agent
    ):
        """Orchestrator correctly sets up tools, middleware, and config."""
        mock_load_tools.return_value = []
        mock_checkpoint.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        orch = ChatAgentOrchestrator(self.session)

        self.assertEqual(orch.session, self.session)
        self.assertEqual(orch.user, self.user)
        self.assertEqual(orch.tools, [])
        self.assertEqual(len(orch.middleware), 1)
        self.assertIsInstance(orch.middleware[0], SummarizationMiddleware)
        self.assertIsNotNone(orch.agent)

        # Verify create_agent called with NEW API params
        mock_create_agent.assert_called_once()
        call_kwargs = mock_create_agent.call_args.kwargs
        self.assertIn("system_prompt", call_kwargs)
        self.assertIn("middleware", call_kwargs)
        self.assertIn("checkpointer", call_kwargs)
        # Model should be "openai:<model_name>"
        self.assertTrue(call_kwargs["model"].startswith("openai:"))

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_custom_recursion_limit(
        self, mock_tools, mock_checkpoint, mock_create_agent
    ):
        """Orchestrator respects custom recursion_limit."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        orch = ChatAgentOrchestrator(self.session, recursion_limit=10)

        self.assertEqual(orch.recursion_limit, 10)
        self.assertEqual(orch.config["recursion_limit"], 10)

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_custom_system_prompt(
        self, mock_tools, mock_checkpoint, mock_create_agent
    ):
        """Orchestrator uses custom system prompt when provided."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        orch = ChatAgentOrchestrator(
            self.session, system_prompt="You are a pirate."
        )

        self.assertEqual(orch.system_prompt, "You are a pirate.")

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_default_system_prompt(
        self, mock_tools, mock_checkpoint, mock_create_agent
    ):
        """Orchestrator builds a default system prompt when none provided."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        orch = ChatAgentOrchestrator(self.session)
        self.assertIn("helpful", orch.system_prompt.lower())

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_model_string_format(
        self, mock_tools, mock_checkpoint, mock_create_agent
    ):
        """Orchestrator passes model as 'openai:<model_name>' string."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        session = self.create_session(
            self.user, model_name="gpt-4o", temperature=0.3
        )
        ChatAgentOrchestrator(session)

        call_kwargs = mock_create_agent.call_args.kwargs
        self.assertEqual(call_kwargs["model"], "openai:gpt-4o")

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_invoke_returns_response(
        self, mock_tools, mock_checkpoint, mock_create_agent
    ):
        """Orchestrator.invoke() returns a dict with 'response' key."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = MagicMock()
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        ai_msg = AIMessage(content="Hello! I am the AI assistant.")
        mock_agent.invoke.return_value = {"messages": [ai_msg]}

        orch = ChatAgentOrchestrator(self.session)
        result = orch.invoke("Hi there!")

        self.assertIn("response", result)
        self.assertEqual(result["response"], "Hello! I am the AI assistant.")
        self.assertIn("messages", result)
        self.assertIn("session", result)

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_invoke_updates_session_title(
        self, mock_tools, mock_checkpoint, mock_create_agent
    ):
        """First invoke auto-generates a session title from the user message."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = MagicMock()
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        # Force default title so auto-title triggers
        self.session.title = "New Conversation"
        self.session.save()

        mock_agent.invoke.return_value = {
            "messages": [AIMessage(content="Sure!")]
        }
        orch = ChatAgentOrchestrator(self.session)
        orch.invoke("Tell me about Python decorators")

        self.session.refresh_from_db()
        self.assertNotEqual(self.session.title, "New Conversation")
        self.assertIn("Python", self.session.title)

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_invoke_updates_analytics(
        self, mock_tools, mock_checkpoint, mock_create_agent
    ):
        """Invoke increments session message_count."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = MagicMock()
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        initial_count = self.session.message_count
        mock_agent.invoke.return_value = {
            "messages": [AIMessage(content="Reply")]
        }
        orch = ChatAgentOrchestrator(self.session)
        orch.invoke("Hello")

        self.session.refresh_from_db()
        self.assertEqual(self.session.message_count, initial_count + 2)

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_get_history_empty(
        self, mock_tools, mock_checkpoint, mock_create_agent
    ):
        """get_history returns empty list when no checkpoint exists."""
        mock_tools.return_value = []
        mock_cp = MagicMock()
        mock_cp.get_tuple.return_value = None
        mock_checkpoint.return_value = mock_cp
        mock_create_agent.return_value = MagicMock()

        orch = ChatAgentOrchestrator(self.session)
        history = orch.get_history()
        self.assertEqual(history, [])

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_get_history_with_messages(
        self, mock_tools, mock_checkpoint, mock_create_agent
    ):
        """get_history returns messages from the checkpointer."""
        mock_tools.return_value = []
        mock_cp = MagicMock()
        mock_cp.get_tuple.return_value = MagicMock(
            checkpoint={
                "channel_values": {
                    "messages": [
                        HumanMessage(content="Hi"),
                        AIMessage(content="Hello!"),
                    ]
                }
            }
        )
        mock_checkpoint.return_value = mock_cp
        mock_create_agent.return_value = MagicMock()

        orch = ChatAgentOrchestrator(self.session)
        history = orch.get_history()
        self.assertEqual(len(history), 2)

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_stream_yields_events(
        self, mock_tools, mock_checkpoint, mock_create_agent
    ):
        """stream() yields events from the agent."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = MagicMock()
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        mock_events = [
            {"messages": [HumanMessage(content="Hi")]},
            {"messages": [HumanMessage(content="Hi"), AIMessage(content="Hello")]},
        ]
        mock_agent.stream.return_value = iter(mock_events)

        orch = ChatAgentOrchestrator(self.session)
        events = list(orch.stream("Hi"))
        self.assertEqual(len(events), 2)

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_config_has_thread_id(
        self, mock_tools, mock_checkpoint, mock_create_agent
    ):
        """Agent config maps thread_id to session UUID."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        orch = ChatAgentOrchestrator(self.session)
        self.assertEqual(
            orch.config["configurable"]["thread_id"],
            str(self.session.id),
        )

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_orchestrator_invoke_extracts_tokens(
        self, mock_tools, mock_checkpoint, mock_create_agent
    ):
        """invoke extracts token usage from the AI message."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = MagicMock()
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent

        ai_msg = AIMessage(
            content="Reply",
            usage_metadata={
                "input_tokens": 20,
                "output_tokens": 22,
                "total_tokens": 42,
            },
        )
        mock_agent.invoke.return_value = {"messages": [ai_msg]}

        orch = ChatAgentOrchestrator(self.session)
        result = orch.invoke("Hello")

        self.assertEqual(result["tokens_used"], 42)


# ---------------------------------------------------------------------------
# AgentService Façade Tests
# ---------------------------------------------------------------------------


class TestAgentService(ChatbotTestMixin, TestCase):
    """Test the AgentService static façade."""

    def setUp(self):
        self.user = self.create_user()
        self.preference = self.create_preference(self.user)
        self.session = self.create_session(self.user)

    @patch("chatbot.services.agent_service.create_agent")
    @patch("chatbot.services.agent_service.get_checkpointer")
    @patch("chatbot.services.agent_service.load_tools_for_user")
    def test_create_orchestrator(
        self, mock_tools, mock_checkpoint, mock_create_agent
    ):
        """create_orchestrator returns a ChatAgentOrchestrator."""
        mock_tools.return_value = []
        mock_checkpoint.return_value = MagicMock()
        mock_create_agent.return_value = MagicMock()

        orch = AgentService.create_orchestrator(self.session)

        self.assertIsInstance(orch, ChatAgentOrchestrator)
        self.assertEqual(orch.session, self.session)

    @patch("chatbot.services.agent_service.ChatAgentOrchestrator.invoke")
    @patch("chatbot.services.agent_service.ChatAgentOrchestrator.__init__")
    def test_chat_convenience(self, mock_init, mock_invoke):
        """AgentService.chat() invokes the orchestrator and returns result."""
        mock_init.return_value = None  # skip __init__
        mock_invoke.return_value = {
            "response": "Test response",
            "messages": [AIMessage(content="Test response")],
            "session": self.session,
            "tokens_used": 50,
        }

        result = AgentService.chat(self.session, "Hello")

        self.assertEqual(result["response"], "Test response")

    @patch("chatbot.services.agent_service.ChatAgentOrchestrator.stream")
    @patch("chatbot.services.agent_service.ChatAgentOrchestrator.__init__")
    def test_chat_stream_yields_events(self, mock_init, mock_stream):
        """AgentService.chat_stream() yields stream events."""
        mock_init.return_value = None
        mock_events = [{"messages": []}]
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
        self.assertEqual(len(tools), 1)
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
        self.assertEqual(
            calculator.invoke({"expression": "15 * 3.5"}), "52.5"
        )

    def test_subtraction(self):
        self.assertEqual(
            calculator.invoke({"expression": "100 - 37"}), "63"
        )

    def test_division(self):
        self.assertEqual(
            calculator.invoke({"expression": "144 / 12"}), "12.0"
        )

    def test_abs(self):
        self.assertEqual(
            calculator.invoke({"expression": "abs(-42)"}), "42"
        )

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

    def test_get_checkpointer_enters_context_manager(self):
        """get_checkpointer enters the from_conn_string context manager."""
        import chatbot.services.agent_service as mod
        mod._checkpointer = None  # reset singleton

        mock_ctx = MagicMock()
        mock_instance = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_instance)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch(
            "chatbot.services.agent_service.PostgresSaver"
        ) as MockSaver:
            MockSaver.from_conn_string.return_value = mock_ctx

            result = get_checkpointer()

            self.assertEqual(result, mock_instance)
            mock_ctx.__enter__.assert_called_once()
            mock_instance.setup.assert_called_once()

        # Cleanup
        mod._checkpointer = None


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
            "chatbot.services.agent_service.ChatAgentOrchestrator.__init__",
            return_value=None,
        ), patch(
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
            "chatbot.services.agent_service.ChatAgentOrchestrator.__init__",
            return_value=None,
        ), patch(
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

        self.assertTrue(ChatSession.objects.filter(user=self.user).exists())

    def test_history_flag_prints_history(self):
        """run_chat --history shows conversation history."""
        session = self.create_session(self.user)

        with patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator.__init__",
            return_value=None,
        ), patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator"
            ".get_history_display"
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
            "chatbot.services.agent_service.ChatAgentOrchestrator.__init__",
            return_value=None,
        ), patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator"
            ".get_history_display"
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
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command(
                "run_chat",
                user="nonexistent@test.com",
                message="Hello",
            )

    def test_invalid_session_raises_error(self):
        """run_chat with invalid --session raises CommandError."""
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
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
            "chatbot.services.agent_service.ChatAgentOrchestrator.__init__",
            return_value=None,
        ), patch(
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
            "chatbot.services.agent_service.ChatAgentOrchestrator.__init__",
            return_value=None,
        ), patch(
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

        session = ChatSession.objects.filter(user=self.user).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.model_name, "gpt-4o")

    def test_custom_temperature_flag(self):
        """run_chat --temperature overrides the default temperature."""
        with patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator.__init__",
            return_value=None,
        ), patch(
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
        self.assertIsNotNone(session)
        self.assertEqual(session.temperature, 0.1)

    def test_agent_error_in_non_interactive(self):
        """run_chat prints error and exits on agent failure."""
        with patch(
            "chatbot.services.agent_service.ChatAgentOrchestrator.__init__",
            return_value=None,
        ), patch(
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
