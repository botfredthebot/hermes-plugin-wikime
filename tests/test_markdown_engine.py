"""Unit tests for WikiMe Markdown Engine."""

import os
import shutil
import unittest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.markdown_engine import WikiMarkdownEngine


class TestWikiMarkdownEngine(unittest.TestCase):
    def setUp(self):
        self.test_vault = "/tmp/wikime_test_vault"
        self.engine = WikiMarkdownEngine(self.test_vault)

    def tearDown(self):
        if os.path.exists(self.test_vault):
            shutil.rmtree(self.test_vault)

    def test_create_page(self):
        """New page should have correct structure."""
        path = self.engine.create_page(
            title="Project-Alpha",
            summary="Initial setup",
            content="- Language: Python\n- Framework: Django",
        )
        self.assertTrue(os.path.exists(path))

        with open(path, "r") as f:
            content = f.read()

        self.assertIn("# Project-Alpha", content)
        self.assertIn("## 🚀 Active Configuration", content)
        self.assertIn("- Language: Python", content)
        self.assertIn("## 📜 Evolution & Changelog", content)
        self.assertIn("### 🕒", content)
        self.assertIn("Initialized", content)

    def test_page_exists(self):
        self.assertFalse(self.engine.page_exists("NonExistent"))
        self.engine.create_page("Test", "Summary", "Content")
        self.assertTrue(self.engine.page_exists("Test"))

    def test_update_page_archives_old_content(self):
        """Updating should archive old active content into changelog."""
        # Create
        self.engine.create_page(
            title="Project-Beta",
            summary="Initial setup with Node.js",
            content="- Runtime: Node.js\n- Framework: Express",
        )

        # Update
        self.engine.update_page(
            title="Project-Beta",
            summary="Migrated to Python for AI features",
            new_content="- Runtime: Python\n- Framework: FastAPI",
        )

        content = self.engine.read_page("Project-Beta") or ""

        # New content should be in active section
        self.assertIn("- Runtime: Python", content.split("---")[0])
        self.assertIn("- Framework: FastAPI", content.split("---")[0])

        # Old content should be archived in details block
        self.assertIn("View Previous Configuration", content)
        self.assertIn("- Runtime: Node.js", content)

        # Changelog entry should exist
        self.assertIn("Migrated to Python", content)

    def test_update_nonexistent_page_creates(self):
        """Updating a page that doesn't exist should create it."""
        path = self.engine.update_page(
            title="New-Project",
            summary="Created from update",
            new_content="- Stack: Go",
        )
        self.assertTrue(os.path.exists(path))
        content = self.engine.read_page("New-Project") or ""
        self.assertIn("- Stack: Go", content)

    def test_read_active_section(self):
        """read_active_section should return only the top part."""
        self.engine.create_page("Test", "S", "- Key: value")
        active = self.engine.read_active_section("Test") or ""
        self.assertIn("- Key: value", active)
        self.assertNotIn("Evolution", active)

    def test_list_pages(self):
        self.engine.create_page("Page-A", "S", "C")
        self.engine.create_page("Page-B", "S", "C")
        pages = self.engine.list_pages()
        self.assertIn("Page-A", pages)
        self.assertIn("Page-B", pages)

    def test_sane_filename(self):
        """Special characters in titles should be sanitized."""
        path = self.engine.create_page("Project: Alpha/Beta", "S", "C")
        self.assertTrue(os.path.exists(path))


class TestBulkLoaderParser(unittest.TestCase):
    """Test the Telegram JSON parsing logic."""

    def test_extract_turns_basic(self):
        from src.bulk_loader import extract_turns
        data = {
            "messages": [
                {"type": "message", "id": 1, "from": "Kit Bryan", "text": "What's the tech stack?", "date": "2026-01-01"},
                {"type": "message", "id": 2, "from": "Hermes", "text": "We use Python and PostgreSQL.", "date": "2026-01-01"},
                {"type": "message", "id": 3, "from": "Kit Bryan", "text": "Thanks!", "date": "2026-01-01"},
                {"type": "message", "id": 4, "from": "Hermes", "text": "You're welcome!", "date": "2026-01-01"},
            ]
        }
        turns = extract_turns(data)
        # Should extract the first real turn, skip the "Thanks!" one (too short)
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["user_text"], "What's the tech stack?")

    def test_extract_text_from_array(self):
        from src.bulk_loader import _extract_text
        # Telegram sometimes sends text as array of strings/objects
        result = _extract_text(["Hello ", {"text": "world"}])
        self.assertEqual(result, "Hello  world")

    def test_extract_text_from_string(self):
        from src.bulk_loader import _extract_text
        self.assertEqual(_extract_text("plain text"), "plain text")


if __name__ == "__main__":
    unittest.main()
