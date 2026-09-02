# Samsung Galaxy S26 Ultra EDM Concert & Festival Capture Standard Operating Procedure (SOP)

**Document ID:** SOP-S26U-CONCERT-001  
**Operational Track:** Track 2 (/content_creation) — Media Engineering & Live Event Video Production  
**Target Hardware:** Samsung Galaxy S26 Ultra (One UI / Android 16 / ISOCELL 200MP Multi-Sensor Platform)  
**Downstream Pipeline:** Autonomous AI Master Mind Ingestion, Transcoding & Mastering Suite  
**Specification Version:** 2026.1  
**Last Updated:** 2026-08-22  
---

## 1. Executive Summary & Hardware Engineering Overview

Capturing high-energy Electronic Dance Music (EDM) festival and stadium concert footage on mobile hardware presents extreme physical and optical challenges:
1. **Dynamic High-Contrast Lighting:** Nanosecond strobe bursts, multi-watt stage lasers (Class 3B/4), high-density LED backdrop walls with high-frequency PWM switching, and sudden pitch-black stage blackouts.
2. **Extreme Acoustic Sound Pressure Levels (SPL):** Sound systems at major festivals (e.g., EDC, Ultra, Tomorrowland, Lost Lands) routinely generate 105 dB to 125+ dB SPL, with sub-bass peaks reaching 130 dB SPL at the rail.
3. **High-Speed Kinetic Motion:** Fast artist movements, rail-riding crowd headbanging, rapid pyrotechnic detonations, and confetti bursts.

Standard automatic smartphone camera modes fail catastrophically in this environment due to continuous auto-exposure hunting, auto-white-balance color shifting, focus hunting through theatrical haze, and severe audio clipping at the microphone capsule preamp.

The **Samsung Galaxy S26 Ultra** provides a professional-grade mobile capture platform featuring a 200MP ISOCELL multi-gain sensor, 10-bit HDR10+ recording, high-bitrate HEVC compression, multi-microphone directional arrays with manual analog/digital gain attenuation, and granular Pro Video mode manual controls.

This report establishes the complete technical specification, physical sensor analysis, acoustic calibration guidelines, and operational runbook required to produce broadcast-quality raw 4K footage that seamlessly feeds the downstream `content_creation` automated ingestion, transcoding, and mastering pipeline.

---

## 2. Samsung Galaxy S26 Ultra Sensor & Optical Architecture

```
+----------------------------------------------------------------------------------------------------+
|                               S26 ULTRA REAR OPTICAL SENSOR ARRAY                                 |
+----------------------------------------------------------------------------------------------------+
|  [ULTRAWIDE]                 [PRIMARY WIDE]                [3X TELEPHOTO]          [5X PERISCOPE]  |
|  - 50MP ISOCELL              - 200MP ISOCELL Primary       - 10MP / 50MP Sensor    - 50MP Sensor   |
|  - 1/2.55" Optical Format    - 1/1.3" Optical Format       - 1/3.52" / 1/2.52"     - 1/2.51"       |
|  - f/2.0-f/2.2 Aperture      - f/1.7 Aperture + OIS        - f/2.4 Aperture + OIS  - f/3.4 + OIS   |
|  - 120° FOV                  - Tetra²pixel (16:1 / 4:1)    - 3x Optical Zoom       - 5x Optical    |
|  - Dual Pixel PDAF           - Dual Slope Gain (DSG) HDR   - Dual Pixel PDAF       - 10x Sensor-In |
+----------------------------------------------------------------------------------------------------+
```

