# Exhaustive Technical Specification Inventory & Extraction Report
**Project:** Master Operational Blueprint for EDM Short-Form Content Strategy Consolidation  
**Author:** Spec Miner 1 (`.agents/spec_miner_survey_1`)  
**Timestamp:** 2026-08-22T01:55:00Z  
**Source Corpus:**
- `G:\My Drive\GOOGLE ANTIGRAVITY\Dropbox\01_master_brand_and_orchestration.md`
- `G:\My Drive\GOOGLE ANTIGRAVITY\Dropbox\02_youtube_shorts_operating_guide.md`
- `G:\My Drive\GOOGLE ANTIGRAVITY\Dropbox\03_tiktok_operating_guide.md`
- `G:\My Drive\GOOGLE ANTIGRAVITY\Dropbox\04_production_and_editing_pipelines.md`
- `G:\My Drive\GOOGLE ANTIGRAVITY\Dropbox\05_asset_management_and_metadata.md`
- `G:\My Drive\GOOGLE ANTIGRAVITY\Dropbox\anti-gravity-blueprint.md`
- `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation\GEMINI.md`
- `G:\My Drive\GOOGLE ANTIGRAVITY\GEMINI.md`
- `G:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md`

---

## 1. Features Discovered Table

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior / Constraints | Discovered Via |
|---|----------|---------|-------------|--------|---------|------------------------------|----------------|
| 1 | Video Canvas & Safe Zones | YouTube Shorts Canvas & Safe Zone | Defines vertical canvas and pixel exclusion bounds for YouTube Shorts UI elements (search, header, channel title, interaction buttons). | 1080x1920 raw video | 900x1160 px centered safe canvas box (Top Excl: Y 0–180px, Bottom Excl: Y 1450–1920px, Right Excl: X 960–1080px) | Text/faces outside safe box obscured by Shorts UI overlays. | `02_youtube_shorts_operating_guide.md`, `anti-gravity-blueprint.md` |
| 2 | Video Canvas & Safe Zones | TikTok Canvas & Safe Area Box | Defines vertical canvas and exclusion coordinates for TikTok UI (Following/FYP tabs, search, username, caption, sound marquee, right action rail). | 1080x1920 raw video | 920x1250 px centered safe area box (Top Excl: Y 0–160px, Bottom Excl: Y 1470–1920px, Right Rail Excl: X 960–1080px, Left Margin: 40px) | Critical visual elements obscured by TikTok interaction stack. | `03_tiktok_operating_guide.md`, `anti-gravity-blueprint.md` |
| 3 | Video Canvas & Safe Zones | YouTube Channel Banner Safe Zone | Multi-device banner dimensions and safe display box for TV, desktop, and mobile. | 2048x1152 px 16:9 image (max 6MB) | Central 1235x338 px cross-device safe display area | Banners >6MB rejected; text outside safe area clipped on mobile. | `02_youtube_shorts_operating_guide.md` |
| 4 | Video Canvas & Safe Zones | YouTube Channel Profile Picture | Round avatar specifications for desktop and mobile Shorts feeds. | Min 98x98 px PNG/GIF (non-animated, max 4MB) | Circular crop rendered at 32x32 px on mobile feeds | Animated GIFs unsupported; files >4MB rejected. | `02_youtube_shorts_operating_guide.md` |
| 5 | Video Canvas & Safe Zones | YouTube Video Watermark | Fixed desktop channel branding overlay. | 150x150 px square PNG/GIF/JPEG (max 1MB) | Fixed lower-right corner overlay on desktop horizontal playback | Watermarks >1MB or non-square aspect ratios distorted. | `02_youtube_shorts_operating_guide.md` |
| 6 | Video Encoding | Master Export Preset (H.264) | Baseline H.264 MP4 export profile for mobile short-form distribution. | Master project sequence | 1080x1920, H.264, 60fps CFR, 8–12 Mbps VBR (10–12 Mbps master preset), AAC 320kbps | Variable frame rate (VFR) causes audio/video desync. | `03_tiktok_operating_guide.md`, `04_production_and_editing_pipelines.md` |
| 7 | Video Encoding | High-Fidelity Transcoding (H.265 / AV1) | Advanced hardware-accelerated transcoding for festival low-light HDR captures. | Raw 1080p/4K mobile captures | 1080x1920 MP4, H.265 (`libx265`/`hevc_nvenc`) or AV1 (`libsvtav1`/`av1_nvenc`), 15–20 Mbps (25 Mbps ceiling), AAC 320kbps 48kHz | Non-hardware builds drop frames during real-time render. | `content_creation/GEMINI.md` |
| 8 | Video Enhancement | AI Denoising & Video Upscaling | Spatio-temporal noise reduction and 4K upscaling for low-light high-ISO festival footage. | Noisy mobile captures | Denoised footage via Topaz Video AI (Nyx/Proteus) or FFmpeg (`hqdn3d`/`nlmeans`), upscaled 2x to 4K | Over-denoising causes plastic skin textures; 4K increases render time. | `04_production_and_editing_pipelines.md`, `content_creation/GEMINI.md` |
| 9 | Video Framing | Smart Reframe & Subject Tracking | Automated dynamic center-crop locking onto DJ booth, decks, or laser apex. | 16:9 or uncropped mobile footage | 9:16 vertical crop locked on subject | Rapid camera panning causes tracking jitter if smoothing is low. | `04_production_and_editing_pipelines.md` |
| 10 | Audio Engineering | Two-Pass Dynamic Loudness Normalization | Broadcast-standard loudness normalization for concert audio. | Raw festival audio | Target Integrated Loudness: -14.0 LUFS (±1.0 LUFS), Loudness Range: 7.0 LRA, True Peak limit: -1.0 to -1.5 dBTP | Single-pass loudnorm causes dynamic pumping and distortion. | `04_production_and_editing_pipelines.md`, `content_creation/GEMINI.md` |
| 11 | Audio Engineering | High-Pass Sub-Bass Filtering | Low-end acoustic rumble elimination below sub-bass thresholds. | Raw microphone feed | High-pass filtered audio at 40 Hz (production pipeline) or 80 Hz (live festival standard) | Inadequate filtering causes mobile phone speaker intermodulation distortion. | `04_production_and_editing_pipelines.md`, `content_creation/GEMINI.md` |
| 12 | Audio Engineering | True Peak Limiting & De-Clipping | Prevention of inter-sample digital clipping and restoration of overloaded phone mics. | Distorted audio waveforms | Audio mastered via FabFilter Pro-L2 (Dynamic Mode, -1.0 dBTP limit) and iZotope RX De-Clip | Hard brickwall limiting crushes punchy transient response. | `04_production_and_editing_pipelines.md` |
| 13 | Audio Engineering | Phase-Aligned Hybrid Audio Mixing | Acoustic spatial blending of clean studio master with live atmosphere. | Studio master WAV + raw crowd microphone | 70% studio track mixed with 30% live crowd reverb/atmosphere | Phase cancellation if studio track and live feed are not micro-aligned. | `01_master_brand_and_orchestration.md` |
| 14 | Audio Engineering | TikTok Ghost-Linking Audio Sync | Algorithmic indexing on official sound pages while retaining live high-fidelity bass. | Clean live master MP4 + official TikTok sound | Added sound volume set to 1%–3%, Original sound volume set to 100% | Setting added sound to 0% may fail sound-page indexing on some app versions. | `01_master_brand_and_orchestration.md`, `03_tiktok_operating_guide.md`, `anti-gravity-blueprint.md` |
| 15 | Audio & Pacing | Automated Drop Detection | Algorithmic identification of musical build-ups and climax drops. | Audio waveform | Detected drop timestamp where RMS energy threshold > 0.8 | False positives on speech or constant-loudness white noise. | `04_production_and_editing_pipelines.md`, `anti-gravity-blueprint.md` |
| 16 | Audio & Pacing | Audio Stem Separation | Isolation of music playback from crowd noise and vocal scream bleed. | Mixed concert audio | Isolated 'Other' stem (synthesizers, bass, drums) via Demucs | Artifacting/swirling if crowd screams overlap identical frequency bands. | `04_production_and_editing_pipelines.md` |
| 17 | Audio & Pacing | Seamless Infinite Loop Crossfade | Continuous looping audio edit point for short-form retention. | 4-bar or 8-bar musical sequence | 30ms micro-fade audio crossfade across measure boundary | Non-bar-aligned cuts produce rhythmic stutters. | `04_production_and_editing_pipelines.md` |
| 18 | Content Pacing | Bass Music / Dubstep / Trap Pacing Formula | High-intensity editing formula for 140–150 BPM genres. | Raw footage & audio | Cut begins 1.5s before drop (final riser build), cuts on drop impact with kinetic zoom & rail-riding crowd reaction | Cutting on off-beats breaks kinetic momentum. | `04_production_and_editing_pipelines.md` |
| 19 | Content Pacing | House / Tech House / Techno Pacing Formula | Hypnotic looping formula for 124–130 BPM genres. | Raw footage & audio | Rolling 4/4 groove cut precisely on 4-bar or 8-bar measure; visual focus on laser sweeps and DJ deck hands | Non-modular bar lengths break seamless video replay loop. | `04_production_and_editing_pipelines.md` |
| 20 | Content Pacing | Trance / Melodic / Future Bass Pacing Formula | Emotional climax formula for 138–145 BPM genres. | Raw footage & audio | Vocal climax into bright laser canopy reveal; visual focus on massive wide stage sweeps | Tight close-ups lose the emotional scale of festival crowd singing. | `04_production_and_editing_pipelines.md` |
| 21 | Content Pacing | Drum & Bass / Hardstyle Pacing Formula | Hyper-speed visual sync for 150–175+ BPM genres. | Raw footage & audio | Rapid cuts synchronized to double-time kick drums and high-speed strobe lights | Slow cuts feel lethargic against 175 BPM percussion. | `04_production_and_editing_pipelines.md` |
| 22 | Content Pacing | 15-Minute Fast-Track Structure Formula | Standard high-retention structural blueprint for daily posting. | Raw footage | Exactly 4 seconds build-up + 12–16 seconds drop payoff (total 16–20s) | Build-ups >6 seconds cause viewer swipe-away in feed. | `04_production_and_editing_pipelines.md` |
| 23 | Copyright Management | 60-Second Content ID Threshold Rule | Platform copyright enforcement rule for vertical clips on YouTube Shorts. | Raw music clips | Video duration ≤59 seconds (optimal: 15–45s) yielding standard Content ID claims (ad revenue split, no strikes) | Vertical videos 61–180s with Content ID match are automatically globally blocked. | `02_youtube_shorts_operating_guide.md` |
| 24 | Copyright Management | YouTube Unlisted Pre-Flight Processing SOP | Quarantine workflow for verifying Content ID restrictions before public release. | Master MP4 export | Video uploaded as Unlisted, 30–60 min hold for HD/VP09 and Content ID processing, audit Restrictions column | Publishing immediately as Public risks instant algorithmic demotion if blocked. | `02_youtube_shorts_operating_guide.md`, `anti-gravity-blueprint.md` |
| 25 | Platform Config | YouTube Channel Settings & Indexing Matrix | SEO indexing, category routing, audience settings, and copyright protection. | Studio Settings UI | Keywords: EDM Shorts, Festival Clips, etc.; Audience: "Not made for kids"; Category: Music; License: Standard YouTube License | Setting audience to "Made for Kids" disables comments and algorithmic recommendation. | `02_youtube_shorts_operating_guide.md` |
| 26 | Platform Config | YouTube Community Spam & Link Blocklist | Automated comment moderation against ticket scammers, phishing bots, and leak spam. | YouTube Studio Automated Filters | Blocked words regex/list (`t.me/`, `whatsapp`, `crypto`, `ticket sale`, etc.) + "Block links" checkbox | Unblocked scam links mislead community and degrade channel reputation. | `02_youtube_shorts_operating_guide.md`, `05_asset_management_and_metadata.md` |
| 27 | Platform Config | TikTok Personal/Creator Account Policy | Commercial music library access configuration. | TikTok Account Settings | Account Type: Personal or Creator (NOT Business) | Business accounts are legally restricted from accessing trending commercial music tracks. | `03_tiktok_operating_guide.md` |
| 28 | Platform Config | TikTok High-Quality Upload Toggle | Platform compression bypass configuration. | Post Settings > More Options | Toggle switch: "Allow High-Quality Uploads" = ON (per post) | Default compression degrades high-ISO low-light concert video and bass transients. | `03_tiktok_operating_guide.md` |
| 29 | Platform SEO | TikTok Caption & 5–7 Hashtag Formula | Algorithmic indexing template for EDM short-form distribution. | Video metadata | Keyword-frontloaded caption + 2 broad (`#EDM`), 2 subgenre (`#TechHouse`), 2 entity (`#[Artist]`), 1 intent (`#EDMTok`) hashtags | >8 hashtags triggers spam penalties; missing artist/event drops search relevance. | `03_tiktok_operating_guide.md` |
| 30 | Community Growth | First-Hour Engagement Velocity Playbook | Immediate post-launch engagement stimulation via pinned comments. | Public video post | Pinned comment: Track ID Crowdsource, Binary 1–10 Rating Hook, or Direct DJ Tag | No early comments lowers algorithmic velocity score in the first 60 minutes. | `03_tiktok_operating_guide.md`, `05_asset_management_and_metadata.md` |
| 31 | Asset Management | Unified 4-Folder Hybrid Drive Architecture | Color-coded, lifecycle-based file repository. | Cloud/local file storage | `01_RAW_INBOX` (Red), `02_IN_PROGRESS` (Orange), `03_READY_TO_POST` (Green), `04_ARCHIVE` (Gray) | Unsorted raw footage causes lost assets and editing bottlenecks. | `05_asset_management_and_metadata.md`, `anti-gravity-blueprint.md` |
| 32 | Asset Management | Standardized Naming Syntax & Nesting Rule | Directory indexing optimization and file tracking standard. | Video assets | `YYYYMMDD_[Event]_[Artist]_[TrackName-or-ID]_V[#]_[Resolution].mp4`; Max 50 items per subfolder | Folders with >50 items cause cloud sync latency and browsing fatigue. | `05_asset_management_and_metadata.md`, `anti-gravity-blueprint.md` |
| 33 | Publishing Strategy | Daily Publishing Frequency & Timing | Multi-timezone peak audience capture schedule. | Platform-ready MP4s | 2 posts per day: 10:00 AM EST (EU peak transit/evening) & 6:00 PM EST (US peak evening scrolling) | Posting during off-hours reduces initial velocity score. | `05_asset_management_and_metadata.md` |
| 34 | Brand Architecture | Dual Brand Strategy Matrix | Target audience separation between high-energy visual spectacle and emotional acoustic sets. | Creative content strategy | Laser Baptism (`@LaserBaptismLive` - laser synchronization, stadium EDM) vs Music Baptism (`@MusicBaptismLive` - acoustic immersion, multi-genre) | Mixing intimate deep-vocal club sets into Laser Baptism dilutes core visual identity. | `01_master_brand_and_orchestration.md`, `anti-gravity-blueprint.md` |
| 35 | Brand Architecture | Content Pillar Classification | Three-tier event coverage structure for automated indexing. | Venue/event raw assets | Pillar A: Big Artist Stadium/Arena; Pillar B: Up-and-Coming DJ Spotlights; Pillar C: Festival Mega-Clips | Uncategorized content leads to inconsistent editing pacing. | `01_master_brand_and_orchestration.md` |
| 36 | AI Orchestration | Spark Orchestration Engine | Autonomous background AI ecosystem coordinating ingestion, pre-production, and publishing. | Raw mobile uploads, search feeds, track databases | MCP Ingestion Router, EXIF/XMP parsing, GPT Workspace Sheets analytics, Google Flow storyboarding, Blogger API publishing | Manual asset transfer breaks autonomous 24/7 publishing cycle. | `01_master_brand_and_orchestration.md`, `anti-gravity-blueprint.md` |
| 37 | Future Roadmap | 8 Creative Short-Form Concepts | Sustained channel growth formats for recurring weekly releases. | Catalog footage & IDs | 1. ID Hunter, 2. Laser Canopy ASMR, 3. Multi-Angle Switch, 4. BPM Acceleration Drop, 5. Interactive Bounty, 6. Audio Remaster Hub, 7. 1001Tracklists Webhook, 8. Soundboard Hybrid Fader | Stagnant single-format content causes audience fatigue over 90 days. | `05_asset_management_and_metadata.md` |

