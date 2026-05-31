"""
Tool Service

Handles tool management and execution for LangGraph agents.

Usage:
    from ..services import ToolService

    # Get enabled tools for user
    tools = ToolService.get_user_tools(user)

    # Enable a tool (from TOOL_REGISTRY)
    ToolService.enable_tool(user, "web_search")

    # Seed all tools for a new user
    ToolService.seed_tools_for_user(user)
"""

from typing import List, Dict, Any, Optional

from langchain_core.tools import BaseTool
from ..models import UserTool
from ..models.user_tool import TOOL_REGISTRY
from accounts.models import CustomUser


class ToolService:
    """Service for managing user tools."""

    @staticmethod
    def get_user_tools(user: CustomUser, enabled_only: bool = True) -> List[UserTool]:
        """
        Get user's tools.

        Args:
            user: The user
            enabled_only: Only return enabled tools

        Returns:
            List of UserTool instances
        """
        return UserTool.get_enabled_for_user(user) if enabled_only else list(
            UserTool.objects.filter(user=user)
        )

    @staticmethod
    def enable_tool(
        user: CustomUser, tool_name: str, configuration: Optional[Dict[str, Any]] = None
    ) -> UserTool:
        """
        Enable a tool for user (delegates to model method).

        Args:
            user: The user
            tool_name: Tool internal name (must exist in TOOL_REGISTRY)
            configuration: Tool configuration

        Returns:
            UserTool instance
        """
        return UserTool.enable_tool(user, tool_name, configuration)

    @staticmethod
    def disable_tool(user: CustomUser, tool_name: str) -> None:
        """
        Disable a tool for user.

        Args:
            user: The user
            tool_name: Tool internal name
        """
        UserTool.disable_tool(user, tool_name)

    @staticmethod
    def seed_tools_for_user(user: CustomUser) -> None:
        """
        Create UserTool entries for every tool in TOOL_REGISTRY.

        Call this after user registration so the frontend can show
        all available tools with toggle switches.

        Args:
            user: The newly registered user
        """
        UserTool.seed_all_tools(user)

    @staticmethod
    def get_tool_instances(user: CustomUser) -> List[BaseTool]:
        """
        Get LangChain tool instances for user.

        Args:
            user: The user

        Returns:
            List of LangChain BaseTool instances

        Example:
            tools = ToolService.get_tool_instances(user)

            # Use with agent
            agent = create_react_agent(
                model=model,
                tools=tools,
                checkpointer=checkpointer
            )
        """
        user_tools = ToolService.get_user_tools(user, enabled_only=True)

        # TODO: Implement tool loading logic
        # This would load actual LangChain tools based on tool_name
        # For now, return empty list
        return []

    @staticmethod
    def check_rate_limit(user: CustomUser, tool_name: str) -> Dict[str, Any]:
        """
        Check if user has exceeded tool rate limit.

        Args:
            user: The user
            tool_name: Tool to check

        Returns:
            Dict with allowed status
        """
        try:
            user_tool = UserTool.objects.get(
                user=user, tool_name=tool_name, is_enabled=True
            )
            return user_tool.check_rate_limit()
        except UserTool.DoesNotExist:
            return {"allowed": False, "reason": "Tool not enabled"}

    @staticmethod
    def increment_tool_usage(user: CustomUser, tool_name: str) -> None:
        """
        Increment tool usage counter.

        Args:
            user: The user
            tool_name: Tool that was used
        """
        from django.utils import timezone
        from django.db import models

        UserTool.objects.filter(user=user, tool_name=tool_name).update(
            usage_count=models.F("usage_count") + 1, last_used_at=timezone.now()
        )
