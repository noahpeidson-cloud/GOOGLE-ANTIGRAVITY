import hashlib
import json
import re

def detailed_verification():
    with open('index.html', 'rb') as f:
        root_bytes = f.read()
    with open('static/index.html', 'rb') as f:
        static_bytes = f.read()

    root_hash = hashlib.sha256(root_bytes).hexdigest()
    static_hash = hashlib.sha256(static_bytes).hexdigest()
    
    html = root_bytes.decode('utf-8')
    
    report = {
        "file_sync": {
            "root_size": len(root_bytes),
            "static_size": len(static_bytes),
            "root_sha256": root_hash,
            "static_sha256": static_hash,
            "identical": root_hash == static_hash
        },
        "color_palette": {
            "#0B0F19 (Base)": "#0B0F19" in html.upper(),
            "#1A2234 (Elevated)": "#1A2234" in html.upper(),
            "#2D3748 (Borders)": "#2D3748" in html.upper(),
            "#E2E8F0 (Text)": "#E2E8F0" in html.upper(),
            "#3B82F6 (Electric Blue)": "#3B82F6" in html.upper()
        },
        "css_grid_layout": {
            "grid-template-areas": bool(re.search(r'grid-template-areas:\s*["\']topbar\s+topbar\s+topbar["\']\s*["\']sidebar\s+workspace\s+inspector["\']\s*["\']footer\s+footer\s+footer["\']', re.sub(r'\s+', ' ', html))),
            "grid-template-rows": "grid-template-rows: var(--topbar-height) 1fr var(--footer-height)" in re.sub(r'\s+', ' ', html),
            "grid-template-columns": "grid-template-columns: var(--sidebar-left-width) 1fr var(--sidebar-right-width)" in re.sub(r'\s+', ' ', html)
        },
        "proxy_viewer_and_hud": {
            "#proxy-video": 'id="proxy-video"' in html,
            "aspect-ratio 9/16": "9 / 16" in html or "9:16" in html,
            "youtube_shorts_safe_box (900x1270)": 'width="900" height="1270"' in html,
            "tiktok_safe_box (920x1310)": 'width="920" height="1310"' in html,
            "hud_controls (None/Shorts/TikTok/Dual)": "data-hud=" in html,
            "svg_viewBox_1080x1920": 'viewBox="0 0 1080 1920"' in html
        },
        "timeline_and_waveform": {
            "#waveform-canvas": 'id="waveform-canvas"' in html,
            "#timeline-scrubber": 'id="timeline-scrubber"' in html,
            "#timeline-playhead": 'id="timeline-playhead"' in html,
            "#start-trim-handle": 'id="start-trim-handle"' in html,
            "#end-trim-handle": 'id="end-trim-handle"' in html,
            "#drop-highlight-region": 'id="drop-highlight-region"' in html,
            "WaveformRenderer class": 'class WaveformRenderer' in html,
            "devicePixelRatio scaling": 'window.devicePixelRatio' in html
        },
        "omnichannel_guardrails": {
            "#content-id-guardrail-banner": 'id="content-id-guardrail-banner"' in html,
            "#clamp-59s-btn": 'id="clamp-59s-btn"' in html,
            "59.00s duration check logic": '59.00' in html or '59' in html,
            "#ghost-link-badge": 'id="ghost-link-badge"' in html
        },
        "fastapi_wiring": {
            "/trigger-pipeline": '/trigger-pipeline' in html,
            "/approve-render": '/approve-render' in html,
            "/proxies": '/proxies' in html,
            "/proxies/{id}/video": '/proxies/' in html,
            "/status": '/status' in html,
            "/cancel": '/cancel' in html,
            "/health": '/health' in html
        }
    }
    
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    detailed_verification()
