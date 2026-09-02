"""Prompt Library - Prompt Template Manager backend.

Standalone FastAPI + SQLite app. Stores reusable prompt templates containing
{{variable}} placeholders, renders them with user-supplied values, and keeps
a history of generated prompts.

Run:
    python backend.py            # starts uvicorn on http://localhost:8090
    uvicorn backend:app --host 0.0.0.0 --port 8090   # equivalent
"""

import json
import re
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants / paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "prompt_templates.db"

# Matches {{ variable }} placeholders (whitespace tolerated, alpha-numeric + _)
PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    """Open a fresh connection (thread-safe for FastAPI's threadpool)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables if they do not exist, then seed sample templates."""
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS templates (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT 'general',
                description TEXT NOT NULL DEFAULT '',
                body        TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS history (
                id              TEXT PRIMARY KEY,
                template_id     TEXT,
                template_name   TEXT,
                variables_json  TEXT NOT NULL,
                rendered_prompt TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_templates_category ON templates(category);
            CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at);
            """
        )
    seed_if_empty()


# ---------------------------------------------------------------------------
# Seed data (subtask 4)
# ---------------------------------------------------------------------------

SEED_TEMPLATES: List[Dict[str, str]] = [
    {
        "name": "Code Review Request",
        "category": "code review",
        "description": "Ask an AI to review a code snippet or PR diff for bugs, style, and performance.",
        "body": (
            "Please perform a thorough code review of the following code.\n\n"
            "```\n{{code_snippet}}\n```\n\n"
            "Context: {{context}}\n\n"
            "Focus areas:\n"
            "1. Correctness - bugs, edge cases, and error handling.\n"
            "2. Readability and maintainability.\n"
            "3. Performance concerns.\n"
            "4. Security issues.\n\n"
            "Reply with a numbered list of findings, each with severity, "
            "explanation, and a concrete fix suggestion."
        ),
    },
    {
        "name": "Blog Post Writer",
        "category": "writing",
        "description": "Generate a structured blog post outline and draft on any topic.",
        "body": (
            "Write a blog post about \"{{topic}}\" aimed at {{audience}}.\n\n"
            "Requirements:\n"
            "- Tone: {{tone}}\n"
            "- Target length: {{word_count}} words\n"
            "- Style: engaging, scannable, with subheadings\n\n"
            "Structure the post as:\n"
            "1. A hook-driven introduction\n"
            "2. Three to five key sections with practical takeaways\n"
            "3. A conclusion with a call to action\n\n"
            "Include a suggested title and a one-line meta description."
        ),
    },
    {
        "name": "Article Summarizer",
        "category": "summarization",
        "description": "Condense a long article or document into a concise summary with key points.",
        "body": (
            "Summarize the following text in {{max_words}} words or fewer.\n\n"
            "Source text:\n\"\"\"\n{{source_text}}\n\"\"\"\n\n"
            "Requirements:\n"
            "- Capture the main argument and most important supporting points.\n"
            "- Preserve factual accuracy - do not add new information.\n"
            "- Use {{summary_style}} style.\n"
            "- End with a one-sentence takeaway."
        ),
    },
    {
        "name": "SQL Query Generator",
        "category": "sql",
        "description": "Translate a natural-language request into a SQL query for a given schema.",
        "body": (
            "Given the database schema below:\n\n"
            "{{schema}}\n\n"
            "Write a {{dialect}} SQL query that answers this question:\n"
            "\"{{question}}\"\n\n"
            "Constraints:\n"
            "- Use only tables/columns present in the schema.\n"
            "- Optimize for readability; add brief comments for non-obvious parts.\n"
            "- Output the final query in a code block, then explain it in 2-3 sentences."
        ),
    },
    {
        "name": "Professional Email Draft",
        "category": "email",
        "description": "Draft a clear, professional email for any situation.",
        "body": (
            "Write a professional email to {{recipient}} about: {{subject}}.\n\n"
            "Key points to cover:\n{{key_points}}\n\n"
            "Tone: {{tone}}.\n"
            "Call to action: {{call_to_action}}\n\n"
            "Guidelines:\n"
            "- Concise and polite, with a clear subject line.\n"
            "- No jargon; assume a busy reader.\n"
            "- Offer alternatives or next steps where appropriate."
        ),
    },
    {
        "name": "Bug Debugging Assistant",
        "category": "debugging",
        "description": "Describe a bug and get a structured diagnosis with likely root causes.",
        "body": (
            "I'm debugging an issue in my {{language}} project.\n\n"
            "What I expected: {{expected_behavior}}\n"
            "What actually happens: {{actual_behavior}}\n\n"
            "Relevant code or stack trace:\n```\n{{code_or_trace}}\n```\n\n"
            "Steps already tried: {{steps_tried}}\n\n"
            "Help me:\n"
            "1. Identify the most likely root cause (rank hypotheses).\n"
            "2. Suggest the simplest diagnostic step to confirm it.\n"
            "3. Provide a minimal fix and any edge cases to watch for."
        ),
    },
    {
        "name": "Translator",
        "category": "translation",
        "description": "Translate text into a target language, preserving tone and meaning.",
        "body": (
            "Translate the following text from {{source_language}} to "
            "{{target_language}}.\n\n"
            "Text:\n\"\"\"\n{{source_text}}\n\"\"\"\n\n"
            "Requirements:\n"
            "- Preserve the original meaning, tone, and nuance.\n"
            "- Adapt idioms naturally rather than translating word-for-word.\n"
            "- Register: {{register}} (e.g. formal, casual, technical).\n"
            "- Return only the translation, then a short note on any "
            "ambiguous choices you made."
        ),
    },
    {
        "name": "Meeting Notes Summarizer",
        "category": "meeting notes",
        "description": "Turn raw meeting transcripts into structured, actionable notes.",
        "body": (
            "Convert the meeting transcript below into structured notes.\n\n"
            "Transcript:\n\"\"\"\n{{transcript}}\n\"\"\"\n\n"
            "Produce:\n"
            "1. **Summary** (2-3 sentences)\n"
            "2. **Decisions made** (bullet list)\n"
            "3. **Action items** - owner and due date for each\n"
            "4. **Open questions / risks**\n"
            "5. **Next steps** for the follow-up meeting\n\n"
            "Formatting: markdown headings and bullet lists; keep it skimmable."
        ),
    },
]


def seed_if_empty() -> None:
    """Insert sample templates only when the templates table is empty."""
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM templates").fetchone()["n"]
        if count > 0:
            return
        now = _now_iso()
        for tpl in SEED_TEMPLATES:
            conn.execute(
                "INSERT INTO templates (id, name, category, description, body, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (_new_id(), tpl["name"], tpl["category"], tpl["description"],
                 tpl["body"], now, now),
            )


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def detect_placeholders(body: str) -> List[str]:
    """Extract the list of {{placeholder}} names, in order of first appearance."""
    seen: List[str] = []
    for match in PLACEHOLDER_RE.finditer(body):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def render_prompt(body: str, variables: Dict[str, Any]) -> str:
    """Substitute {{name}} with the provided value.

    Missing variables are replaced with an empty string (no crash); the set of
    missing names is reported separately by the caller via detect_placeholders.
    """

    def repl(match: re.Match) -> str:
        name = match.group(1)
        value = variables.get(name)
        if value is None:
            return ""
        return str(value)

    return PLACEHOLDER_RE.sub(repl, body)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    body: str = Field(..., min_length=1)


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=2000)
    body: Optional[str] = Field(default=None, min_length=1)


class RenderRequest(BaseModel):
    variables: Dict[str, Any] = Field(default_factory=dict)
    strict: bool = Field(
        default=False,
        description="If True, raise a 422 error when a placeholder is missing.",
    )


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Prompt Library",
    description="Prompt template manager: store templates with {{variables}}, "
                "render them, and keep a generation history.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Template CRUD endpoints
# ---------------------------------------------------------------------------

def _template_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "description": row["description"],
        "body": row["body"],
        "placeholders": detect_placeholders(row["body"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@app.get("/api/templates")
def list_templates(
    category: Optional[str] = Query(default=None, description="Filter by category"),
    search: Optional[str] = Query(default=None, description="Case-insensitive substring match on name/description"),
) -> Dict[str, Any]:
    """List templates. Optional ?category= and ?search= filters."""
    sql = "SELECT * FROM templates"
    params: List[Any] = []
    where: List[str] = []
    if category:
        where.append("category = ?")
        params.append(category)
    if search:
        where.append("(name LIKE ? OR description LIKE ? OR body LIKE ?)")
        like = f"%{search}%"
        params += [like, like, like]
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC, name ASC"

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"templates": [_template_row(r) for r in rows]}


@app.post("/api/templates", status_code=201)
def create_template(payload: TemplateCreate) -> Dict[str, Any]:
    now = _now_iso()
    row_id = _new_id()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO templates (id, name, category, description, body, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row_id, payload.name.strip(), payload.category.strip(),
             payload.description.strip(), payload.body, now, now),
        )
        row = conn.execute("SELECT * FROM templates WHERE id = ?", (row_id,)).fetchone()
    return _template_row(row)


@app.get("/api/templates/{template_id}")
def get_template(template_id: str) -> Dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return _template_row(row)


@app.put("/api/templates/{template_id}")
def update_template(template_id: str, payload: TemplateUpdate) -> Dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Template not found")

        new_name = (payload.name if payload.name is not None else row["name"]).strip()
        new_category = (payload.category if payload.category is not None else row["category"]).strip()
        new_description = (payload.description if payload.description is not None else row["description"]).strip()
        new_body = payload.body if payload.body is not None else row["body"]

        conn.execute(
            "UPDATE templates SET name = ?, category = ?, description = ?, "
            "body = ?, updated_at = ? WHERE id = ?",
            (new_name, new_category, new_description, new_body, _now_iso(), template_id),
        )
        row = conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
    return _template_row(row)


@app.delete("/api/templates/{template_id}", status_code=204)
def delete_template(template_id: str) -> None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Template not found")
        # ON DELETE SET NULL keeps history entries intact.
        conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))


# ---------------------------------------------------------------------------
# Render + history endpoints
# ---------------------------------------------------------------------------

@app.post("/api/templates/{template_id}/render")
def render_template(template_id: str, payload: RenderRequest) -> Dict[str, Any]:
    """Render a template with user-supplied variables.

    Substitutes every {{placeholder}} with the matching value from
    ``variables``. Missing values are left blank (rendered as empty string) and
    reported in ``missing_variables``. If ``strict`` is true, a missing value
    raises HTTP 422 instead. Every successful render is recorded in history.
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Template not found")

        variables = {str(k): v for k, v in payload.variables.items()}
        missing = [p for p in detect_placeholders(row["body"]) if p not in variables]

        if payload.strict and missing:
            raise HTTPException(
                status_code=422,
                detail=f"Missing required variable(s): {', '.join(missing)}",
            )

        rendered = render_prompt(row["body"], variables)

        history_id = _new_id()
        conn.execute(
            "INSERT INTO history (id, template_id, template_name, variables_json, "
            "rendered_prompt, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (history_id, template_id, row["name"],
             json.dumps(variables, ensure_ascii=False), rendered, _now_iso()),
        )

    return {
        "template_id": template_id,
        "template_name": row["name"],
        "rendered_prompt": rendered,
        "missing_variables": missing,
        "history_id": history_id,
    }


@app.get("/api/history")
def list_history(limit: int = Query(default=50, ge=1, le=500)) -> Dict[str, Any]:
    """List recent generation history, newest first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM history ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    history = []
    for r in rows:
        try:
            variables = json.loads(r["variables_json"])
        except json.JSONDecodeError:
            variables = {}
        history.append({
            "id": r["id"],
            "template_id": r["template_id"],
            "template_name": r["template_name"],
            "variables": variables,
            "rendered_prompt": r["rendered_prompt"],
            "created_at": r["created_at"],
        })
    return {"history": history}


@app.delete("/api/history", status_code=204)
def clear_history() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM history")


# ---------------------------------------------------------------------------
# Static UI + entry point
# ---------------------------------------------------------------------------

# Mount AFTER API routes so /api/* takes precedence.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8090)
