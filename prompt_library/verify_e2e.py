"""End-to-end verification script for the Prompt Library app.

Runs against a live server on http://localhost:8090 and exercises:
- GET  /api/templates            (seeded list)
- POST /api/templates            (create)
- GET  /api/templates/{id}       (read one)
- PUT  /api/templates/{id}       (update)
- POST /api/templates/{id}/render (substitution + missing-var behavior)
- GET  /api/history              (history recorded)
- DELETE /api/templates/{id}     (delete + 404 after)
- DELETE /api/history            (clear history)
- GET  /                         (UI HTML served)

Exit code 0 when every check passes, 1 otherwise.
"""

import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8090"
PASS = 0
FAIL = 0


def request(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:  # pragma: no cover - network failure
        return -1, str(e)


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {label} {extra}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} {extra}")


def main():
    print("== 1. Server + UI ==")
    status, html = request("GET", "/")
    check("UI serves at / with HTTP 200", status == 200, f"(status={status})")
    check("UI contains app shell", status == 200 and "Prompt Library" in html and "templateGrid" in html)

    print("== 2. List seeded templates ==")
    status, raw = request("GET", "/api/templates")
    data = json.loads(raw)
    check("GET /api/templates -> 200", status == 200, f"(status={status})")
    check("8 seeded templates present", len(data["templates"]) == 8,
          f"(found {len(data['templates'])})")
    categories = sorted({t["category"] for t in data["templates"]})
    print(f"       categories: {categories}")
    for expected in ["code review", "writing", "summarization", "sql", "email",
                     "debugging", "translation", "meeting notes"]:
        check(f"seed category '{expected}'", expected in categories)

    tpl = data["templates"][0]
    print(f"       sample template: {tpl['name']} placeholders={tpl['placeholders']}")

    print("== 3. Filtering ==")
    status, raw = request("GET", "/api/templates?category=writing")
    data = json.loads(raw)
    check("category filter works", status == 200 and len(data["templates"]) == 1
          and data["templates"][0]["category"] == "writing", f"(got {len(data['templates'])})")
    status, raw = request("GET", "/api/templates?search=sql")
    data = json.loads(raw)
    check("search filter works", status == 200 and len(data["templates"]) == 1
          and "SQL" in data["templates"][0]["name"], f"(got {len(data['templates'])})")

    print("== 4. Create / Read / Update / Delete (CRUD) ==")
    create_body = {
        "name": "E2E Test Template",
        "category": "testing",
        "description": "Created by verification script",
        "body": "Analyze {{code}} using language {{lang}} and level {{level}}. "
                "Repeated placeholder: {{code}}.",
    }
    status, raw = request("POST", "/api/templates", create_body)
    created = json.loads(raw)
    check("POST create -> 201", status == 201, f"(status={status})")
    new_id = created["id"]
    check("placeholders auto-detected on create", created["placeholders"] == ["code", "lang", "level"],
          f"(got {created['placeholders']})")

    status, raw = request("GET", f"/api/templates/{new_id}")
    got = json.loads(raw)
    check("GET single -> 200 + fields", status == 200 and got["name"] == "E2E Test Template"
          and got["category"] == "testing" and "{{code}}" in got["body"])

    update_body = {"name": "E2E Test Template (renamed)", "description": "updated via PUT"}
    status, raw = request("PUT", f"/api/templates/{new_id}", update_body)
    upd = json.loads(raw)
    check("PUT update -> 200 + applied", status == 200 and upd["name"] == "E2E Test Template (renamed)"
          and upd["description"] == "updated via PUT")

    print("== 5. Render + substitution ==")
    vars1 = {"code": "x = 1", "lang": "Python", "level": "beginner"}
    status, raw = request("POST", f"/api/templates/{new_id}/render", {"variables": vars1})
    r1 = json.loads(raw)
    check("render -> 200", status == 200, f"(status={status})")
    p1 = r1["rendered_prompt"]
    check("all placeholders substituted", "x = 1" in p1 and "Python" in p1 and "beginner" in p1)
    check("no missing_variables", r1["missing_variables"] == [], f"(got {r1['missing_variables']})")
    check("repeated placeholder reused same value", p1.count("x = 1") == 2)
    check("template body structure preserved",
          "Analyze " in p1 and "Repeated placeholder: " in p1)

    # render again with DIFFERENT values -> output must vary
    vars2 = {"code": "y = 99", "lang": "Rust", "level": "advanced"}
    status, raw = request("POST", f"/api/templates/{new_id}/render", {"variables": vars2})
    r2 = json.loads(raw)
    p2 = r2["rendered_prompt"]
    check("render varies across inputs", p1 != p2 and "y = 99" in p2 and "Rust" in p2)
    print(f"       p1: {p1[:80]!r}")
    print(f"       p2: {p2[:80]!r}")

    print("== 6. Missing-var handling ==")
    # non-strict: missing left blank, reported, no crash
    status, raw = request("POST", f"/api/templates/{new_id}/render",
                          {"variables": {"code": "only code"}})
    r3 = json.loads(raw)
    check("missing vars -> 200 (non-strict)", status == 200, f"(status={status})")
    check("missing vars reported", sorted(r3["missing_variables"]) == ["lang", "level"],
          f"(got {r3['missing_variables']})")
    check("missing vars left blank (no crash)", "only code" in r3["rendered_prompt"]
          and r3["rendered_prompt"].count("{{") == 0)
    # strict: 422 with clear message
    status, raw = request("POST", f"/api/templates/{new_id}/render",
                          {"variables": {"code": "x"}, "strict": True})
    check("strict missing -> 422 with message",
          status == 422 and "lang" in raw and "level" in raw, f"(status={status}, raw={raw[:80]})")

    print("== 7. History ==")
    status, raw = request("GET", "/api/history")
    hist = json.loads(raw)
    check("history has entries", status == 200 and len(hist["history"]) >= 3,
          f"(got {len(hist['history'])})")
    check("history records rendered prompt + template",
          any(h["template_id"] == new_id and "Rust" in h["rendered_prompt"]
              and h["template_name"] == "E2E Test Template (renamed)"
              for h in hist["history"]))

    print("== 8. Delete ==")
    status, _ = request("DELETE", f"/api/templates/{new_id}")
    check("DELETE template -> 204", status == 204, f"(status={status})")
    status, raw = request("GET", f"/api/templates/{new_id}")
    check("GET deleted -> 404", status == 404 and "not found" in raw.lower(),
          f"(status={status})")
    status, raw = request("GET", "/api/history")
    hist = json.loads(raw)
    # ON DELETE SET NULL: entry persists, template_id becomes NULL
    check("history entry survives template delete (template_id nulled)",
          any(h["template_id"] is None
              and h["template_name"] == "E2E Test Template (renamed)"
              for h in hist["history"]))

    status, _ = request("DELETE", "/api/history")
    check("DELETE /api/history -> 204", status == 204, f"(status={status})")
    status, raw = request("GET", "/api/history")
    hist = json.loads(raw)
    check("history cleared", status == 200 and len(hist["history"]) == 0,
          f"(got {len(hist['history'])})")

    print("== 9. Validation errors ==")
    status, raw = request("POST", "/api/templates", {"name": "", "category": "x", "body": "y"})
    check("empty name -> 422", status == 422, f"(status={status})")
    status, raw = request("GET", "/api/templates/doesnotexist")
    check("unknown template -> 404", status == 404, f"(status={status})")

    print(f"\n==== RESULT: {PASS} passed, {FAIL} failed ====")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