### 2.1 Primary 200MP ISOCELL Sensor & Pixel Binning Architecture
*   **Sensor Specifications:** 200 Megapixels, 1/1.3-inch optical format, native $0.6\,\mu\text{m}$ photosite pitch, $f/1.7$ aperture lens with enhanced Optical Image Stabilization (OIS) and multi-directional Phase Detection Auto Focus (PDAF / Super Quad Pixel).
*   **Pixel Binning Modes:**
    *   **16-in-1 Tetra²pixel Binning (12.5MP Master):** Groups 16 adjacent $0.6\,\mu\text{m}$ pixels into a single $2.4\,\mu\text{m}$ equivalent super-pixel. This mode delivers maximum photon sensitivity, ultra-low read noise, and optimal dynamic range in extreme low-light concert environments.
    *   **4-in-1 Binning (50MP):** Groups 4 adjacent pixels into a $1.2\,\mu\text{m}$ equivalent pixel. Used for high-detail daylight festival captures.
    *   **Full 200MP Native Mode:** $0.6\,\mu\text{m}$ native resolution; restricted to high-illumination static photography. **Prohibited for concert video recording** due to reduced low-light sensitivity and computational overhead.
*   **Dynamic Range & Dual Conversion Gain:**
    *   Features **Dual Slope Gain (DSG)** / **Smart-ISO Pro** technology. The sensor captures high-conversion-gain (HCG) and low-conversion-gain (LCG) analog signals simultaneously from a single exposure, outputting a merged 10-bit/12-bit high dynamic range stream that preserves stage highlight details (lasers, LED fixtures) without crushing deep venue shadows.

### 2.2 Ultrawide Sensor Capabilities
*   **Sensor Specifications:** 50MP ISOCELL sensor, 1/2.55-inch format, $f/2.0-f/2.2$ aperture, $120^\circ$ ultra-wide field of view, Dual Pixel PDAF.
*   **Concert Utility:** Captures massive stage canopies, arena-wide laser arrays spanning across festival grounds, pyrotechnic aerial shells, and immersive crowd rail perspectives.

### 2.3 Dual Telephoto Array (3x and 5x Periscope)
*   **3x Optical Telephoto:** 10MP/50MP sensor, $f/2.4$ aperture, OIS. Provides clean mid-range framing from Front-of-House (FOH) or VIP viewing decks to the main stage.
*   **5x Periscope Telephoto:** 50MP sensor, 1/2.51-inch format, $f/3.4$ aperture with prism OIS. Enables 5x optical and up to 10x sensor-crop lossless capture of DJ mixer close-ups, hand movements on Pioneer CDJ-3000 / DJM-A9 gear, and expressive artist performance reactions from 30–60 meters distance.

### 2.4 Bit Depth, Dynamic Range & Video Container Profiles
*   **10-bit HDR (Rec.2020 / HDR10+) vs 8-bit SDR (Rec.709):**
    *   **8-bit SDR:** 256 quantization levels per channel (16.7 million colors). Prone to severe color banding in smooth smoke/haze gradients and saturated laser fields.
    *   **10-bit HDR:** 1024 quantization levels per channel (1.07 billion colors). Completely eliminates banding and clipping across intense saturated stage colors (e.g., pure 445nm royal blue, 520nm emerald green, and 638nm crimson laser wavelengths).
*   **Compression Profile & Bitrates:**
    *   **Codec:** HEVC / H.265 Main 10 Profile (`yuv420p10le`) for 10-bit HDR; Main Profile (`yuv420p`) for 8-bit SDR.
    *   **High Bitrate Video Mode:** Pushes 4K UHD 60fps recording bitrates from standard ~48–54 Mbps up to **80.0–100.0+ Mbps VBR**. This increased bit budget is essential for eliminating macroblocking during high-entropy concert scenes (e.g., confetti explosions, rapid strobe flashes, CO2 cannon blasts).

---

## 3. Pro Video Mode Master Settings Matrix (Concert & Festival Standard)

