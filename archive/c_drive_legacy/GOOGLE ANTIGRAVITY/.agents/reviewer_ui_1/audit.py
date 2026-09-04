import re
import sys

def run_audit():
    with open('index.html', 'r', encoding='utf-8') as f:
        html_root = f.read()

    with open('static/index.html', 'r', encoding='utf-8') as f:
        html_static = f.read()

    print(f"Root index.html lines: {len(html_root.splitlines())}, bytes: {len(html_root)}")
    print(f"Static index.html lines: {len(html_static.splitlines())}, bytes: {len(html_static)}")
    print(f"Files identical: {html_root == html_static}")

    collapsed = re.sub(r'\s+', ' ', html_root)
    
    grid_pattern = bool(re.search(r'grid-template-areas:\s*["\']topbar\s+topbar\s+topbar["\']\s*["\']sidebar\s+workspace\s+inspector["\']\s*["\']footer\s+footer\s+footer["\']', collapsed))

    checks = [
        ("CSS Grid Area (topbar/sidebar/workspace/inspector/footer)", grid_pattern),
        ("Slate Dark Base #0B0F19", "#0B0F19" in html_root.upper()),
        ("Slate Dark Elevated #1A2234", "#1A2234" in html_root.upper()),
        ("Slate Dark Borders #2D3748", "#2D3748" in html_root.upper()),
        ("Slate Dark Text #E2E8F0", "#E2E8F0" in html_root.upper()),
        ("Electric Blue Accent #3B82F6", "#3B82F6" in html_root.upper()),
        ("720p Proxy Video element #proxy-video", 'id="proxy-video"' in html_root or "id='proxy-video'" in html_root),
        ("9:16 Aspect Ratio", '9 / 16' in html_root or '9:16' in html_root),
        ("YouTube Shorts Safe Zone (900x1270)", '900' in html_root and '1270' in html_root and 'shorts' in html_root.lower()),
        ("TikTok Safe Zone (920x1310)", '920' in html_root and '1310' in html_root and 'tiktok' in html_root.lower()),
        ("59.00s Content ID Alert", '59' in html_root and ('content-id' in html_root.lower() or 'guardrail' in html_root.lower())),
        ("Clamp to 59.00s button", 'clamp-59s-btn' in html_root),
        ("TikTok Ghost Link Badge", 'ghost-link-badge' in html_root),
        ("FastAPI /trigger-pipeline wiring", '/trigger-pipeline' in html_root),
        ("FastAPI /approve-render wiring", '/approve-render' in html_root),
        ("FastAPI /proxies wiring", '/proxies' in html_root),
        ("FastAPI /status wiring", '/status' in html_root),
        ("FastAPI /cancel wiring", '/cancel' in html_root),
        ("FastAPI /health wiring", '/health' in html_root),
    ]

    all_passed = True
    for label, result in checks:
        status = "PASS" if result else "FAIL"
        if not result:
            all_passed = False
        print(f"[{status}] {label}")

    return all_passed

if __name__ == "__main__":
    success = run_audit()
    sys.exit(0 if success else 1)