---

## 2. Edge Cases & Boundary Conditions Table

| # | Feature | Input / Condition | Observed Behavior / Mandatory Handling |
|---|---------|-------------------|-----------------------------------------|
| 1 | Video Duration (YouTube Shorts) | Video length = 60.5 seconds (between 61 and 180 seconds) with Content ID match | **Global Block:** Video is automatically blocked worldwide by YouTube; channel reach is penalized. Clip must be strictly trimmed to ≤ 59 seconds. |
| 2 | Video Duration (TikTok) | Original sound video duration > 60 seconds with commercial EDM track | **Audio Muted:** TikTok automatically mutes the audio track across the entire video. Clip must be kept between 15–45 seconds. |
| 3 | Audio Sync (TikTok) | Added commercial track volume set to 0% | In some TikTok app versions, setting added sound to 0% disables sound page indexing. Maintain Added Sound Volume at **1% to 3%** and Original Sound at 100%. |
| 4 | Safe Zones (YouTube Shorts) | Text or DJ face placed at Y = 1600 px (within bottom 470px) | Obscured by channel name, subscription button, video title, and sound marquee. All text must remain inside the **900x1160 px** universal safe area (Y 180–1450 px). |
| 5 | Safe Zones (TikTok) | Action or track ID placed at X = 1000 px (right 120px) | Obscured by TikTok right-rail engagement stack (profile follow, like heart, comment icon, bookmark, share). Keep critical action within the **920x1250 px** safe area box (X 40–960 px). |
| 6 | Audio Clipping (Concert Bass) | Raw phone microphone overloaded with 115 dB festival sub-bass | Massive inter-sample distortion and digital clipping. High-pass filter at 40 Hz (or 80 Hz for extreme festival environments) + iZotope RX De-Clip + FabFilter Pro-L2 limiting to -1.0 / -1.5 dBTP. |
| 7 | Video Low-Light Sensor Noise | Mobile sensor ISO > 3200 in dark warehouse or nightclub | Heavy chroma and luma grain ("festival haze"). Apply Topaz Video AI (Nyx/Proteus) or FFmpeg spatio-temporal denoising (`hqdn3d`/`nlmeans`) prior to final transcode; do not over-sharpen. |
| 8 | Channel Account Type (TikTok) | Registered as TikTok Business Account | Commercial music catalog is restricted; platform blocks the use of trending EDM tracks and labels. Account MUST be set to **Personal / Creator**. |
| 9 | Upload Visibility (YouTube) | Direct upload to "Public" without processing hold | Video may launch in low-res 360p before HD/VP09 transcoding finishes, and triggers instant public restriction if Content ID blocks. MUST upload as **Unlisted** and wait 30–60 minutes. |
| 10 | Spam Comments & Scams | Scammers posting Telegram ticket links (`t.me/edcorlando`) | Blocked words filter automatically quarantines comments matching `t.me/`, `whatsapp`, `buy tickets`, `crypto`, `dm to promote`, and the "Block links" toggle intercepts URLs. |
| 11 | Loop Transition Timing | Cut made on non-bar boundary (e.g., 3.5 bars) | Rhythmic cadence stutters upon video loop restart, destroying hypnotic retention. MUST trim precisely on 4-bar or 8-bar measure boundaries with a 30ms micro-fade. |
| 12 | Subfolder Scale Limit | Subfolder in Google Drive exceeds 50 items | Cloud synchronization latency increases and IDE metadata scrapers encounter indexing timeouts. Enforce strict **50-item cap** per subfolder. |
| 13 | High-Contrast Stage Lighting | Extreme strobe and laser flashes causing luma blowouts | Bitrate starvation leading to macroblocking artifacts. Use 10–12 Mbps VBR (up to 20–25 Mbps VBR) and preserve sub-black / highlight dynamic range without hard crushing. |
| 14 | Hybrid Audio Phase Alignment | Studio master and live crowd mic out of sync by 15ms | Severe acoustic comb filtering and hollow vocal flanging. Waveforms must be phase-aligned to the millisecond before blending 70% studio / 30% crowd. |