| Parameter | Recommended Master Setting | Fallback / Alternative | Technical Rationale |
| :--- | :--- | :--- | :--- |
| **Shooting Mode** | **Pro Video** | Dedicated Preset | Unlocks full manual control over shutter, ISO, WB, mic gain, and focus. Auto video modes are strictly prohibited. |
| **Resolution** | **4K UHD ($3840 \times 2160$)** | 1080p FHD (High Speed) | Provides pristine canvas for 9:16 vertical center-crop ($1080 \times 1920$) with zero pixel interpolation loss. |
| **Frame Rate** | **60.0 fps (CFR)** | 30.0 fps (Low-light) / 120 fps (Pyro/FX) | High temporal fidelity for rapid laser sweeps and headbanging; allows 50% slow-motion ramping in post. |
| **High Bitrate Video** | **Enabled (ON)** | Standard Bitrate (if storage low) | Pushes bitrate to 80–100 Mbps, preventing macroblocking during strobe and confetti hits. |
| **Color Profile / HDR** | **10-bit HDR10+ / HLG** | 8-bit SDR (BT.709) | 1.07 billion colors; eliminates color banding across laser gradients and intense LED stage lighting. |
| **Shutter Speed** | **$1/120\text{ s}$** (at 60 fps) | $1/60\text{ s}$ (at 30 fps) / Fine-tune | Obey 180° shutter rule; minimizes strobe rolling shutter banding and PWM LED roll. |
| **ISO Gain** | **Manual Lock: ISO 100 – 400** | Max Ceiling: ISO 800 (Dark Club) | Prevents auto-gain pumping during stage blackouts. Maintains maximum sensor SNR and dynamic range. |
| **White Balance (WB)** | **Manual Lock: 5000K – 5200K** | 4200K (Warm Club) / 5600K (Daylight) | Freezes color matrix. Prevents AWB from constantly hunting and distorting stage laser colors. |
| **Microphone Source** | **Rear** (or **Omni**) | USB-C External (if equipped) | "Rear" focuses on stage PA audio and attenuates crowd chatter; "Omni" captures total venue immersion. |
| **Mic Input Gain** | **$-6\text{ dB to }-10\text{ dB}$** | Adjust until VU peaks $\le -6\text{ dBFS}$ | Prevents internal mic capsule analog saturation and digital 0 dBFS clipping under 115–125 dB SPL. |
| **Zoom-in Mic** | **Disabled (OFF)** | **STRICTLY OFF** | Prevents erratic volume and EQ jumps when changing focal lengths or framing. |
| **Focus Mode** | **Manual Focus (MF) with Peaking**| AF Lock (long-press) | Eliminates focus hunting/breathing through stage fog, laser beams, and flashing strobes. |
| **Super Steady** | **Disabled (OFF)** | Rely on Hardware OIS | "Super Steady" uses heavy digital cropping and aggressive EIS that produces warping in low-light. |

---

## 4. Deep-Dive Technical Engineering & Physics Breakdown

### 4.1 Shutter Speed Math, PWM Flicker & Strobe Banding Mitigation

```
+----------------------------------------------------------------------------------------------------+
|                                SHUTTER TIMING & ROLLING SHUTTER ARTIFACTS                          |
+----------------------------------------------------------------------------------------------------+
|  Frame Interval (60 fps): 16.67 ms                                                                 |
|  Sensor Line Readout Time: ~12.5 ms                                                                |
|                                                                                                    |
|  [Strobe Pulse (3ms)] ──▶ Hits during readout ──▶ Top half frame EXPOSED, Bottom half DARK        |
|  SOLUTION: 60 fps capture + Shutter 1/120s restricts line integration window to 8.33ms,            |
|  minimizing the spatial proportion of partial-frame flash artifacts.                               |
+----------------------------------------------------------------------------------------------------+
```

1. **The 180-Degree Shutter Rule:**
   $$\text{Target Shutter Speed} = \frac{1}{2 \times \text{Framerate}}$$
   *   At $60\text{ fps} \rightarrow \text{Shutter} = 1/120\text{ s}$ ($8.33\text{ ms}$ integration time).
   *   At $30\text{ fps} \rightarrow \text{Shutter} = 1/60\text{ s}$ ($16.67\text{ ms}$ integration time).
   *   At $120\text{ fps} \rightarrow \text{Shutter} = 1/240\text{ s}$ ($4.17\text{ ms}$ integration time).
