"""Chrome DevTools Accessibility Tree snapshot fixtures and loaders."""

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent

TIKTOK_A11Y_SNAPSHOT_PATH = FIXTURES_DIR / "tiktok_creative_center_a11y_snapshot.txt"
YOUTUBE_A11Y_SNAPSHOT_PATH = FIXTURES_DIR / "youtube_trending_a11y_snapshot.txt"


def get_tiktok_a11y_snapshot() -> str:
    """Load raw TikTok Creative Center a11y tree snapshot text."""
    if not TIKTOK_A11Y_SNAPSHOT_PATH.exists():
        raise FileNotFoundError(f"Fixture file missing: {TIKTOK_A11Y_SNAPSHOT_PATH}")
    return TIKTOK_A11Y_SNAPSHOT_PATH.read_text(encoding="utf-8")


def get_youtube_a11y_snapshot() -> str:
    """Load raw YouTube Trending a11y tree snapshot text."""
    if not YOUTUBE_A11Y_SNAPSHOT_PATH.exists():
        raise FileNotFoundError(f"Fixture file missing: {YOUTUBE_A11Y_SNAPSHOT_PATH}")
    return YOUTUBE_A11Y_SNAPSHOT_PATH.read_text(encoding="utf-8")


# Raw in-memory constants
TIKTOK_A11Y_SNAPSHOT_RAW = get_tiktok_a11y_snapshot()
YOUTUBE_A11Y_SNAPSHOT_RAW = get_youtube_a11y_snapshot()

# Edge case fixtures
EMPTY_LOADING_A11Y_SNAPSHOT = """uid=1_0 RootWebArea "Loading..."
  uid=1_1 main "Please wait..."
"""

MALFORMED_A11Y_SNAPSHOT = """uid=1_0 RootWebArea "Broken Page"
  malformed_line_without_uid
  uid=1_1 heading "Valid Heading #SportsCards" level=2
  uid=1_2 row "Rank 1 #CardLadder"
    uid=1_3 cell "1"
    uid=1_4 cell "#CardLadder"
    uid=1_5 cell "500K"
    uid=1_6 cell "+150%"
  [corrupted_binary_data_line]
  uid=1_7 link "Broken link with unmatched quotes "foo" bar"
"""

EMOJI_A11Y_SNAPSHOT = """uid=1_0 RootWebArea "TikTok Trending"
  uid=1_1 main
    uid=1_2 table "Trending"
      uid=1_3 row "Rank 1 #Wembanyama🔥"
        uid=1_4 cell "1"
        uid=1_5 cell "#Wembanyama🔥"
        uid=1_6 cell "2.5M"
        uid=1_7 cell "+320%"
      uid=1_8 row "Rank 2 #CardLadder💎"
        uid=1_9 cell "2"
        uid=1_10 cell "#CardLadder💎"
        uid=1_11 cell "980K"
        uid=1_12 cell "+110%"
"""


def generate_large_a11y_tree(num_nodes: int = 10000) -> str:
    """Generate a synthetic massive accessibility tree for performance stress testing."""
    lines = ['uid=1_0 RootWebArea "Massive Tree Stress Benchmark"']
    lines.append('  uid=1_1 main "Stress Table"')
    lines.append('    uid=1_2 table "Massive Hashtags"')
    for i in range(1, num_nodes + 1):
        lines.append(f'      uid=node_{i} row "Rank {i} #BenchmarkTag{i}"')
        lines.append(f'        uid=cell_rank_{i} cell "{i}"')
        lines.append(f'        uid=cell_tag_{i} cell "#BenchmarkTag{i}"')
        lines.append(f'        uid=cell_cnt_{i} cell "{i}00K"')
        lines.append(f'        uid=cell_vel_{i} cell "+{i % 200}%"')
    return "\n".join(lines)
