"""
Management Command: run_chat

Interactive CLI chatbot powered by the LangGraph ReAct agent.
Designed for intern onboarding — demonstrates the agent pipeline
end-to-end before building the Next.js frontend.

Usage:
    # Start a new conversation
    python manage.py run_chat

    # Resume an existing session
    python manage.py run_chat --session <session-uuid>

    # Use a specific model
    python manage.py run_chat --model gpt-4o-mini

    # Adjust temperature
    python manage.py run_chat --temperature 0.3

    # Non-interactive (single message)
    python manage.py run_chat --message "What is Python and Django?" --model gpt-4o-mini

    # Show conversation history for a session
    python manage.py run_chat --session <uuid> --history

Commands inside the chat:
    /help     — Show available commands
    /history  — Show conversation history
    /tools    — Show enabled tools
    /stats    — Show session statistics
    /new      — Start a new session
    /quit     — Exit the chat
"""

import sys
import time
import uuid
import logging

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from chatbot.models import ChatSession, UserPreference
from chatbot.services import AgentService, ChatAgentOrchestrator

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Interactive CLI chatbot — talk to the LangGraph agent from the "
        "terminal. Perfect for testing and intern onboarding."
    )

    # ANSI colour codes for pretty terminal output
    class Colors:
        RESET = "\033[0m"
        BOLD = "\033[1m"
        DIM = "\033[2m"
        GREEN = "\033[32m"
        CYAN = "\033[36m"
        YELLOW = "\033[33m"
        RED = "\033[31m"
        MAGENTA = "\033[35m"
        BLUE = "\033[34m"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="Email of the user to chat as (defaults to first superuser)",
        )
        parser.add_argument(
            "--session",
            type=str,
            help="UUID of an existing session to resume",
        )
        parser.add_argument(
            "--model",
            type=str,
            help="LLM model name (e.g. gpt-4o-mini, gpt-4o)",
        )
        parser.add_argument(
            "--temperature",
            type=float,
            help="Model temperature (0.0 – 2.0)",
        )
        parser.add_argument(
            "--message",
            type=str,
            help="Send a single message (non-interactive mode)",
        )
        parser.add_argument(
            "--history",
            action="store_true",
            help="Print conversation history and exit",
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        self.user = self._resolve_user(options["user"])
        self.session = self._resolve_session(
            options.get("session"),
            model=options.get("model"),
            temperature=options.get("temperature"),
        )

        # History-only mode
        if options.get("history"):
            self._print_history()
            return

        # Non-interactive single-message mode
        if options.get("message"):
            self._send_single(options["message"])
            return

        # Interactive loop
        self._interactive_loop()

    # ------------------------------------------------------------------
    # User resolution
    # ------------------------------------------------------------------

    def _resolve_user(self, email: str | None):
        """Find the user to chat as."""
        if email:
            try:
                return User.objects.get(email=email)
            except User.DoesNotExist:
                raise CommandError(f"User not found: {email}")

        # Default: use the first superuser
        user = User.objects.filter(is_superuser=True).first()
        if user:
            return user

        # Fallback: first user
        user = User.objects.first()
        if user:
            return user

        raise CommandError(
            "No users found. Create a superuser first:\n"
            "  python manage.py createsuperuser"
        )

    # ------------------------------------------------------------------
    # Session resolution
    # ------------------------------------------------------------------

    def _resolve_session(
        self,
        session_uuid: str | None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> ChatSession:
        """Get an existing session or create a new one."""
        if session_uuid:
            try:
                return ChatSession.objects.get(
                    id=uuid.UUID(session_uuid),
                    user=self.user,
                )
            except (ChatSession.DoesNotExist, ValueError):
                raise CommandError(f"Session not found: {session_uuid}")

        # Ensure user has preferences
        prefs, _ = UserPreference.objects.get_or_create(user=self.user)

        # Create new session
        kwargs = {}
        if model:
            kwargs["model_name"] = model
        if temperature is not None:
            kwargs["temperature"] = temperature

        return ChatSession.create_for_user(self.user, preferences=prefs, **kwargs)

    # ------------------------------------------------------------------
    # Interactive loop
    # ------------------------------------------------------------------

    def _interactive_loop(self):
        """Run the REPL (Read-Eval-Print Loop)."""
        C = self.Colors

        self._print_banner()

        while True:
            try:
                user_input = input(f"\n{C.BOLD}{C.GREEN}You:{C.RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                self._print_goodbye()
                break

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                should_continue = self._handle_command(user_input)
                if not should_continue:
                    break
                continue

            # Send to agent
            self._chat(user_input)

    # ------------------------------------------------------------------
    # Chat execution
    # ------------------------------------------------------------------

    def _chat(self, user_message: str):
        """Send a message to the agent and print the response."""
        C = self.Colors
        start = time.time()

        try:
            orchestrator = AgentService.create_orchestrator(self.session)
            result = orchestrator.invoke(user_message)
            elapsed = time.time() - start

            response = result["response"]
            tokens = result.get("tokens_used", 0)

            # Print AI response
            self.stdout.write(f"\n{C.BOLD}{C.CYAN}AI:{C.RESET} {response}")

            # Print metadata
            meta_parts = [f"{elapsed:.1f}s"]
            if tokens:
                meta_parts.append(f"{tokens} tokens")
            self.stdout.write(f"{C.DIM}[{' | '.join(meta_parts)}]{C.RESET}")

        except Exception as e:
            logger.exception("Agent error")
            self.stderr.write(f"\n{C.RED}Error: {e}{C.RESET}")

    def _send_single(self, message: str):
        """Send a single message in non-interactive mode."""
        C = self.Colors

        try:
            result = AgentService.chat(
                session=self.session,
                user_message=message,
            )
            self.stdout.write(f"{result['response']}")
        except Exception as e:
            self.stderr.write(f"{C.RED}Error: {e}{C.RESET}")
            sys.exit(1)

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------

    def _handle_command(self, cmd: str) -> bool:
        """
        Handle a slash command. Returns False to exit the loop.
        """
        C = self.Colors
        cmd = cmd.lower().strip()

        if cmd in ("/quit", "/exit", "/q"):
            self._print_goodbye()
            return False

        elif cmd == "/help":
            self._print_help()

        elif cmd == "/history":
            self._print_history()

        elif cmd == "/tools":
            self._print_tools()

        elif cmd == "/stats":
            self._print_stats()

        elif cmd == "/new":
            self.session = ChatSession.create_for_user(self.user)
            self.stdout.write(
                f"\n{C.GREEN}New session started: {self.session.thread_id}{C.RESET}"
            )

        else:
            self.stdout.write(
                f"{C.YELLOW}Unknown command: {cmd}. Type /help for options.{C.RESET}"
            )

        return True

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def _print_banner(self):
        C = self.Colors
        self.stdout.write(f"\n{C.BOLD}{'=' * 60}{C.RESET}")
        self.stdout.write(
            f"{C.BOLD}{C.MAGENTA}  🤖 LangGraph Chatbot — Interactive CLI{C.RESET}"
        )
        self.stdout.write(f"{C.BOLD}{'=' * 60}{C.RESET}")
        self.stdout.write(f"  User:    {C.CYAN}{self.user.email}{C.RESET}")
        self.stdout.write(f"  Session: {C.CYAN}{self.session.thread_id}{C.RESET}")
        self.stdout.write(f"  Model:   {C.CYAN}{self.session.model_name}{C.RESET}")
        self.stdout.write(f"  Temp:    {C.CYAN}{self.session.temperature}{C.RESET}")
        self.stdout.write(f"{C.DIM}  Type /help for commands, /quit to exit{C.RESET}")
        self.stdout.write(f"{C.BOLD}{'=' * 60}{C.RESET}")

    def _print_goodbye(self):
        C = self.Colors
        self.stdout.write(
            f"\n{C.YELLOW}Goodbye! Session saved: {self.session.thread_id}{C.RESET}\n"
        )

    def _print_help(self):
        C = self.Colors
        self.stdout.write(f"\n{C.BOLD}Available Commands:{C.RESET}")
        self.stdout.write(f"  {C.CYAN}/help{C.RESET}     — Show this help")
        self.stdout.write(f"  {C.CYAN}/history{C.RESET}  — Show conversation history")
        self.stdout.write(f"  {C.CYAN}/tools{C.RESET}    — Show enabled tools")
        self.stdout.write(f"  {C.CYAN}/stats{C.RESET}    — Show session statistics")
        self.stdout.write(f"  {C.CYAN}/new{C.RESET}      — Start a new session")
        self.stdout.write(f"  {C.CYAN}/quit{C.RESET}     — Exit the chat")

    def _print_history(self):
        """Print the conversation history for the current session."""
        C = self.Colors

        try:
            orchestrator = AgentService.create_orchestrator(self.session)
            messages = orchestrator.get_history_display()
        except Exception:
            from chatbot.services import MessageService

            messages = MessageService.format_messages_for_display(
                MessageService.get_conversation_history(self.session.id)
            )

        if not messages:
            self.stdout.write(f"\n{C.DIM}(No messages yet){C.RESET}")
            return

        self.stdout.write(f"\n{C.BOLD}Conversation History:{C.RESET}")
        self.stdout.write(f"{C.DIM}{'─' * 50}{C.RESET}")

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "human":
                prefix = f"{C.GREEN}You"
            elif role == "ai":
                prefix = f"{C.CYAN}AI"
            elif role == "system":
                prefix = f"{C.YELLOW}System"
                content = content[:200] + ("..." if len(content) > 200 else "")
            else:
                prefix = f"{C.DIM}{role}"

            self.stdout.write(f"  {prefix}:{C.RESET} {content}")

        self.stdout.write(f"{C.DIM}{'─' * 50}{C.RESET}")
        self.stdout.write(f"  Total: {len(messages)} messages")

    def _print_tools(self):
        """Print enabled tools for the current user."""
        C = self.Colors
        from chatbot.services import ToolService

        tools = ToolService.get_user_tools(self.user, enabled_only=False)

        self.stdout.write(f"\n{C.BOLD}Tools:{C.RESET}")
        self.stdout.write(f"{C.DIM}{'─' * 50}{C.RESET}")

        for t in tools:
            status = f"{C.GREEN}ON{C.RESET}" if t.is_enabled else f"{C.RED}OFF{C.RESET}"
            self.stdout.write(
                f"  {t.icon or '🔧'} {t.tool_display_name:<25} [{status}]"
            )

        if not tools:
            self.stdout.write(f"  {C.DIM}(No tools configured){C.RESET}")

    def _print_stats(self):
        """Print session statistics."""
        C = self.Colors

        self.stdout.write(f"\n{C.BOLD}Session Stats:{C.RESET}")
        self.stdout.write(f"{C.DIM}{'─' * 50}{C.RESET}")
        self.stdout.write(f"  Session ID:  {self.session.thread_id}")
        self.stdout.write(f"  Title:       {self.session.title}")
        self.stdout.write(f"  Messages:    {self.session.message_count}")
        self.stdout.write(f"  Tokens Used: {self.session.total_tokens_used}")
        self.stdout.write(f"  Model:       {self.session.model_name}")
        self.stdout.write(f"  Temperature: {self.session.temperature}")
        self.stdout.write(
            f"  Created:     {self.session.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
        self.stdout.write(
            f"  Last Active: "
            f"{self.session.last_message_at.strftime('%Y-%m-%d %H:%M') if self.session.last_message_at else 'N/A'}"
        )
        self.stdout.write(
            f"  Summarize:   {'ON' if self.session.enable_summarization else 'OFF'}"
        )
        self.stdout.write(
            f"  Threshold:   {self.session.summarization_threshold} tokens"
        )