2. **LED Stage Backdrop Wall PWM Flicker Mitigation:**
   *   Stage LED walls (e.g., Roe Visual, Unilumin) refresh at high frequencies ($1920\text{ Hz}$, $3840\text{ Hz}$, or $7680\text{ Hz}$), but video processors synchronize at AC mains frequencies ($60\text{ Hz}$ in North America, $50\text{ Hz}$ in Europe/Asia).
   *   When phone rolling shutter speed creates a beat frequency against the panel scan cycle, dark horizontal bars roll across the video.
   *   *Remediation:* Set shutter to an integer multiple of the mains frequency:
     *   **$60\text{ Hz}$ Regions (USA/Canada/Japan):** Lock shutter to $1/60\text{ s}$ or $1/120\text{ s}$.
     *   **$50\text{ Hz}$ Regions (Europe/UK/Australia):** Lock shutter to $1/50\text{ s}$ or $1/100\text{ s}$.
     *   If subtle rolling bars persist in the Pro Video live preview, micro-step the shutter speed slider by one notch (e.g., $1/125\text{ s}$ or $1/90\text{ s}$) until the interference pattern stabilizes.
3. **Strobe Light Banding Mitigation:**
   *   Concert xenon and LED strobes emit rapid flash bursts lasting $2\text{ to }10\text{ ms}$.
   *   Because smartphone CMOS sensors read lines sequentially (rolling shutter scan over $\approx 12.5\text{ ms}$), a strobe flash that triggers during a scan will illuminate only a horizontal fraction of the frame ("split-frame flash").
   *   *Remediation:* Capturing at $60\text{ fps}$ forces the sensor to operate at its highest pixel clock and fastest line readout speed, minimizing the visual duration of split-frame artifacts compared to $24\text{ fps}$ or $30\text{ fps}$.

---

### 4.2 Optical Laser Radiation Hazards & CMOS Sensor Damage Prevention

```
+----------------------------------------------------------------------------------------------------+
|                               LASER RADIATION SENSOR DAMAGE MECHANICS                              |
+----------------------------------------------------------------------------------------------------+
|  [Stage Laser Aperture (10W-30W+ Class 4)] ───────────────────────────────┐                        |
|                                                                           ▼                        |
|                                                     [Smartphone Objective Lens (f/1.7)]            |
|                                                                           │ (Focuses beam)         |
|                                                                           ▼                        |
|                                                     [CMOS Photodiode Array (2.4um pitch)]          |
|                                                     Energy Density > 10 mJ/cm²                     |
|                                                     RESULT: Permanent Silicon Ablation,            |
|                                                     Dead Pixels, and Vertical Line Defects.        |
+----------------------------------------------------------------------------------------------------+
```

*   **The Physics of Laser Damage:**
    *   Stage laser projectors at festivals utilize high-power Class 3B and Class 4 solid-state lasers ranging from **5 Watts to over 40 Watts** per projector.
    *   While venue laser operators must comply with International Laser Display Association (ILDA) audience-scanning regulations (e.g., ANSI Z136, IEC 60825) for human eye safety, **digital CMOS sensors are far more fragile than the human eye**.
    *   The phone’s camera lens acts as a high-precision optical concentrator, focusing parallel laser light down to a microscopic focal spot directly on the silicon photodiode array and color filter array (CFA).
    *   A single direct hit exceeds the optical breakdown threshold ($>10\text{ mJ/cm}^2$), causing instant thermal vaporization of the Bayer color filters, silicon dielectric breakdown, and permanent dead pixel lines across all four camera sensors.