---

## 3. Comprehensive Categorical Technical Breakdown

### Category 1: Video Engineering & Encoding Parameters

```
+---------------------------------------------------------------------------------------+
|                                1080 x 1920 MASTER CANVAS                              |
|                                                                                       |
|  [ Top Exclusion Zone: Y 0 - 180 px (YouTube) / Y 0 - 160 px (TikTok) ]               |
|  ...................................................................................  |
|  |                                                                                 |  |
|  |                                                                                 |  |
|  |                     UNIVERSAL SAFE CANVAS BOX                                   |  |
|  |                     - YouTube: 900 x 1160 px (X: 60-960, Y: 180-1450)           |  |
|  |                     - TikTok:  920 x 1250 px (X: 40-960, Y: 160-1470)           |  |
|  |                                                                                 |  |
|  |   [ Center all laser apex, DJ faces, build-up text, and Track ID overlays ]     |  |
|  |                                                                                 |  |
|  |                                                                                 |  |
|  ...................................................................................  |
|  [ Bottom Exclusion Zone: Y 1450 - 1920 px (YouTube) / Y 1470 - 1920 px (TikTok) ]    |
|  [ Right Rail Exclusion: X 960 - 1080 px (Action Icons on both platforms) ]           |
+---------------------------------------------------------------------------------------+
```

