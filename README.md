# 🧠 WikiMe — Personal Knowledge Wiki for Hermes Agent

WikiMe is a plugin for [Hermes Agent](https://github.com/nousresearch/hermes-agent) that automatically extracts decisions, preferences, and architectural facts from your conversations and saves them as structured Markdown files with full evolution tracking.

## Features

- **🟡 Automatic Triage** — After each conversation turn, decides if the content is wiki-worthy (preferences, project specs, business decisions) or noise (greetings, short fixes, thanks).
- **📜 Evolution Changelog** — When you change your mind about a stack or spec, old content is archived into collapsible `<details>` blocks with timestamps and reasoning. Never lose context.
- **📂 File-Based Vault** — All pages are plain Markdown in `~/.hermes/plugins/wikime/vault/`. Readable in any editor, version-controllable with git.
- **🔒 AES-256-GCM Encryption** — Optional encryption layer keeps sensitive data secure on disk.
- **📥 Bulk Importer** — CLI tool to import Telegram conversation exports chronologically.
- **💬 Telegram Commands** — `/wiki list`, `/wiki view <title>`, `/wiki recent`.
- **🖥️ Three-Pane Dashboard** — Web UI with page navigator, markdown workspace, and knowledge graph visualization.

## Installation

```bash
# Clone into your Hermes plugins directory
cd ~/.hermes/plugins/
git clone https://github.com/<you>/hermes-plugin-wikime.git wikime

# Restart Hermes to register the plugin
hermes gateway restart
```

## Usage

### Telegram Commands

| Command | Description |
|---------|-------------|
| `/wiki list` | List all wiki pages |
| `/wiki view <title>` | View a page's active configuration |
| `/wiki recently` | Show recently updated pages |

### Bulk Import from Telegram Export

```bash
# Export your Telegram chat as JSON, then:
cd ~/.hermes/plugins/wikime
python3 -m src.bulk_loader path/to/result.json --dry-run  # Preview
python3 -m src.bulk_loader path/to/result.json            # Import
```

### Running Tests

```bash
cd ~/.hermes/plugins/wikime
python3 -m unittest tests.test_markdown_engine -v
```

## Wiki Page Anatomy

Each page is a Markdown file with two clear sections:

```markdown
# Project Nexus Architecture
**Last Updated**: 2026-06-02

## 🚀 Active Configuration
- Language: Go
- Database: PostgreSQL 17

---
## 📜 Evolution & Changelog

### 🕒 2026-06-02: Migrated from Python to Go
* Context: Performance bottleneck on websocket connections
* Reasoning: Python's GIL couldn't handle concurrent data ingestion
* Archived Snapshot:
<details>
<summary>View Previous Configuration</summary>

- Language: Python 3.11
- Framework: FastAPI

</details>

### 🕒 2026-05-15: Initial Project Setup
* Context: Initial MVP scoped out
* Reasoning: Team agreed on Python for rapid prototyping
```

Hidden in each changelog entry is a JSON metadata comment that links back to the original conversation turn:

```html
<!-- {"session_id": "tg_8719181389", "message_id": "msg_4402", "channel": "telegram"} -->
```

## Architecture

```
~/.hermes/plugins/wikime/
├── plugin.yaml              # Hermes plugin manifest
├── __init__.py              # register(ctx): hooks + commands + API
├── src/
│   ├── markdown_engine.py   # Core: create/update/read pages
│   ├── security.py          # AES-256-GCM encryption
│   ├── bulk_loader.py       # Telegram JSON import CLI
│   └── __init__.py
├── web/
│   └── dist/
│       └── index.html       # Three-pane dashboard UI
├── tests/
│   ├── __init__.py
│   └── test_markdown_engine.py
├── vault/                   # Auto-generated Markdown pages
├── secret/                  # Encryption keys (chmod 600)
└── README.md
```

## Triage Rules

WikiMe saves content that matches these categories:

| Category | Examples |
|----------|---------|
| Tech Stack | Languages, frameworks, databases, tools |
| Architecture | Project structure, API design, deployment |
| Preferences | Coding style, naming conventions, standards |
| Business | Goals, strategies, client info |
| Artifacts | Scripts, configs, deployment checklists |

And filters out:

| Noise | Examples |
|-------|---------|
| Greetings | "Hi", "Thanks", "You're welcome" |
| Transitions | "Let me check", "Hold on", "Ok" |
| Short fixes | Typo corrections, one-line debugging |
| Meta-chat | "Rewrite this", "Change the tone" |

## License

MIT — see [LICENSE](LICENSE) for details.
