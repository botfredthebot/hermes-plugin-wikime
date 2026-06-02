"""
WikiMe Plugin — Automated personal knowledge wiki for Hermes Agent.

Hooks into conversation turns to extract wiki-worthy content and
maintain a vault of structured Markdown pages with evolution timelines.
"""

from __future__ import annotations

import json
import logging
import os

from .src.markdown_engine import WikiMarkdownEngine

logger = logging.getLogger(__name__)

# Global engine instance, initialised in register()
_engine: WikiMarkdownEngine | None = None


# ---------------------------------------------------------------------------
# Hook callbacks
# ---------------------------------------------------------------------------

async def _on_post_llm_call(response_text: str, user_message: str, **kwargs) -> None:
    """
    After the LLM replies, triage the turn for wiki-worthy content.

    This runs on post_llm_call hook. We ask the agent (via a lightweight
    prompt) whether the turn contains long-term facts, preferences, or
    architectural decisions worth saving.
    """
    global _engine
    if _engine is None:
        return

    # Skip very short / trivial turns
    if not user_message or len(user_message.strip()) < 15:
        return

    # Build triage prompt
    triage_prompt = (
        "You are the WikiMe triage agent. Analyse the following conversation turn.\n"
        "Determine if it contains ANY of the following:\n"
        "  - Long-term preferences (tech stack, coding style, tools)\n"
        "  - Project specifications or architecture decisions\n"
        "  - Reusable artifacts (scripts, commands, configurations)\n"
        "  - Business goals, strategies, or important facts\n\n"
        "Respond STRICTLY with valid JSON only (no markdown fences):\n"
        '{\n'
        '  "wiki_worthy": true or false,\n'
        '  "page_title": "Short-Descriptive-Title" or "",\n'
        '  "summary": "One-line description of what changed" or "",\n'
        '  "active_content": "Markdown bullet list of current config" or ""\n'
        '}\n\n'
        f"User message:\n{user_message[:500]}\n\n"
        f"Assistant response:\n{response_text[:500]}\n"
    )

    try:
        # We can't call the agent directly from a hook — instead we write
        # a triage request to a queue file that the agent picks up on next turn.
        # For now, log the intent. The bulk_loader handles historical import.
        logger.debug("[WikiMe] Triage queued for turn: %s...", user_message[:80])
    except Exception as e:
        logger.debug("[WikiMe] Triage error: %s", e)


async def _on_session_end(session_id: str, **kwargs) -> None:
    """Clean up when a session ends."""
    logger.debug("[WikiMe] Session ended: %s", session_id)


# ---------------------------------------------------------------------------
# Slash command handler
# ---------------------------------------------------------------------------

async def _wiki_command(raw_args: str) -> str | None:
    """
    Handle /wiki slash commands.

    Usage:
      /wiki list              — List all wiki pages
      /wiki view <title>      — View a page's active configuration
      /wiki recent            — Show recently updated pages
    """
    global _engine
    if _engine is None:
        return "⚠️ WikiMe engine not initialised."

    args = raw_args.strip().split()
    if not args:
        return (
            "📖 **WikiMe** — Your personal knowledge wiki\n\n"
            "Commands:\n"
            "• `/wiki list` — List all pages\n"
            "• `/wiki view <title>` — View a page\n"
            "• `/wiki recent` — Recently updated\n"
        )

    sub = args[0].lower()

    if sub == "list":
        pages = _engine.list_pages()
        if not pages:
            return "📂 Wiki vault is empty. Start chatting to build it!"
        lines = [f"• `{p}`" for p in pages]
        return f"📂 **Wiki Pages ({len(pages)}):**\n" + "\n".join(lines)

    elif sub == "view":
        if len(args) < 2:
            return "❌ Usage: `/wiki view <title>`"
        title = " ".join(args[1:])
        content = _engine.read_active_section(title)
        if content is None:
            return f"🔍 Page `{title}` not found."
        # Truncate for Telegram
        if len(content) > 3000:
            content = content[:3000] + "\n\n…(truncated)"
        return content

    elif sub == "recent":
        pages = _engine.list_pages()
        if not pages:
            return "📂 Wiki vault is empty."
        # Sort by modification time, most recent first
        vault = _engine.vault_path
        pages_sorted = sorted(
            pages,
            key=lambda p: os.path.getmtime(os.path.join(vault, f"{p}.md")),
            reverse=True,
        )
        top = pages_sorted[:10]
        lines = []
        for p in top:
            mtime = os.path.getmtime(os.path.join(vault, f"{p}.md"))
            from datetime import datetime
            dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            lines.append(f"• `{p}` — {dt}")
        return f"🕐 **Recently Updated:**\n" + "\n".join(lines)

    return f"❓ Unknown subcommand: `{sub}`. Try `/wiki list`, `/wiki view <title>`, `/wiki recent`."


# ---------------------------------------------------------------------------
# Plugin registration entry point
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Called by Hermes plugin loader on startup."""
    global _engine

    vault_path = os.path.expanduser("~/.hermes/plugins/wikime/vault")
    _engine = WikiMarkdownEngine(vault_path)

    # Register hooks
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)

    # Register slash command
    ctx.register_command(
        "wiki",
        handler=_wiki_command,
        description="WikiMe — personal knowledge wiki",
    )

    logger.info("[WikiMe] Plugin loaded. Vault: %s", vault_path)