1. **Master Video Resolution & Aspect Ratio:**
   - **Canvas Size:** `1080 x 1920` pixels (Vertical `9:16` aspect ratio).
   - **Upscale Target:** Optional 2x AI upscale to `2160 x 3840` (4K) via Topaz Video AI to force high-bitrate platform transcode profiles (e.g., VP09/AV01 on YouTube).
2. **Safe Zones & UI Overlay Coordinates:**
   - **YouTube Shorts Universal Safe Area:**
     - Top Exclusion: `Y = 0 to 180 px` (Search header and sound icon).
     - Bottom Exclusion: `Y = 1450 to 1920 px` (Title, `@handle`, sound marquee, subscribe button).
     - Right Margin Exclusion: `X = 960 to 1080 px` (Like, Comment, Share, Remix icons).
     - **Active Canvas Box:** `900 x 1160 px` (Centered horizontally and vertically between Y:180 and Y:1450).
   - **TikTok Safe Area:**
     - Top Exclusion: `Y = 0 to 160 px` (Following / For You tabs, Search bar).
     - Bottom Exclusion: `Y = 1470 to 1920 px` (Username, caption, audio marquee, system nav bar).
     - Right Rail Exclusion: `X = 960 to 1080 px` (Profile avatar, Like heart, Comment, Bookmark, Share stack).
     - Left Margin Clearance: `40 px` minimum clearance from X = 0.
     - **Active Canvas Box:** `920 x 1250 px` (Vertically centered between Y:160 and Y:1470).
   - **YouTube Channel Branding Surfaces:**
     - Banner Dimensions: `2048 x 1152 px` (16:9, max 6 MB). Central Cross-Device Safe Area: `1235 x 338 px`.
     - Profile Picture: Minimum `98 x 98 px` PNG/GIF (non-animated, max 4 MB), rendered circular at `32 x 32 px` on mobile feeds.
     - Watermark: `150 x 150 px` square PNG/GIF/JPEG (max 1 MB), fixed lower-right corner on desktop horizontal player.
