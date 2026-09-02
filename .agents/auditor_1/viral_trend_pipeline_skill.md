# Skill: viral-trend-pipeline

Weekly automated workflow for scraping, storing, and analyzing viral trends across EDM and Sports Cards using SQLite (for context garbage collection) and BigQuery ML.

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