*   **Mandatory Operator Safety Rules:**
    1. **NEVER aim the camera lens directly into the aperture barrel of a stage laser projector.**
    2. **Film Laser Scatter, Not Direct Emitters:** Position the phone to capture atmospheric laser beams traversing through haze/fog, reflecting off crowd hands, or projecting onto backdrops/canopies.
    3. **Angle of Incidence:** Maintain an oblique angle ($>30^\circ$ off-axis) relative to the primary projection vector.
    4. **Safety Plane:** If standing at the front rail, keep the camera below the lowest crowd-scanning termination line, or film upward toward the sky/canopy where beams do not intersect the lens.
    5. **Lens Filters:** Standard UV and CPL glass filters provide **zero protection** against high-power optical lasers.

---

### 4.3 ISO Locking Strategy & Dynamic Range Management

```
+----------------------------------------------------------------------------------------------------+
|                                    AUTO-ISO vs MANUAL ISO LOCKING                                  |
+----------------------------------------------------------------------------------------------------+
|  SCENARIO: Stage Blackout (0.8s) followed by Pyrotechnic / Strobe Drop Drop Hit                     |
|                                                                                                    |
|  [AUTO-ISO BEHAVIOR]:                                                                              |
|  Blackout ──▶ Auto-Exposure ramps ISO to 3200+ ──▶ Strobe Ignites ──▶ BLOWN OUT WHITE FOR 1.5s    |
|                                                                                                    |
|  [MANUAL ISO LOCK BEHAVIOR]:                                                                       |
|  Blackout ──▶ ISO locked at 200 (Clean True Black) ──▶ Strobe Ignites ──▶ PERFECT CRISP EXPOSURE   |
+----------------------------------------------------------------------------------------------------+
```

*   **The Auto-Exposure Failure Mode:**
    *   In auto mode, the camera's metering algorithm interprets a dark concert stage or brief pre-drop blackout as an underexposed scene, immediately ramping sensor gain (ISO $3200–6400$).
    *   When the drop triggers massive pyro, lasers, and blinders, the camera sensor is saturated, resulting in 20–40 frames of completely blown-out, overexposed white frames while the auto-exposure slowly steps down.
*   **Manual ISO Locking Rules:**
    *   **Mainstage Festival / Heavy Lighting:** Lock ISO between **ISO 100 and ISO 250**.
    *   **Standard Concert / Club Stage:** Lock ISO between **ISO 250 and ISO 500**.
    *   **Dark Underground Warehouse / Club Booth:** Lock ISO between **ISO 500 and ISO 800** (Absolute maximum ceiling: **ISO 1600**).
*   **Low-Light Sensor Denoising Synergy:**
    *   Expose for the stage highlights (lasers, LED screens, performer key lights).
    *   Allow deep background shadows to fall to clean true blacks.
    *   Any minor shadow grain at ISO 400–800 will be non-destructively cleaned during Phase 2 transcoding via the FFmpeg `hqdn3d=4:3:6:4.5` spatio-temporal filter without blurring laser edge sharpness.

---

### 4.4 White Balance Calibration & Kelvin Temperature Locking

*   **Auto White Balance (AWB) Failure:**
    *   Concert lighting designers use dynamic RGB moving heads that flood the stage with monochromatic saturated colors (deep red, vibrant cyan, ultraviolet blue, acid green).
    *   AWB continuously tries to "correct" these creative colors to neutral gray, resulting in sickening skin tones, desaturated laser beams, and jarring color temperature oscillations.
*   **Manual Kelvin Lock Selection:**
    *   **$5000\text{K} – 5200\text{K}$ (Direct Daylight / Concert Master Standard):**  
        *Recommended for 95% of all festival and arena concert captures.* Preserves true spectral laser emission wavelengths (445nm royal blue, 520nm emerald green, 638nm crimson red) and keeps performer skin tones natural under white follow-spots.
    *   **$4000\text{K} – 4500\text{K}$ (Neutral / Club Setting):**  
        Used in intimate club environments illuminated predominantly by warm tungsten or amber fixtures.
    *   **$5600\text{K}$ (Daylight / Golden Hour):**  
        Used during daytime and sunset festival stages (e.g., open-air festival day parties).

---

### 4.5 Acoustic Engineering: SPL Handling & Microphone Attenuation

