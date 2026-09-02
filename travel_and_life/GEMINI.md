<system>
## Travel & Life Domain Logic
This manifest governs the rules for the `/travel_and_life` track.

### 1. Operational Scope
- Logistics planning, travel itinerary creation, sports route tracking, and location scouting for content creation (vlogs).
- Do NOT perform media transcoding or execute FFmpeg in this directory.

### 2. Proactive Workflows
- **Travel & Location Scout**: When Noah mentions travel or sports routes, leverage the `google-maps-platform` skill.
  - Calculate transit times, discover points of interest, and map out shooting locations.
  - Format the complete itineraries into clear markdown tables or CSV outputs, or proactively suggest using `gdrive` to create a Google Sheet for the itinerary.
- **Web Research**: Use the native web search and url reading tools (`search_web`, `read_url_content`) to scrape location data, event information, and sports statistics. Avoid complex browser automation unless explicitly requested or necessary.

### 3. Rule Isolation
- **STRICTLY PROHIBITED:** Card Ladder ETL, 21-variable sports card schemas, and video transcoding. 
- Any request to edit video or grade sports cards within `/travel_and_life` MUST be rejected with a domain mismatch error.
</system>
