---
name: vectorized-rule-registry
description: "Implements a localized, zero-dependency SQLite FTS5 database to store and dynamically inject workspace rules using BM25 keyword matching, preventing context bloat."
---

# Native Rule Registry (FTS5)

## Core Philosophy
Loading a monolithic `GEMINI.md` file into the active context window degrades reasoning. External vector packages (`sqlite-vec`) violate Rule 3. Rules must be injected dynamically at runtime via native SQLite FTS5 (Full-Text Search).

## Implementation Protocol

### 1. The FTS5 Sentinel Store
Utilize standard Python `sqlite3` and its native FTS5 virtual tables.

```python
import sqlite3

def initialize_sentinel_db():
    conn = sqlite3.connect("sentinel_rules.db")
    # Create FTS5 virtual table for native full-text search
    conn.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS rules_fts USING fts5(
            rule_name,
            rule_content
        )
    ''')
    conn.commit()
    return conn
```

### 2. Pre-Turn Dynamic Injection (BM25 RAG)
Hook into the Antigravity SDK's `on_pre_turn` to execute a native keyword search based on the user's current prompt.

1. **Extract Keywords:** Identify core nouns/verbs in the `USER_INPUT`.
2. **BM25 MATCH Query:** Search `rules_fts` using `SELECT * FROM rules_fts WHERE rules_fts MATCH ? ORDER BY rank`. 
3. **Inject:** The native BM25 scoring algorithm will instantly (<1ms) surface the exact blueprints (e.g., surfacing the 21-variable schema when "card ladder" is mentioned) without hallucinations. Inject the top 3 constraints into the agent's active system prompt for that specific turn.