```
+----------------------------------------------------------------------------------------------------+
|                                    PRO VIDEO AUDIO SIGNAL FLOW                                     |
+----------------------------------------------------------------------------------------------------+
|  [Stage PA: 120 dB SPL] ──▶ [Multi-Mic Capsule] ──▶ [Preamp (Set to -8 dB Gain)] ──▶ [24-bit ADC]  |
|                                                              │                                     |
|                                                              ▼                                     |
|                                           [Real-time VU Meters: -12 to -6 dBFS]                    |
|                                           (Zero Analog or Digital Clipping)                        |
|                                                              │                                     |
|                                                              ▼                                     |
|                                         [Phase 2 FFmpeg: loudnorm -14 LUFS]                        |
+----------------------------------------------------------------------------------------------------+
```

*   **Acoustic Physics at EDM Festivals:**
    *   Festival line arrays (e.g., L-Acoustics K1/K2, d&b audiotechnik GSL, PK Sound Trinity) produce sustained acoustic energy of **$110\text{ to }125\text{ dB SPL}$** in the crowd, with sub-bass transient excursions exceeding **$130\text{ dB SPL}$** near the rail.
    *   Standard smartphone video modes apply automatic gain control (AGC) that boosts quiet moments (crowd talking) and clips violently on kick drum transients, producing severe square-wave distortion.
*   **Pro Video Microphone Configuration:**
    1. **Microphone Mode Selection:**
       *   **"Rear" Mic Mode:** Uses the rear-facing microphone capsule situated on the camera island. Directionally attenuates ambient crowd conversations behind the phone while capturing pristine direct-path audio from the stage line array.
       *   **"Omni" Mic Mode:** Uses all 3 device microphones to capture 360-degree venue acoustics (recommended when recording crowd chants and rail reactions).
       *   **"Zoom-in Mic":** **MUST BE DISABLED (OFF).** Zoom-in mic applies aggressive frequency filtering and dynamic gain shifting during zoom actions, destroying audio consistency.
    2. **Manual Preamp Gain Attenuation:**
       *   Open the microphone level control in Pro Video mode.
       *   Attenuate the input gain slider to **$-6\text{ dB to }-10\text{ dB}$** (Standard default: **$-8\text{ dB}$**).
       *   Monitor the live stereo VU meters on screen: ensure kick drum hits and sub-bass drops peak between **$-12\text{ dBFS and }-6\text{ dBFS}$**, maintaining a healthy $6\text{ dB}$ safety headroom margin below $0\text{ dBFS}$ digital clipping.
    3. **Downstream DSP Alignment:**
       *   Raw audio recorded with $-8\text{ dB}$ attenuation is cleanly mastered in Phase 2 of the pipeline using FFmpeg:
         *   High-pass filter at $80\text{ Hz}$ (`highpass=f=80`) to eliminate sub-audible physical wind and diaphragm excursion rumble.
         *   Two-pass EBU R128 loudness normalization to **$-14.0\text{ LUFS} \pm 1.0\text{ LUFS}$** and True Peak ceiling $\le -1.5\text{ dBTP}$.

---

### 4.6 Optical Focusing: Focus Peaking & Hyperfocal Locking

*   **The Auto-Focus Breakdown:**
    *   Concert environments defeat traditional autofocus and LiDAR/laser AF systems. Theatrical fog, rapidly strobing lights, sweeping laser beams crossing the lens axis, and moving crowd hands in the foreground cause the AF motor to hunt continuously ("focus breathing").
*   **Focus Peaking Calibration:**
    1. In Pro Video settings, enable **Focus Peaking**. Set the highlight color to **High-Visibility Green** or **Cyan**.
    2. Switch focus from **Auto (AF)** to **Manual (MF)**.
    3. Rotate the manual focus slider: the green peaking highlights will outline high-contrast edges currently in sharp optical focus.
