# Viral Trend Pipeline Integration Test Suite

Comprehensive Python integration test suite and data processing engine for the **Viral Trend Pipeline**.

## Features
- **Deterministic Extraction Mocking (R1)**:
  - `ChromeDevToolsExtractor`: Parses Accessibility Tree snapshots from TikTok Creative Center and YouTube Trending.
  - `AndroidCLIExtractor`: Parses Android UI hierarchy layout dumps from Instagram Reels.
  - Case-preserving hashtag normalization, emoji stripping, and metric parsing.
- **Zero-Network Socket Guardrail**: Autouse pytest fixture enforcing 100% offline deterministic test runs by barring real socket connections.
- **Unified Data Contract**: Canonical `TrendRecord` dataclass modeling trends across platforms (`tiktok`, `youtube`, `instagram`) and tracks (`sports_cards`, `edm`, `general`).

## Running Tests
```bash
python -m pytest tests/ -v
```
