"""
WikiMe Markdown Engine — creates and updates wiki pages with evolution changelogs.

Each page is a Markdown file with:
  - Active Configuration section (current state)
  - Evolution & Changelog section (archived history with hidden JSON metadata)
"""

import os
import re
from datetime import datetime


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _safe_filename(title: str) -> str:
    """Sanitize a title for use as a filename."""
    return re.sub(r'[\\/*?:"<>| ]', '-', title)


WIKI_HEADER = """# {title}
**Last Updated**: {date}

## 🚀 Active Configuration
{content}

---
## 📜 Evolution & Changelog
"""

HISTORY_ENTRY = """### 🕒 {date}: {summary} <!-- {metadata} -->
* Context: {context}
* Archived Snapshot:
<details>
<summary>View Archived Configurations</summary>

{archived}

</details>
"""


class WikiMarkdownEngine:
    """Create and update wiki pages as structured Markdown files."""

    def __init__(self, vault_path: str):
        self.vault_path = vault_path
        os.makedirs(self.vault_path, exist_ok=True)

    # -- public API ---------------------------------------------------------

    def page_exists(self, title: str) -> bool:
        """Return True if a page already exists in the vault."""
        return os.path.exists(self._filepath(title))

    def create_page(
        self,
        title: str,
        summary: str,
        content: str,
        metadata: dict | None = None,
    ) -> str:
        """Create a new wiki page. Returns the file path."""
        filepath = self._filepath(title)
        meta_str = _meta_to_str(metadata or {})
        date = _now()

        text = (
            f"# {title}\n"
            f"**Last Updated**: {date}\n\n"
            f"## 🚀 Active Configuration\n"
            f"{content}\n\n"
            f"---\n"
            f"## 📜 Evolution & Changelog\n"
            f"### 🕒 {date}: Initialized <!-- {meta_str} -->\n"
            f"* Context: {summary}\n"
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)

        return filepath

    def update_page(
        self,
        title: str,
        summary: str,
        new_content: str,
        metadata: dict | None = None,
    ) -> str:
        """
        Update an existing page's Active Configuration.
        The old active content is archived into the Evolution & Changelog.
        Returns the file path.
        """
        filepath = self._filepath(title)
        meta_str = _meta_to_str(metadata or {})
        date = _now()

        if not os.path.exists(filepath):
            return self.create_page(title, summary, new_content, metadata)

        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()

        # Split into header+active and history sections
        split_marker = "---\n## 📜 Evolution & Changelog"
        if split_marker in raw:
            before, history = raw.split(split_marker, 1)
            history = history.strip()
        else:
            before = raw
            history = ""

        # Extract old active content
        active_match = re.search(
            r"## 🚀 Active Configuration\n([\s\S]*?)(?:\n\n---|\n## |\Z)", before
        )
        old_active = (
            active_match.group(1).strip() if active_match else "No previous data."
        )

        # Build new archived entry
        archived_block = (
            f"### 🕒 {date}: Updated <!-- {meta_str} -->\n"
            f"* Context: {summary}\n"
            f"* Archived Snapshot:\n"
            f"<details>\n"
            f"<summary>View Previous Configuration</summary>\n\n"
            f"{old_active}\n\n"
            f"</details>\n"
        )

        # Reassemble: new header + active + existing history + new entry
        updated = (
            f"# {title}\n"
            f"**Last Updated**: {date}\n\n"
            f"## 🚀 Active Configuration\n"
            f"{new_content}\n\n"
            f"---\n"
            f"## 📜 Evolution & Changelog\n"
        )
        if history:
            updated += f"{archived_block}{history}\n"
        else:
            updated += f"{archived_block}\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(updated)

        return filepath

    def read_page(self, title: str) -> str | None:
        """Read a page's raw markdown content. Returns None if not found."""
        filepath = self._filepath(title)
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def read_active_section(self, title: str) -> str | None:
        """Read only the Active Configuration section of a page."""
        raw = self.read_page(title)
        if raw is None:
            return None
        parts = raw.split("---")
        return parts[0].strip() if parts else raw

    def list_pages(self) -> list[str]:
        """Return a list of all page titles in the vault."""
        if not os.path.exists(self.vault_path):
            return []
        return sorted(
            f.replace(".md", "")
            for f in os.listdir(self.vault_path)
            if f.endswith(".md")
        )

    # -- internal -----------------------------------------------------------

    def _filepath(self, title: str) -> str:
        return os.path.join(self.vault_path, f"{_safe_filename(title)}.md")


def _meta_to_str(metadata: dict) -> str:
    """Convert metadata dict to compact JSON string for HTML comment."""
    if not metadata:
        return "{}"
    parts = [f'"{k}": "{v}"' for k, v in metadata.items()]
    return "{" + ", ".join(parts) + "}"