3. **Frame Rates & Motion Fluidity:**
   - **Frame Rate:** `60 fps` Constant Frame Rate (`CFR`) mandatory for fast stage lighting and laser strobes; `30 fps CFR` acceptable fallback. Variable Frame Rate (`VFR`) strictly prohibited.
4. **Encoding Codecs & Bitrate Ceilings:**
   - **Standard Social Export:** `H.264` (`libx264`), MP4 container (`.mp4`), `8–12 Mbps` VBR (Master preset target: `10–12 Mbps`).
   - **High-Fidelity Archive / Media Pipeline:** `H.265 / HEVC` (`libx265` or `hevc_nvenc`) or `AV1` (`libsvtav1` or `av1_nvenc`), `15–20 Mbps` VBR, with a hard maximum ceiling of `25 Mbps`.
5. **Color & Sensor Filtering:**
   - **Low-Light Sensor Denoising:** Spatio-temporal filtering (`hqdn3d` or `nlmeans` in FFmpeg; `Nyx` or `Proteus Fine Tune` in Topaz Video AI) to eliminate high-ISO sensor noise.
   - **Dynamic Range Preservation:** Preserve highlight detail in high-contrast laser and pyrotechnic bursts; prevent clipping in laser apexes and avoid crushing sub-blacks in dark club backgrounds.

