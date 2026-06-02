"""
WikiMe Bulk Loader — import Telegram conversation history from JSON export.

Usage:
    python -m wikime.bulk_loader path/to/result.json [--dry-run] [--max-turns N]

The TelegramDesktop export format has a top-level "messages" array.
Each message has: type, id, from, from_id, text, date.

We pair consecutive user→bot turns and run each through the wiki triage.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime

# Add parent to path so we can import as a module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.markdown_engine import WikiMarkdownEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Telegram JSON parser
# ---------------------------------------------------------------------------

def extract_turns(data: dict, bot_names: list[str] | None = None) -> list[dict]:
    """
    Extract user→bot QA turn pairs from Telegram export JSON.

    Returns list of dicts with keys: user_text, bot_text, date, msg_id
    """
    if bot_names is None:
        bot_names = ["fred", "hermes", "owl", "botfred"]

    messages = data.get("messages", [])
    turns = []

    for i in range(len(messages) - 1):
        curr = messages[i]
        nxt = messages[i + 1]

        # Both must be actual messages
        if curr.get("type") != "message" or nxt.get("type") != "message":
            continue

        curr_from = (curr.get("from") or "").lower()
        nxt_from = (nxt.get("from") or "").lower()

        # Skip empty
        if not curr_from or not nxt_from:
            continue

        # Check if next message is from bot
        is_bot_reply = nxt_from in bot_names

        # Skip same-sender pairs
        if curr_from == nxt_from:
            continue

        if not is_bot_reply:
            continue

        user_text = _extract_text(curr.get("text"))
        bot_text = _extract_text(nxt.get("text"))

        if not user_text or not bot_text:
            continue

        # Skip very short / trivial turns
        if len(user_text) < 15 and len(bot_text) < 50:
            continue

        turns.append({
            "user_text": user_text[:2000],
            "bot_text": bot_text[:2000],
            "date": nxt.get("date", ""),
            "msg_id": str(nxt.get("id", "")),
        })

    return turns


def _extract_text(text_field) -> str:
    """Convert Telegram's mixed text format to plain string."""
    if isinstance(text_field, str):
        return text_field.strip()
    if isinstance(text_field, list):
        parts = []
        for item in text_field:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
        return " ".join(parts).strip()
    return ""


# ---------------------------------------------------------------------------
# Triage — simple rule-based (no LLM needed for basic extraction)
# ---------------------------------------------------------------------------

# Keywords that suggest wiki-worthiness
WIKI_KEYWORDS = [
    "prefer", "always use", "never use", "standard", "convention",
    "architecture", "stack", "deploy", "database", "framework",
    "project", "feature", "requirement", "spec", "api",
    "config", "setup", "install", "secret", "key", "token",
    "business", "goal", "strategy", "customer", "revenue",
    "recipe", "ingredient", "cook", "bbq", "street food",
]

NOISE_PATTERNS = [
    "thanks", "thank you", "ok", "okay", "sure", "great",
    "sounds good", "no problem", "you're welcome",
    "let me check", "let me see", "hold on", "one moment",
    "ha ha", "lol", "nice", "cool", "awesome",
]


def triage_turn(user_text: str, bot_text: str) -> dict | None:
    """
    Simple rule-based triage. Returns None if not wiki-worthy.

    For production use, this would call an LLM. For the bulk loader
    we use keyword heuristics to avoid API costs.
    """
    combined = (user_text + " " + bot_text).lower()

    # Skip noise
    for noise in NOISE_PATTERNS:
        if combined.startswith(noise) and len(combined) < 100:
            return None

    # Check for wiki-worthy keywords
    matched_keywords = [kw for kw in WIKI_KEYWORDS if kw in combined]
    if not matched_keywords:
        return None

    # Determine a page title from the content
    title = _guess_page_title(combined, matched_keywords)

    # Build active content summary
    summary = _build_summary(user_text, bot_text)

    return {
        "page_title": title,
        "summary": summary,
        "content": summary,
    }


