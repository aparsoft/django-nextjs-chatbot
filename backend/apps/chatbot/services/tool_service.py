"""
Tool Service

Handles tool management and execution for LangGraph agents.

Usage:
    from ..services import ToolService

    # Get enabled tools for user
    tools = ToolService.get_user_tools(user)

    # Enable a tool
    ToolService.enable_tool(user, "web_search")
"""

from typing import List, Dict, Any, Optional
from uuid import UUID

from langchain_core.tools import BaseTool
from ..models import UserTool, AvailableTool
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
        query = UserTool.objects.filter(user=user)

        if enabled_only:
            query = query.filter(is_enabled=True)

        return list(query.select_related("available_tool"))

    @staticmethod
    def enable_tool(
        user: CustomUser, tool_name: str, configuration: Optional[Dict[str, Any]] = None
    ) -> UserTool:
        """
        Enable a tool for user.

        Args:
            user: The user
            tool_name: Tool internal name
            configuration: Tool configuration

        Returns:
            Created/updated UserTool instance
        """
        available_tool = AvailableTool.objects.get(tool_name=tool_name, is_active=True)

        user_tool, created = UserTool.objects.get_or_create(
            user=user,
            available_tool=available_tool,
            defaults={
                "tool_name": tool_name,
                "tool_display_name": available_tool.display_name,
                "is_enabled": True,
                "configuration": configuration or {},
            },
        )

        if not created:
            user_tool.is_enabled = True
            if configuration:
                user_tool.configuration = configuration
            user_tool.save()

        return user_tool

    @staticmethod
    def disable_tool(user: CustomUser, tool_name: str) -> None:
        """
        Disable a tool for user.

        Args:
            user: The user
            tool_name: Tool internal name
        """
        UserTool.objects.filter(user=user, tool_name=tool_name).update(is_enabled=False)

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
        UserTool.objects.filter(user=user, tool_name=tool_name).update(
            usage_count=models.F("usage_count") + 1, last_used_at=timezone.now()
        )