*   **Focus Distance Strategy:**
    *   **Arena / Stadium / Mainstage ($>15\text{ meters}$ distance):** Set the MF slider to **Hyperfocal / Infinity ($\infty$)**. Everything from 3 meters to infinity remains in crisp focus at $f/1.7$.
    *   **Club / DJ Booth ($2\text{ to }5\text{ meters}$ distance):** Adjust the slider until the green peaking outline crisply hugs the DJ mixer console and artist's face, then lock the focus.

---

## 5. Field Operational Playbook: Step-by-Step Concert Capture SOP

### 5.1 Pre-Show Setup Checklist (5 Minutes Before Set)
```
[ ] Clean all four rear camera lenses thoroughly with a microfiber cloth.
[ ] Open Camera app -> Settings (Gear Icon) -> Advanced Video Options:
    [ ] Enable "High bitrate videos" [ON]
    [ ] Enable "HDR10+ videos" [ON] (or verify HEVC Main 10 profile)
[ ] Select "PRO VIDEO" Mode.
[ ] Set Resolution & Framerate to "UHD 60" (4K @ 60fps).
[ ] Tap "MIC" Icon:
    [ ] Select "Rear" (or "Omni").
    [ ] Set Gain Attenuation slider to -8 dB.
    [ ] Verify "Zoom-in Mic" is disabled [OFF].
[ ] Tap "WB" (White Balance) -> Set to Manual 5000K or 5200K.
[ ] Tap "ISO" -> Set to Manual ISO 200 (Adjust between ISO 100-400 based on stage wash).
[ ] Tap "SPEED" (Shutter) -> Set to 1/120s.
[ ] Tap "FOCUS" -> Switch to MF, verify Green Peaking on stage, lock to Infinity (or stage distance).
[ ] Disable "Super Steady" (rely on hardware OIS).
```

### 5.2 Live Performance Capture Protocol (During Set)
1. **The 4-Second Pre-Drop Lead-in:**
   *   Start recording **$4.0\text{ seconds}$ before the drop** on the final vocal riser or snare roll buildup.
   *   Hold the phone firmly with two hands, elbows anchored against your torso for maximum mechanical stabilization.
2. **The Drop Impact & Payoff:**
   *   Maintain smooth, steady framing through the drop impact ($12\text{ to }16\text{ seconds}$ of drop action).
   *   Do not perform rapid erratic whip-pans. Use slow, deliberate rotational sweeps or push-ins to capture laser apexes and crowd reactions.
3. **Capture Duration Window:**
   *   Target total clip runtime: **$16.0\text{ to }30.0\text{ seconds}$** (Maximum hard ceiling: **$55.0\text{ seconds}$**).
   *   Stopping the recording under $59.0\text{s}$ ensures full compliance with the downstream YouTube Shorts Content ID guardrail.
4. **Lens Switching Rules:**
   *   Do NOT use pinch-to-zoom (which triggers noisy digital zoom).
   *   Tap dedicated optical zoom buttons (**0.6x**, **1x**, **3x**, **5x**) between recordings to utilize native optical lenses.

---

## 6. Pipeline Integration & Downstream Compatibility

The footage captured using this SOP is engineered to integrate seamlessly with the automated `content_creation` pipeline:

```
+----------------------------------------------------------------------------------------------------+
|                                    END-TO-END DATAFLOW PIPELINE                                    |
+----------------------------------------------------------------------------------------------------+
|  [Samsung S26 Ultra (4K60 10-bit HDR / -8dB Mic / Locked WB/ISO)]                                  |
|                                    │                                                               |
|                                    ▼ (Phase 0: samsung_ingest.py via ADB)                          |
|  [content_creation/01_RAW_INBOX/] (Untouched, Zero-Cloud Compression Master)                       |
|                                    │                                                               |
|                                    ▼ (Phase 1: ingest_assets.py & metadata_tracker.py)            |
|  [02_IN_PROGRESS/{project_id}/] (Metadata Extracted, Brand Routed: Laser vs Music Baptism)         |
|                                    │                                                               |
|                                    ▼ (Phase 2: ffmpeg_processor.py)                                |
|  - 9:16 Smart Vertical Crop (Center / Safe-Zone Box 900x1270 px)                                   |
|  - Tone-Mapping: HDR10+ / HLG -> BT.709 SDR (Mobius Curve)                                         |
|  - Denoise: hqdn3d spatio-temporal filter for ISO grain smoothing                                  |
|  - Audio DSP: 80Hz High-pass + Two-pass EBU R128 (-14.0 LUFS, -1.5 dBTP)                           |
|  - Duration Clamping: <= 59.0s (Content ID Guardrail) + 30ms Seamless Loop Fade                    |
|                                    │                                                               |
|                                    ▼ (Phase 3: qc_validator.py & orchestrator.py)                  |
|  [03_READY_TO_POST/] (Signed Master MP4 + Distribution Metadata Package)                           |
+----------------------------------------------------------------------------------------------------+
```

1. **Phase 0 Ingestion (`samsung_ingest.py`):**
   *   Extracts raw MP4 files directly from the device `/sdcard/DCIM/Camera/` directory over USB 3.2 Gen 2 ADB connection at 300+ MB/s, bypassing cloud compression (Google Photos/Dropbox transcoding).
2. **Safe Zone Geometry Compatibility:**
   *   Because the S26 Ultra captures standard 16:9 4K ($3840 \times 2160$), center-cropping to 9:16 ($1080 \times 1920$) places the performer and laser apex directly within the universal safe zones:
     *   **YouTube Shorts Safe Box:** $900 \times 1270\text{ px}$ ($X: 60-960, Y: 180-1450$).
     *   **TikTok Safe Box:** $920 \times 1310\text{ px}$ ($X: 40-960, Y: 160-1470$).
3. **Audio Normalization Compatibility:**
   *   Audio captured with $-8\text{ dB}$ attenuation possesses pristine, unclipped transient waveforms that allow the FFmpeg `loudnorm` filter to compute accurate loudness range ($7.0\text{ LRA}$) and master cleanly to $-14.0\text{ LUFS} \pm 1.0\text{ LUFS}$ with zero inter-sample limiter distortion.

---

## 7. Comprehensive Parameter Quick Reference Card

```
================================================================================
           SAMSUNG S26 ULTRA EDM CONCERT CAPTURE QUICK REFERENCE
================================================================================
CAMERA APP SETTING          VALUE / TARGET SPECIFICATION
--------------------------------------------------------------------------------
Capture Mode                PRO VIDEO
Resolution & FPS            UHD 60fps (3840 x 2160 @ 60.0 fps Constant Frame Rate)
Compression / Codec         HEVC (H.265 Main 10) + High Bitrate Mode [ON]
Dynamic Range               HDR10+ / HLG (10-bit color, Rec.2020)
--------------------------------------------------------------------------------
Shutter Speed               1/120s (60Hz regions) or 1/100s (50Hz regions)
ISO Sensitivity             ISO 100 - 400 (Festival Stage) / ISO 400 - 800 (Dark Club)
White Balance               MANUAL 5000K - 5200K (Daylight / Laser Standard)
Focus Mode                  MANUAL FOCUS (MF) with Green Peaking -> Hyperfocal / Stage
Image Stabilization         Hardware OIS Enabled (Super Steady = OFF)
--------------------------------------------------------------------------------
Microphone Mode             REAR (Stage focus) or OMNI (Crowd + Stage)
Mic Gain Attenuation        -8 dB (Monitor VU meters: Peak between -12 and -6 dBFS)
Zoom-in Mic                 STRICTLY OFF
--------------------------------------------------------------------------------
Clip Duration Target        16.0s - 30.0s (Hard Ceiling: <= 55.0s for Content ID safe)
Framing Safety Margin       Center stage performer & lasers in middle 60% of canvas
Laser Radiation Warning     NEVER aim directly down projector aperture barrels
================================================================================
```

---
*End of Standard Operating Procedure.*