def _guess_page_title(text: str, keywords: list[str]) -> str:
    """Derive a page title from the conversation content."""
    # Simple heuristic: look for project names or use keyword categories
    if any(kw in text for kw in ["project", "app", "site", "platform"]):
        # Try to extract a proper noun after "project"
        import re
        m = re.search(r'project\s+([A-Z][a-zA-Z0-9-_]+)', text, re.IGNORECASE)
        if m:
            return m.group(1)
    if any(kw in text for kw in ["stack", "framework", "language", "database"]):
        return "Tech-Stack"
    if any(kw in text for kw in ["deploy", "config", "setup", "install"]):
        return "Deployment"
    if any(kw in text for kw in ["recipe", "cook", "bbq", "food", "ingredient"]):
        return "Recipes"
    if any(kw in text for kw in ["business", "goal", "strategy", "revenue"]):
        return "Business-Strategy"
    if any(kw in text for kw in ["api", "endpoint", "route"]):
        return "API-Design"
    return "General-Notes"


def _build_summary(user_text: str, bot_text: str) -> str:
    """Build a one-line summary of the turn."""
    # Use the first meaningful line from the user message
    for line in user_text.split("\n"):
        line = line.strip()
        if len(line) > 10 and not line.startswith(("#", ">", "-")):
            return line[:200]
    return user_text[:200]


# ---------------------------------------------------------------------------
# Main import logic
# ---------------------------------------------------------------------------

async def run_import(
    json_path: str,
    vault_path: str,
    dry_run: bool = False,
    max_turns: int | None = None,
    delay: float = 0.05,
) -> dict:
    """
    Load Telegram JSON, extract turns, triage, and write to vault.

    Returns stats dict.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    turns = extract_turns(data)
    if max_turns:
        turns = turns[:max_turns]

    engine = WikiMarkdownEngine(vault_path)

    stats = {"total_turns": len(turns), "wiki_worthy": 0, "skipped": 0, "errors": 0}

    for i, turn in enumerate(turns):
        result = triage_turn(turn["user_text"], turn["bot_text"])

        if result is None:
            stats["skipped"] += 1
            continue

        stats["wiki_worthy"] += 1

        if dry_run:
            print(f"[DRY] {result['page_title']}: {result['summary'][:60]}")
            continue

        metadata = {
            "session_id": "telegram",
            "message_id": turn["msg_id"],
            "channel": "telegram_import",
            "date": turn.get("date", ""),
        }

        try:
            if engine.page_exists(result["page_title"]):
                engine.update_page(
                    title=result["page_title"],
                    summary=result["summary"],
                    new_content=result["content"],
                    metadata=metadata,
                )
            else:
                engine.create_page(
                    title=result["page_title"],
                    summary=result["summary"],
                    content=result["content"],
                    metadata=metadata,
                )
        except Exception as e:
            stats["errors"] += 1
            logger.error("[WikiMe] Error writing page: %s", e)

        if delay > 0:
            await asyncio.sleep(delay)

        # Progress
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(turns)} turns processed...")

    return stats


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="WikiMe Bulk Loader — import Telegram history")
    parser.add_argument("json_path", help="Path to Telegram result.json export")
    parser.add_argument("--vault", default="~/.hermes/plugins/wikime/vault", help="Vault directory")
    parser.add_argument("--dry-run", action="store_true", help="Parse but don't write")
    parser.add_argument("--max-turns", type=int, default=None, help="Limit number of turns")
    parser.add_argument("--delay", type=float, default=0.01, help="Delay between writes (seconds)")
    args = parser.parse_args()

    vault = os.path.expanduser(args.vault)
    os.makedirs(vault, exist_ok=True)

    print(f"[WikiMe] Loading: {args.json_path}")
    print(f"[WikiMe] Vault: {vault}")
    if args.dry_run:
        print("[wikiMe] DRY RUN — no files will be written")

    stats = asyncio.run(run_import(
        json_path=args.json_path,
        vault_path=vault,
        dry_run=args.dry_run,
        max_turns=args.max_turns,
        delay=args.delay,
    ))

    print(f"\n{'='*50}")
    print(f"[WikiMe] Import complete!")
    print(f"  Turns parsed:     {stats['total_turns']}")
    print(f"  Wiki-worthy:      {stats['wiki_worthy']}")
    print(f"  Skipped (noise):  {stats['skipped']}")
    print(f"  Errors:           {stats['errors']}")
    print(f"  Pages in vault:   {len([f for f in os.listdir(vault) if f.endswith('.md')])}")


if __name__ == "__main__":
    main()
