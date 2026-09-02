---
name: viral-trend-pipeline
description: Weekly automated workflow for scraping, storing, and analyzing viral trends across EDM and Sports Cards using SQLite (for context garbage collection) and BigQuery ML.
---

# Viral Trend Pipeline & Algorithm Strategy

## 1. Context Structure & Garbage Collection (Anti-Bloat)
To prevent context rot and ensure agents are only working with up-to-date trends, all research is stored in a localized SQLite database (`trends.db`) rather than an infinitely growing markdown file.
*   **The Mark-and-Sweep**: A scheduled weekly cron job (`/schedule`) runs the pipeline. It inserts new trends and executes a hard `DELETE FROM trends WHERE date_added < date('now', '-14 days')`. 
*   **The View**: It then generates a single, clean `current_trends.md` artifact that only contains the active rolling 14-day window.

## 2. Multi-Platform Scraping Lenses
*   **Web Dashboards (YouTube, TikTok)**: The `BrowserMaster` (using `chrome-devtools-mcp`) navigates to TikTok Creative Center and YouTube Trending, bypassing standard DOM scraping by reading the Accessibility Tree to extract trending audio titles and hashtags.
*   **Mobile-First Platforms (Instagram/Facebook Reels)**: The `android-cli` skill is utilized to launch a headless Android emulator, navigating the IG Reels feed and dumping the UI structure via `android layout` to extract organic, app-only trends.

## 3. Data Autocleaning & BigQuery AI Forecasting
If trend data exceeds local capacity, it is exported to BigQuery.
*   **Autocleaning**: We apply the `data-autocleaning` protocol: extracting JSON arrays of tags, using `SAFE_CAST`, normalizing strings (preserving case, stripping emojis where necessary), and deduplicating.
*   **AI/ML**: We utilize BigQuery's `AI.FORECAST` to predict the trajectory of a hashtag's momentum, and `AI.KEY_DRIVERS` to determine which editing styles (e.g., "stutter edit" vs "slow zoom") drive the highest engagement.

## 4. Platform-Specific Editing & Tagging Matrix

### TikTok
*   **Algorithm Lens**: Discovery-focused, high velocity. Watch-time and re-watches are the ultimate metrics.
*   **Editing**: 9:16 vertical. The "Hook" must happen visually and audibly in the first 1.5 seconds. Fast cuts. 
*   **Tags**: 3-5 highly targeted tags. 
    *   *Cards*: `#SportsCards`, `#PaniniPrizm`, `#CardLadder`
    *   *EDM*: `#HardTechno`, `#RaveTok`, `#EDMDrop`

### Instagram Reels (Primary for Cards)
*   **Algorithm Lens**: Aesthetic and shareability (DMs). The algorithm heavily favors content that is shared to stories or sent to friends.
*   **Editing**: High-quality lighting, seamless loops, and educational overlays (e.g., showing ROI data from Card Ladder).
*   **Tags**: 10-15 tags. Mix broad community tags with specific niches. 
    *   *Cards*: `#TheHobby`, `#WhoDoYouCollect`, `#SportsCardInvesting`

### YouTube Shorts
*   **Algorithm Lens**: Search-intent and session time.
*   **Editing**: High retention required (often >100% via perfect looping).
*   **Tags/Metadata**: Tags matter less here; the *Title* and on-screen text are parsed for SEO. 
    *   *Title Example*: "Is the 2026 Topps Chrome Wembanyama worth grading?"

### Facebook Reels
*   **Algorithm Lens**: Older demographic, nostalgia-driven, high engagement on opinionated content.
*   **Editing**: Slightly slower pacing. Clear text banners explaining the context. 
    *   *EDM*: Focus on 2010s festival nostalgia.
    *   *Cards*: Focus on vintage or junk-wax era comparisons.