---

### Category 2: Audio Engineering & Mastering Parameters

1. **Loudness Standards & Targets:**
   - **Integrated Loudness Target ($I$):** `-14.0 LUFS` ($\pm 1.0 \text{ LUFS}$ tolerance).
   - **Loudness Range ($LRA$):** `7.0 LRA`.
   - **True Peak Ceiling ($TP$):** `-1.0 dBTP` (production pipeline) to `-1.5 dBTP` (media engineering standard in `content_creation/GEMINI.md`).
2. **Filter Graphs & Two-Pass Loudnorm:**
   - **Two-Pass Normalization Filter:** `loudnorm=I=-14:LRA=7:TP=-1.5` (or `TP=-1.0`).
   - **High-Pass Cutoff (Low-Cut):** `40 Hz` minimum cutoff in studio DAWs/CapCut to eliminate sub-audible stage rumble; `80 Hz` cutoff for bass-heavy live festival environments.
   - **Audio Codec & Bitrate:** `AAC-LC` (`aac`), `320 kbps`, `48 kHz`, Stereo.
3. **Drop Detection & Stem Separation DSP:**
   - **Drop Detection Engine:** `Librosa` Python library analyzing Root Mean Square (RMS) energy:
     $$\text{RMS Energy} > 0.8 \implies \text{Drop Trigger Identified}$$
   - **Stem Separation Engine:** `Demucs` isolation targeting the `'Other'` stem (synths, leads, percussion) to separate musical feeds from crowd screams and microphone bleed.
4. **Phase-Aligned Hybrid Audio Mixing:**
   - **Ratio:** `70%` Studio Master Track Audio mixed with `30%` Live Crowd Reverb/Microphone Feed.
   - **Alignment Requirement:** Microsecond waveform phase alignment to eliminate acoustic comb filtering.
5. **TikTok Ghost-Linking Volume Matrix:**
   - **Added Sound (Official Studio Track):** `1% to 3%` volume.
   - **Original Sound (Remastered Live Concert Audio):** `100%` volume.
6. **Seamless Loop Audio Micro-Fade:**
   - **Crossfade Window:** `30 ms` linear micro-fade at the transition boundary across an `8-bar` or `4-bar` loop cycle.

---

### Category 3: Hook, Structure, Pacing & Retention Formulas

1. **Clip Duration Guardrails:**
   - **Total Duration Window:** Strictly `15 to 45 seconds` (Absolute ceiling: `≤ 59 seconds` on YouTube Shorts to prevent Content ID global blocks; `≤ 60 seconds` on TikTok to prevent sound muting).
2. **High-Retention Structure (The 15-Minute Fast-Track Formula):**
   - **Phase 1: The Hook / Build-up:** Exactly `4.0 seconds` of tension build-up.
   - **Phase 2: The Drop Payoff:** `12.0 to 16.0 seconds` of explosive visual/audio drop.
   - **Total Runtime:** `16.0 to 20.0 seconds`.
3. **Genre-Specific Pacing & BPM Matching:**

| Genre Group | Typical Tempo | Hook Window & Cutting Strategy | Visual Focus & Edits |
|:---|:---|:---|:---|
| **Bass Music / Dubstep / Trap** | 140–150 BPM | Cut starts **1.5s before the drop** on final riser; hard cut exactly as bass drop and pyro trigger. | Kinetic zoom edits, rail-riding crowd reactions, violent headbanging, high-contrast strobe flashes. |
| **House / Tech House / Techno** | 124–130 BPM | Rolling 4/4 groove; cut into vocal hook or groove; loop precisely on **4-bar or 8-bar measure**. | Hypnotic laser sweeps, warehouse club lighting, DJ deck POV, hand movements. |
| **Trance / Melodic Dubstep / Future Bass** | 138–145 BPM | Emotional vocal climax and synth buildup leading into bright drop. | Wide festival stage shots, massive laser light canopies, crowd singing moments. |
| **Drum & Bass / Hardstyle** | 150–175+ BPM | Rapid cuts synced to fast kick drums or double-time rhythms. | High-speed strobe effects, light flashes, fast-paced kinetic crowd energy. |

