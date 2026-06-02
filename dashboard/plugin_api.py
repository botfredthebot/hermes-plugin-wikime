"""
WikiMe Dashboard API — FastAPI router served at /api/plugins/wikime/

Endpoints:
  GET  /api/plugins/wikime/pages        — List all pages
  GET  /api/plugins/wikime/page          — Get a page by title (?title=...)
  GET  /api/plugins/wikime/stats         — Vault statistics
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolve vault path
# ---------------------------------------------------------------------------

VAULT_PATH = Path(os.path.expanduser("~/.hermes/plugins/wikime/vault"))


def _safe_title(title: str) -> str:
    """Prevent path traversal."""
    safe = title.replace("..", "").replace("/", "").replace("\\", "")
    if not safe.strip():
        raise HTTPException(status_code=400, detail="Invalid page title")
    return safe


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()


@router.get("/pages")
async def list_pages():
    """List all wiki pages."""
    if not VAULT_PATH.is_dir():
        return {"pages": [], "total": 0}

    pages = []
    for f in sorted(VAULT_PATH.iterdir()):
        if f.suffix != ".md":
            continue
        stat = f.stat()
        pages.append({
            "title": f.stem,
            "size": stat.st_size,
            "modified": int(stat.st_mtime),
        })

    return {"pages": pages, "total": len(pages)}


@router.get("/page")
async def get_page(title: str = Query(..., min_length=1)):
    """Get a wiki page's raw markdown content."""
    safe = _safe_title(title)
    filepath = VAULT_PATH / f"{safe}.md"

    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Page '{title}' not found")

    return {
        "title": safe,
        "markdown": filepath.read_text(encoding="utf-8"),
    }


@router.get("/stats")
async def vault_stats():
    """Return vault statistics."""
    if not VAULT_PATH.is_dir():
        return {"pages": 0, "total_revisions": 0}

    pages = list(VAULT_PATH.glob("*.md"))
    total_revisions = 0
    for p in pages:
        text = p.read_text(encoding="utf-8")
        # Count changelog entries by counting ### headers in Evolution section
        if "📜 Evolution & Changelog" in text:
            section = text.split("📜 Evolution & Changelog")[1]
            total_revisions += section.count("### 🕒")

    return {
        "pages": len(pages),
        "total_revisions": total_revisions,
    }
