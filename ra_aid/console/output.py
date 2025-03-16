from typing import Any, Dict, Literal, Optional, Sequence

from langchain_core.messages import AIMessage, BaseMessage
from rich.markdown import Markdown
from rich.panel import Panel

from ra_aid.exceptions import ToolExecutionError
from ra_aid.callbacks.anthropic_callback_handler import AnthropicCallbackHandler
from ra_aid.database.repositories.config_repository import get_config_repository
from ra_aid.config import DEFAULT_SHOW_COST

from .formatting import console


def get_cost_subtitle() -> Optional[str]:
    """Generate a subtitle with cost information if cost tracking is enabled and show_cost is enabled."""

    if not get_config_repository().get("show_cost", DEFAULT_SHOW_COST):
        return None

    # Get the current singleton instance
    callback = AnthropicCallbackHandler._instances.get(AnthropicCallbackHandler, None)

    if not callback:
        return None

    if hasattr(callback, "session_totals") and callback.session_totals:
        cost = callback.session_totals.get("cost", 0.0)
        tokens = callback.session_totals.get("tokens", 0)
        return f"Cost: ${cost:.6f} | Tokens: {tokens}"

    # Fallback to direct values if session_totals not available
    return f"Cost: ${callback.total_cost:.6f} | Tokens: {callback.total_tokens}"


def print_agent_output(
    chunk: Dict[str, Any],
    agent_type: Literal["CiaynAgent", "React"],
) -> None:
    """Print only the agent's message content, not tool calls.

    Args:
        chunk: A dictionary containing agent or tool messages.
        agent_type: Specifies the type of agent. 'CiaynAgent' handles tool errors internally, while 'React' raises a ToolExecutionError.
    """
    if "agent" in chunk and "messages" in chunk["agent"]:
        messages = chunk["agent"]["messages"]
        for msg in messages:
            if isinstance(msg, AIMessage):
                # Handle text content
                if isinstance(msg.content, list):
                    for content in msg.content:
                        if content["type"] == "text" and content["text"].strip():
                            subtitle = get_cost_subtitle()

                            console.print(
                                Panel(
                                    Markdown(content["text"]),
                                    title="🤖 Assistant",
                                    subtitle=subtitle,
                                    subtitle_align="right",
                                )
                            )
                else:
                    if msg.content.strip():
                        subtitle = get_cost_subtitle()

                        console.print(
                            Panel(
                                Markdown(msg.content.strip()),
                                title="🤖 Assistant",
                                subtitle=subtitle,
                                subtitle_align="right",
                            )
                        )
    elif "tools" in chunk and "messages" in chunk["tools"]:
        for msg in chunk["tools"]["messages"]:
            if msg.status == "error" and msg.content:
                err_msg = msg.content.strip()
                subtitle = get_cost_subtitle()

                console.print(
                    Panel(
                        Markdown(err_msg),
                        title="❌ Tool Error",
                        subtitle=subtitle,
                        subtitle_align="right",
                        border_style="red bold",
                    )
                )
                tool_name = getattr(msg, "name", None)

                # CiaynAgent handles this internally
                if agent_type == "React":
                    raise ToolExecutionError(
                        err_msg, tool_name=tool_name, base_message=msg
                    )


def cpm(message: str, title: Optional[str] = None, border_style: str = "blue", subtitle: Optional[str] = None) -> None:
    """
    Print a message using a Panel with Markdown formatting.

    Args:
        message (str): The message content to display.
        title (Optional[str]): An optional title for the panel.
        border_style (str): Border style for the panel.
        subtitle (Optional[str]): An optional subtitle for the panel. If None, will try to get cost subtitle.
    """
    if subtitle is None:
        subtitle = get_cost_subtitle()
        
    console.print(Panel(
        Markdown(message), 
        title=title, 
        border_style=border_style,
        subtitle=subtitle,
        subtitle_align="right" if subtitle else None
    ))


def console_panel(
    message: str, 
    title: Optional[str] = None, 
    border_style: str = "blue",
    subtitle: Optional[str] = None,
    subtitle_align: str = "right",
    padding: tuple = (1, 1),
    expand: bool = True,
    safe_box: bool = True,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> None:
    """
    Print a message using a Panel without Markdown formatting, with all panel options available.

    Args:
        message (str): The message content to display.
        title (Optional[str]): An optional title for the panel.
        border_style (str): Border style for the panel.
        subtitle (Optional[str]): An optional subtitle for the panel. If None, will try to get cost subtitle.
        subtitle_align (str): Alignment for the subtitle ("left", "center", or "right").
        padding (tuple): Padding for the panel content (vertical, horizontal).
        expand (bool): Whether the panel should expand to fill available width.
        safe_box (bool): Whether to use ASCII characters instead of Unicode for the box.
        width (Optional[int]): Optional fixed width for the panel.
        height (Optional[int]): Optional fixed height for the panel.
    """
    if subtitle is None:
        subtitle = get_cost_subtitle()
        
    console.print(
        Panel(
            message,
            title=title,
            border_style=border_style,
            subtitle=subtitle,
            subtitle_align=subtitle_align if subtitle else None,
            padding=padding,
            expand=expand,
            safe_box=safe_box,
            width=width,
            height=height,
        )
    )


def print_messages_compact(messages: Sequence[BaseMessage]) -> None:
    """Print a compact representation of a list of messages.

    Warning: Used mainly for debugging purposes so do not delete if not referenced anywhere!
    For all message types, only the first 30 characters of content are shown.

    Args:
        messages: A sequence of BaseMessage objects to print
    """
    if not messages:
        console.print("[italic]No messages[/italic]")
        return

    for i, msg in enumerate(messages):
        msg_type = msg.__class__.__name__
        content = msg.content

        # Process content based on its type
        if isinstance(content, str):
            display_content = f"{content[:30]}..." if len(content) > 30 else content
        elif isinstance(content, list):
            # Handle structured content (list of content blocks)
            content_preview = []
            for item in content[:2]:  # Show first 2 items at most
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text = item.get("text", "")
                        content_preview.append(
                            f"text: {text[:20]}..."
                            if len(text) > 20
                            else f"text: {text}"
                        )
                    elif item.get("type") == "tool_call":
                        tool_name = item.get("tool_call", {}).get("name", "unknown")
                        content_preview.append(f"tool_call: {tool_name}")
                    else:
                        content_preview.append(f"{item.get('type', 'unknown')}")

            if len(content) > 2:
                content_preview.append(f"...({len(content)-2} more)")

            display_content = ", ".join(content_preview)
        else:
            display_content = (
                str(content)[:30] + "..." if len(str(content)) > 30 else str(content)
            )

        # Add additional tool message info if available
        additional_info = []
        if hasattr(msg, "tool_call_id") and msg.tool_call_id:
            additional_info.append(f"tool_call_id: {msg.tool_call_id}")
        if hasattr(msg, "name") and msg.name:
            additional_info.append(f"name: {msg.name}")
        if hasattr(msg, "status") and msg.status:
            additional_info.append(f"status: {msg.status}")

        info_str = f" ({', '.join(additional_info)})" if additional_info else ""
        console.print(f"[{i}] [bold]{msg_type}{info_str}[/bold]: {display_content}")