4. **On-Screen Typography & Track ID Placement:**
   - Kinetic text with drop shadow / high-contrast stroke placed within the upper-third portion of the universal safe zone (`Y: 250–500 px`).

---

### Category 4: Platform-Specific Constraints & Operations

#### 1. YouTube Shorts Platform Ecosystem
- **Audience Classification:** `"No, set this channel as not made for kids."` (Mandatory).
- **Default Category:** `Music`.
- **Default Visibility:** `Unlisted` (Pre-flight hold for 30–60 min to complete HD/VP09 processing and Content ID validation).
- **Default License:** `Standard YouTube License`.
- **Copyright Policy:**
  - `≤ 59s` with Content ID match $\to$ Standard Copyright Claim (Ad revenue shared/directed to label, 0 strikes, remains live worldwide).
  - `61–180s` with Content ID match $\to$ **Global Block** (Video blocked worldwide, algorithmic demotion).
  - Unreleased Stolen Leaks $\to$ Risk of **DMCA Takedown** (1 Strike; 3 strikes in 90 days = account termination).
- **Comment Moderation & Blocklist:**
  - Check **"Block links"** setting.
  - Automated Filter Blocklist:
    ```text
    t.me/, whatsapp, crypto, investment, check bio, full set link, telegram, drop your track, promo on, dm to promote, click here, ticket sale, buy tickets, leak, scam, dm me, free download
    ```

#### 2. TikTok Platform Ecosystem
- **Account Type:** **Personal or Creator Account** (Business accounts strictly forbidden due to commercial music licensing locks).
- **High-Quality Upload Setting:** Explicitly toggle **"Allow High-Quality Uploads" = ON** under "More options" on the final post screen for every upload.
- **Audio Muting Rule:** Commercial music in original sounds muted if video $> 60\text{s}$.
- **Caption SEO Template:**
  ```text
  [Artist Name] dropping [Track ID / Title] live at [Festival Name] [Year] 🤯 [Stage Name] was electric. #EDM #[Genre] #[Festival] #[Artist] #LiveMusic #EDMTok
  ```
- **The 5–7 Hashtag Formula:**
  - 2 Broad: `#EDM`, `#Festival`
  - 2 Sub-genre: `#TechHouse`, `#Dubstep`, `#Techno`
  - 2 Entity/Event: `#[ArtistName]`, `#[FestivalName2026]`
  - 1 Community/Intent: `#EDMTok` or `#UnreleasedID`

#### 3. Cross-Platform Publishing & Velocity Protocols
- **Daily Publishing Windows:**
  - Post 1: `10:00 AM EST` (Peak EU evening & transit browsing).
  - Post 2: `6:00 PM EST` (Peak US after-work scrolling).
- **First-Hour Engagement Pinned Comments:**
  - *Track ID Bounty:* `"This unreleased track blew our minds. Crowdsourcing the ID—who knows who produced this? 👇"`
  - *Binary Rating Scale:* `"Laser and bass drop rating: 1 to 10? Drop your rating below! 🔥👇"`
  - *Direct Artist Tagging:* `"Filmed live at [Event]. @[ArtistHandle] dropped this at 3 AM. When is this master finally dropping?! 🔊"`

---

### Category 5: Brand Matrix & Content Pillars

```
+------------------------------------------------------------------------------------------------+
|                                    MASTER BRAND ARCHITECTURE                                   |
+------------------------------------------------------------------------------------------------+
|                          LASER BAPTISM                         |         MUSIC BAPTISM         |
|  - High-energy visual & laser synchronization                  | - Total acoustic immersion    |
|  - Stadium house, dubstep, heavy techno, hardstyle             | - Multi-genre emotional sets  |
|  - Handles: @LaserBaptismLive, @LaserBaptismClips              | - Handles: @MusicBaptismLive  |
|  - Visual: Neon laser slicing synth wave on black background   | - Visual: Intimate DJ POV/deck|
+------------------------------------------------------------------------------------------------+
                                           |
                                           v
+------------------------------------------------------------------------------------------------+
|                                       CONTENT PILLARS                                          |
|  - Pillar A: Big Artist Stadium & Arena Shows (Skrillex, Garrix, Charlotte de Witte, Excision) |
|  - Pillar B: Up-and-Coming Artist Spotlights (Club venues, warehouse raves, #LaserBaptismID)   |
|  - Pillar C: Festival Mega-Clips (EDC, Tomorrowland, Ultra, Lost Lands, Movement)              |
+------------------------------------------------------------------------------------------------+
```

