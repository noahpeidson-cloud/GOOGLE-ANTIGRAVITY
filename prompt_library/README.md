# Prompt Library

A standalone **prompt template manager** built with FastAPI + SQLite + a plain
HTML/JS single-page UI (no npm build step). Store reusable prompts containing
`{{variable}}` placeholders, fill in the variables through an auto-generated
form, and generate complete, ready-to-copy prompts for use cases like code
review, writing, summarization, SQL generation, and more.

```
d:\GOOGLE ANTIGRAVITY\prompt_library\
├── backend.py          # FastAPI app: API + SQLite + static file serving
├── static\
│   └── index.html      # Single-page dark-themed UI (vanilla JS, no framework)
├── prompt_templates.db # SQLite database (auto-created & seeded on first run)
├── verify_e2e.py       # End-to-end API verification script
└── README.md
```

## Features

- **Template library** — create, edit, delete, and list templates with
  `name`, `category` (use case), `description`, and a prompt `body`.
- **Auto-detected placeholders** — the backend detects every `{{variable}}`
  in a template body and returns it with the template.
- **Fill-in form** — the UI generates a form from the detected placeholders,
  validates that each one is filled in, and shows the missing ones.
- **Server-side rendering** — placeholders are substituted on the server;
  repeated placeholders reuse the same value.
- **Graceful missing-variable handling** — by default missing values are left
  blank and reported in `missing_variables` (no crash); with `strict: true`
  the API returns HTTP 422 with a clear message.
- **Copy to clipboard** — one click to copy the rendered prompt.
- **Generation history** — every render is recorded; history survives template
  deletion (`ON DELETE SET NULL`).
- **Search + category filter** on the library grid.
- **8 seeded sample templates** covering: code review, writing, summarization,
  SQL generation, email drafting, debugging, translation, and meeting notes.

## Requirements

- Python 3.9+ (tested on 3.13)
- `fastapi`
- `uvicorn`

Install:

```bat
pip install fastapi uvicorn
```

## How to run

From the project directory:

```bat
cd /d "d:\GOOGLE ANTIGRAVITY\prompt_library"
python backend.py
```

or equivalently:

```bat
uvicorn backend:app --host 0.0.0.0 --port 8090
```

Then open <http://localhost:8090> in your browser.

- The SQLite database `prompt_templates.db` is created automatically on first
  startup and seeded with the 8 sample templates (seeding only happens when the
  `templates` table is empty).
- To reset everything, stop the server and delete `prompt_templates.db`, then
  start again.
- The default port is **8090** (set in the `if __name__ == "__main__"` block).

## API reference

Base URL: `http://localhost:8090`

### Templates

| Method | Endpoint                  | Description                                        |
|--------|---------------------------|----------------------------------------------------|
| GET    | `/api/templates`          | List templates. Query params: `?category=`, `?search=` (optional) |
| POST   | `/api/templates`          | Create a template. Body: `{name, category, description?, body}` (201) |
| GET    | `/api/templates/{id}`     | Get one template (404 if missing)                  |
| PUT    | `/api/templates/{id}`     | Update fields: `{name?, category?, description?, body?}` (partial update allowed) |
| DELETE | `/api/templates/{id}`     | Delete a template (204). History entries are kept with `template_id` set to `null` |

A template object looks like:

```json
{
  "id": "475e5719218d",
  "name": "Code Review Request",
  "category": "code review",
  "description": "Ask an AI to review a code snippet...",
  "body": "Please perform a thorough code review...\n\n```\n{{code_snippet}}\n```...",
  "placeholders": ["code_snippet", "context"],
  "created_at": "2026-09-01T20:30:00+00:00",
  "updated_at": "2026-09-01T20:30:00+00:00"
}
```

### Render

| Method | Endpoint                     | Description |
|--------|------------------------------|-------------|
| POST   | `/api/templates/{id}/render` | Substitute variables into the template and record history |

Request body:

```json
{
  "variables": { "code_snippet": "def foo(): pass", "context": "Legacy module" },
  "strict": false
}
```

Response:

```json
{
  "template_id": "475e5719218d",
  "template_name": "Code Review Request",
  "rendered_prompt": "Please perform a thorough code review...",
  "missing_variables": [],
  "history_id": "a1b2c3d4e5f6"
}
```

- **Non-strict (default):** placeholders with no matching value are replaced
  with an empty string and listed in `missing_variables`. The server never
  crashes on missing input.
- **Strict:** if any placeholder is missing a value, the API returns
  `422 {"detail": "Missing required variable(s): name1, name2"}` and nothing is
  recorded in history.

### History

| Method | Endpoint        | Description                                        |
|--------|-----------------|----------------------------------------------------|
| GET    | `/api/history`  | List recent generations, newest first. Query param: `?limit=` (default 50, max 500) |
| DELETE | `/api/history`  | Clear all history (204)                            |

History entry:

```json
{
  "id": "a1b2c3d4e5f6",
  "template_id": "475e5719218d",
  "template_name": "Code Review Request",
  "variables": { "code_snippet": "def foo(): pass" },
  "rendered_prompt": "...",
  "created_at": "2026-09-01T21:00:00+00:00"
}
```

> Note: CORS is enabled with `allow_origins=["*"]` so the API can also be
> called from other frontends during development.

## How to add templates

**Via the UI:** click **+ New Template**, fill in name/category/description,
write the prompt body with `{{variable}}` placeholders (the UI shows live chips
of detected placeholders), and save.

**Via the API:**

```bat
curl -X POST http://localhost:8090/api/templates ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"My Prompt\",\"category\":\"general\",\"description\":\"\",\"body\":\"Summarize {{text}} in {{max_words}} words.\"}"
```

**Via the database:** edit the `SEED_TEMPLATES` list in `backend.py`, delete
`prompt_templates.db`, and restart the server. (Seeding only runs when the
templates table is empty.)

Placeholder syntax: `{{name}}` where `name` matches `[A-Za-z0-9_]+`.
Whitespace inside the braces is tolerated (`{{ name }}`).

## Verification

With the server running, execute the end-to-end suite:

```bat
python verify_e2e.py
```

It asserts 37 checks: UI serving, seeded content, category/search filters,
full CRUD, placeholder substitution (including repeated placeholders and
varying output across inputs), graceful missing-variable handling (both
non-strict and strict), history recording/clearing, template deletion
semantics, and API validation errors.