---

### Category 6: Operational Pipelines, Workflows & Storage Schemas

#### 1. Dual-Track Editing SOPs
- **Track A: The High-Fidelity "North Star" Pipeline:**
  $$\text{Raw Clip} \xrightarrow{\text{Librosa RMS}>0.8} \text{Demucs 'Other'} \xrightarrow{\text{iZotope RX HPF 40Hz + De-clip}} \text{FabFilter Pro-L2 (-1.0dBTP)} \xrightarrow{\text{Topaz Nyx/Proteus 4K}} \text{DaVinci Resolve Smart Reframe 9:16}$$
- **Track B: The 15-Minute Fast-Track SOP:**
  1. Ingest & Scrub (4s build-up + 12–16s drop payoff).
  2. Audio Clean & Bass Tame (1-knob AI denoise, 40 Hz low-cut, normalize to -14 LUFS).
  3. Vertical Framing (9:16 aspect ratio within 900x1160 px safe zone).
  4. Track ID Overlay (Kinetic text with drop shadow).
  5. Infinite Loop (30ms micro-fade over 8-bar loop).
  6. Export (1080x1920, H.264, 60fps CFR, 10–12 Mbps, AAC 320kbps).

#### 2. Storage & Directory Taxonomy
- **4-Folder Hybrid Architecture:**
  - `01_RAW_INBOX` (Folder Color: Red) — Raw mobile uploads sorted by Event Name.
  - `02_IN_PROGRESS` (Folder Color: Orange) — Active NLE timelines, Demucs stems, denoised masters.
  - `03_READY_TO_POST` (Folder Color: Green) — Platform-ready, watermarked MP4s.
  - `04_ARCHIVE` (Folder Color: Gray) — Compressed cold backups.
- **Nesting Rule:** Max `50 items` per subfolder.
- **Standardized File Naming Syntax:**
  `YYYYMMDD_[Event]_[Artist]_[TrackName-or-ID]_V[#]_[Resolution].mp4`  
  *(e.g., `20260821_EDCOrlando_JohnSummit_WhereYouAre_V1_1080p.mp4`)*

#### 3. Spark Orchestration Engine Subsystems
- **Subsystem 1: Asset Ingestion & Routing:** MCP bridge connecting mobile upload folders to Google Drive; Python script extracts EXIF/XMP GPS, timestamp, and ISO metadata.
- **Subsystem 2: Competitive Intelligence Tracker:** Scrapers gathering trending sounds, track IDs, view velocities from YouTube Shorts & TikTok feeds into Google Sheets via GPT Workspace.
- **Subsystem 3: Pre-Production & Publishing:** Google Flow tempo/shot list mapping; automated vertical video draft generation pushed to Blogger API v3.

#### 4. Future Content Concepts Roadmap
1. *ID Hunter Series:* Weekly top-3 unreleased track spotlight.
2. *Laser Canopy Stack:* Pure visual/spatial audio laser ASMR.
3. *Multi-Angle Switch:* DJ booth POV side-by-side with front-row crowd reaction.
4. *BPM Acceleration Drop:* 128 BPM house transitioning into 150+ BPM hardstyle/DnB.
5. *Interactive Track ID Bounty:* Mystery track sleuthing with community bounty.
6. *Festival Audio Remastering Hub:* Historical distorted viral clips restored with hybrid mixes.
7. *1001Tracklists Webhook:* Real-time alerts when wanted IDs are identified.
8. *Live Soundboard Hybrid Fader:* On-screen fader graphic showing board feed vs crowd mic blend.

---

### Category 7: AI Context Injection Prompt & Agent Orchestration Rules

```markdown
System Prompt for EDM Short-Form Automation Assistant:
You are the master co-pilot for the @LaserBaptism and @MusicBaptism short-form media brands. Your job is to generate on-brand captions, title structures, video editing guides, and metadata tags based on our Master Operational Blueprint.

Ensure you adhere to these core guardrails in every response:
1. Brand Boundaries:
   - "Laser Baptism" focuses on heavy stadium visuals, massive laser displays, club POVs, and unreleased IDs.
   - "Music Baptism" focuses on deep acoustic immersion, emotional vocal climaxes, and diverse dance subgenres.
2. Technical Guardrails:
   - Video length must be kept strictly under 60 seconds (target: 15–45 seconds) to avoid global Content ID blocks.
   - All visual highlights, texts, and DJ faces must reside within the 900x1160 px universal safe zone for YouTube and 920x1250 px for TikTok.
3. Audio Rule:
   - We use Phase-Aligned Hybrid Audio (mixing 70% studio track audio with 30% live crowd reverb). On TikTok, always use the Ghost-Linking Method (official track at 1-3% volume, remastered live venue sound at 100%).
```
