# EDM Viral Formula & Multimodal Video Grading Architecture
**Deep Research Analysis & Mathematical Specification for Short-Form Video Grading (YouTube Shorts, TikTok, Instagram Reels)**

---

## 1. Executive Summary & Algorithmic Foundations

In algorithmic short-form video ecosystems (YouTube Shorts, TikTok, Meta Instagram Reels), discovery and distribution are governed by **satisfaction and retention signals** rather than traditional CTR (Click-Through Rate). 

### 1.1 The Algorithmic Distribution Funnel
1. **Explore Phase (Cold Start / Seed Audience)**:
   - The platform serves a raw video to a test batch of 200–1,000 active users.
   - Primary Gatekeeper: **Viewed vs. Swiped Away (VVSA)** within the first 1.5–3.0 seconds.
     - **VVSA $\ge$ 75%**: Promoted to high-velocity distribution tier.
     - **50% $\le$ VVSA < 75%**: Average performance, incremental testing.
     - **VVSA < 50%**: Algorithmic stall / death.
2. **Exploit Phase (Exponential Virality & Loop Retention)**:
   - Evaluated by **Average Percentage Viewed (APV)** and **Loop / Replay Multiplier ($M_{\text{loop}}$)**.
   - For short videos ($< 30\text{s}$), viral distribution requires $\text{APV} \ge 110\text{--}130\%$ (meaning viewers rewatch at least 1.1x to 1.3x).
3. **EDM Video Unique Physics**:
   - EDM content is fundamentally driven by **tension, anticipation, sensory overload, and collective crowd synchronization**.
   - Unlike narrative comedy or talking-head content, EDM video engagement relies on high sensory density: fast audio transient drops, visual laser/strobe synchronicity, high crowd optical flow kinetic energy, and seamless loop transitions.

---

## 2. The 5 Core Mathematical Viral Grading Parameters

Below are the 5 mathematically formalized grading parameters designed for autonomous evaluation via Google Gemini Video / Omni Flash API and PySpark distributed scoring.

---

### Parameter 1: 3-Second Hook Retention Velocity (HRV)

#### 1. Technical Definition & Rationale
The first 0.0s to 3.0s window determines whether a user swipes or stays. In EDM content, "dead air", silence, or static camera pans cause immediate drop-off. The hook must deliver immediate visual kinetic stimulation, high audio loudness onset, or an explicit curiosity/anticipation anchor.

#### 2. Mathematical Formulation
Let $t \in [0, 3.0]$ seconds.
- $A(t) \in [0, 1]$: Normalized RMS audio envelope amplitude.
- $V_{\text{opt}}(t) \in [0, \infty)$: Mean magnitude of dense optical flow vectors across frame pixels:
  $$V_{\text{opt}}(t) = \frac{1}{W \cdot H} \sum_{x=1}^W \sum_{y=1}^H \sqrt{u(x,y,t)^2 + v(x,y,t)^2}$$
- $N_{\text{transients}}$: Number of discrete audiovisual pattern interrupts (jump cuts, camera zooms, bass hits, text overlays) in $[0, 3.0]\text{s}$.
- $t_{\text{onset}}$: Timestamp of initial audio/visual event (seconds).

The Hook Kinetic Density $D_{\text{hook}}$ is:
$$D_{\text{hook}} = \int_{0}^{3.0} \left( 0.55 \cdot A(t) + 0.45 \cdot \min(1.0, \frac{V_{\text{opt}}(t)}{V_{\text{norm}}}) \right) dt$$

The Raw HRV Function:
$$\text{HRV}_{\text{raw}} = \left[ 0.40 \cdot \frac{D_{\text{hook}}}{3.0} + 0.35 \cdot \min\left(1.0, \frac{N_{\text{transients}}}{3.0}\right) + 0.25 \cdot \max\left(0, 1.0 - \frac{t_{\text{onset}}}{0.5}\right) \right]$$

#### 3. Scoring Scale (0–100)
$$S_{\text{HRV}} = 100 \times \text{Clamp}_{[0, 1.0]}(\text{HRV}_{\text{raw}})$$

*Scale Benchmarks:*
- `90–100`: Instantaneous explosion ($t_{\text{onset}} < 0.1\text{s}$), drop tease or intense crowd action, $>3$ visual pattern interrupts.
- `70–89`: Solid hook with immediate music presence and clear visual focus within 0.5s.
- `40–69`: Sluggish start, music builds slowly without on-screen visual tension.
- `0–39`: Dead air ($>1.0\text{s}$ silence/black screen), shaky unfocused floor shot, instant swipe trigger.

---

### Parameter 2: Drop Pacing & Anticipation Window (DPAW)

#### 2. Technical Definition & Rationale
In short-form media (15s–45s), traditional full-length EDM build-ups (30s–60s) fail catastrophically. The optimal tension-to-release curve requires:
1. An anticipation build-up window of **3.0s to 6.5s**.
2. A pre-drop silence/vocal pocket of **150ms to 450ms** (acoustic vacuum before the bass slam).
3. The primary drop climax occurring within the **40% to 65% duration mark** of the video clip ($t_{\text{drop}} \in [0.40 T, 0.65 T]$) to allow sufficient post-drop payoff and loop setup.

#### 2. Mathematical Formulation
Let $T$ be total video duration in seconds.
- $t_{\text{drop}}$: Timestamp of the drop impact (kick/bass entry).
- $W_{\text{build}} = t_{\text{drop}} - t_{\text{build\_start}}$: Build-up duration in seconds.
- $\Delta t_{\text{pocket}}$: Duration of pre-drop micro-pause / vocal sample silence window.

Normalized Drop Position Metric:
$$P_{\text{pos}} = \exp\left( -\frac{\left(\frac{t_{\text{drop}}}{T} - 0.52\right)^2}{2 \cdot (0.12)^2} \right)$$

Build-up Duration Metric (Gaussian centered at $\mu=4.5\text{s}, \sigma=1.5\text{s}$):
$$B_{\text{window}} = \exp\left( -\frac{(W_{\text{build}} - 4.5)^2}{2 \cdot (1.5)^2} \right)$$

Pre-Drop Pocket Metric:
$$Q_{\text{pocket}} = \begin{cases}
1.0 & \text{if } 0.15 \le \Delta t_{\text{pocket}} \le 0.45\text{s} \\
0.5 + 0.5 \cdot \frac{\Delta t_{\text{pocket}}}{0.15} & \text{if } 0.0 < \Delta t_{\text{pocket}} < 0.15\text{s} \\
\max\left(0, 1.0 - \frac{\Delta t_{\text{pocket}} - 0.45}{0.5}\right) & \text{if } \Delta t_{\text{pocket}} > 0.45\text{s}
\end{cases}$$

#### 3. Scoring Scale (0–100)
$$S_{\text{DPAW}} = 100 \times \left( 0.45 \cdot P_{\text{pos}} + 0.35 \cdot B_{\text{window}} + 0.20 \cdot Q_{\text{pocket}} \right)$$

*Scale Benchmarks:*
- `90–100`: Flawless 4s build, crisp pre-drop vocal chop/silence, bass drops at 50% duration.
- `70–89`: Well-timed drop between 40–65% duration, build-up under 7 seconds.
- `40–69`: Drop occurs too early ($<2\text{s}$, no build anticipation) or too late ($>75\%$ of video, viewer abandons before payoff).
- `0–39`: No drop detected, linear repetitive loop without dynamic release.

---

### Parameter 3: Audio Dynamic Range & Spectral Flux Delta (ADR-SFD)

#### 1. Technical Definition & Rationale
Visceral EDM impact requires a massive acoustic contrast between the build-up phase and the drop. The drop must exhibit a dramatic surge in **Sub-Bass Power (30 Hz – 90 Hz)**, a surge in **High-Frequency Spectral Flux** (cymbals, saw leads, distortion harmonics), and an integrated loudness delta ($\Delta \text{LUFS}$) of $+4\text{ to }+8\text{ LUFS}$ without catastrophic clipping/distortion.

#### 2. Mathematical Formulation
Let $X(t, f)$ denote Short-Time Fourier Transform (STFT) magnitude at time $t$ and frequency bin $f$.
- **Spectral Flux (SF)**:
  $$\text{SF}(t) = \sum_{f} \mathcal{H}\left( |X(t, f)| - |X(t - \Delta t, f)| \right)$$
  where $\mathcal{H}(x) = \max(0, x)$ is half-wave rectification.
- **Sub-Bass Energy Ratio ($R_{\text{sub}}$)**:
  $$E_{\text{sub}}(t) = \int_{30\,\text{Hz}}^{90\,\text{Hz}} |X(t, f)|^2 df$$
  $$R_{\text{sub}} = \frac{\text{Mean}_{t \in \text{drop}}(E_{\text{sub}}(t))}{\text{Mean}_{t \in \text{build}}(E_{\text{sub}}(t)) + \epsilon}$$
- **Integrated Loudness Delta ($\Delta \text{LUFS}$)**:
  $$\Delta \text{LUFS} = \text{LUFS}_{\text{drop}} - \text{LUFS}_{\text{build}}$$

ADR-SFD Composite:
$$\text{SFD}_{\text{norm}} = \min\left(1.0, \frac{\text{Peak}(\text{SF}_{\text{drop}}) - \text{Mean}(\text{SF}_{\text{build}})}{\sigma_{\text{SF}} + \epsilon}\right)$$
$$R_{\text{norm}} = \text{Clamp}_{[0, 1.0]}\left( \frac{\log_{10}(R_{\text{sub}} + 1.0)}{\log_{10}(10.0)} \right)$$
$$L_{\text{norm}} = \text{Clamp}_{[0, 1.0]}\left( \frac{\Delta \text{LUFS}}{6.0} \right)$$

#### 3. Scoring Scale (0–100)
$$S_{\text{ADR-SFD}} = 100 \times \left( 0.40 \cdot R_{\text{norm}} + 0.35 \cdot \text{SFD}_{\text{norm}} + 0.25 \cdot L_{\text{norm}} \right)$$

*Scale Benchmarks:*
- `90–100`: Massive sub-bass slam, instant wide-band spectral explosion, clear mastering dynamics.
- `70–89`: Good bass punch and noticeable loudness jump on drop.
- `40–69`: Flat acoustic profile, muddy bass, or heavy phone microphone limiter squashing.
- `0–39`: Distorted digital peaking/screeching, blown-out mic clipping, or near-zero low-end bass presence.

---

### Parameter 4: Crowd Kinetic Energy & Motion Vector Entropy (CKE-MVE)

#### 1. Technical Definition & Rationale
Short-form festival virality relies on emotional and physical contagion. When viewers see thousands of people jumping in perfect synchronization or mosh pits opening and collapsing, mirror neurons trigger high emotional arousal. We measure crowd bounding box density, vertical velocity coherence ($v_y$ jump phase), and kinetic energy burst at drop onset.

#### 2. Mathematical Formulation
Let $\vec{v}(x,y,t) = (u, v)$ be optical flow vectors for pixels belonging to detected human/crowd segments $\Omega_{\text{crowd}}$.
- **Vertical Jump Coherence ($C_{\text{jump}}(t)$)**:
  $$C_{\text{jump}}(t) = \frac{\left| \sum_{(x,y) \in \Omega} v(x,y,t) \right|}{\sum_{(x,y) \in \Omega} |v(x,y,t)| + \epsilon}$$
  ($C_{\text{jump}} \approx 1.0$ when entire crowd moves upwards/downwards in sync; $\approx 0$ for chaotic random jitter).
- **Kinetic Energy Acceleration ($\Delta E_{\text{kinetic}}$)**:
  $$E_k(t) = \frac{1}{|\Omega|} \sum_{(x,y) \in \Omega} \left( u(x,y,t)^2 + v(x,y,t)^2 \right)$$
  $$\Delta E_{\text{kinetic}} = \frac{\text{Mean}_{t \in [t_{\text{drop}}, t_{\text{drop}}+3.0]}(E_k(t))}{\text{Mean}_{t \in [t_{\text{drop}}-3.0, t_{\text{drop}}]}(E_k(t)) + \epsilon}$$
- **BPM Motion Phase Coupling ($\Phi_{\text{BPM}}$)**:
  Cross-correlation between vertical velocity oscillation frequency and music BPM tempo ($128\text{--}175\text{ BPM}$):
  $$\Phi_{\text{BPM}} = \text{Corr}(v_y(t), \cos(2\pi \cdot f_{\text{BPM}} \cdot t))$$

#### 3. Scoring Scale (0–100)
$$S_{\text{CKE-MVE}} = 100 \times \left( 0.40 \cdot \min\left(1.0, \frac{\Delta E_{\text{kinetic}}}{4.0}\right) + 0.35 \cdot C_{\text{jump}}(t_{\text{drop}}) + 0.25 \cdot \max(0, \Phi_{\text{BPM}}) \right)$$

*Scale Benchmarks:*
- `90–100`: Massive crowd jump sync, mosh pit eruption, or sea of arms pumping in exact tempo.
- `70–89`: Clear visible crowd movement and energy increase at drop.
- `40–69`: Passive crowd standing still or sparse audience with low movement.
- `0–39`: Static crowd, no human interaction, or back of person's head blocking screen.

---

### Parameter 5: Lighting Transition & Strobe Peak Synchronicity (LTSS)

#### 1. Technical Definition & Rationale
Stage production (lasers, moving heads, CO2 cryo jets, pyrotechnic flame cannons, and strobe bursts) creates visual dopamine. The visual transients must hit within $\pm 33\text{ms}$ (1 video frame at 30 fps) of the musical transients. We evaluate lighting state delta, strobe frequency ($8\text{--}20\,\text{Hz}$), and cryogenic/laser density.

#### 2. Mathematical Formulation
Let $Y(x,y,t)$ be luminance in ITU-R BT.709 color space:
- Frame Luminance $L(t) = \frac{1}{W \cdot H}\sum_{x,y} Y(x,y,t)$.
- Strobe Modulation Frequency $f_{\text{strobe}}$: Dominant spectral peak of $\frac{d L(t)}{dt}$ in $[6, 25]\,\text{Hz}$.
- Transient Alignment Latency $\tau_{\text{sync}}$:
  $$\tau_{\text{sync}} = |t_{\text{light\_burst}} - t_{\text{audio\_transient}}|$$
- Production Feature Multiplier $F_{\text{prod}}$:
  $$F_{\text{prod}} = \min(1.0, 0.3 \cdot \mathbb{I}_{\text{lasers}} + 0.3 \cdot \mathbb{I}_{\text{pyro}} + 0.2 \cdot \mathbb{I}_{\text{CO2\_cryo}} + 0.2 \cdot \mathbb{I}_{\text{visual\_LED}})$$

Synchronicity Metric:
$$\text{Sync}_{\text{score}} = \exp\left( -\frac{\tau_{\text{sync}}^2}{2 \cdot (0.033)^2} \right)$$

#### 3. Scoring Scale (0–100)
$$S_{\text{LTSS}} = 100 \times \left( 0.40 \cdot \text{Sync}_{\text{score}} + 0.35 \cdot F_{\text{prod}} + 0.25 \cdot \text{Clamp}_{[0,1]}\left(\frac{f_{\text{strobe}} - 4.0}{12.0}\right) \right)$$

*Scale Benchmarks:*
- `90–100`: Exact-frame laser/pyro/CO2 blast on the drop transient with high-speed strobe modulation.
- `70–89`: Well-synchronized lighting changes and active stage visuals.
- `40–69`: Out-of-sync lights (delayed by $>0.2\text{s}$), dim club lighting without distinct stage production.
- `0–39`: Pitch black, washed out static lighting, or no lighting shifts on the drop.

---

## 3. Composite EDM Viral Potential Index (EVPI)

### 3.1 Composite Formula & Weight Distribution
The composite **EDM Viral Potential Index (EVPI)** is computed via a weighted linear combination modulated by nonlinear algorithmic killswitches:

$$\text{EVPI} = \left( \sum_{i=1}^5 w_i \cdot S_i \right) \times \prod_{k=1}^3 K_k$$

#### Weight Matrix:
| Parameter | Symbol | Weight ($w_i$) | Algorithmic Justification |
| :--- | :--- | :--- | :--- |
| **3-Second Hook Retention Velocity** | $S_{\text{HRV}}$ | **0.25** | Governs the critical VVSA gatekeeper ($<3\text{s}$ swipe-away). |
| **Drop Pacing & Anticipation Window** | $S_{\text{DPAW}}$ | **0.25** | Prevents early churn; ensures drop payoff occurs in optimal retention window. |
| **Audio Dynamic Range & Spectral Flux** | $S_{\text{ADR-SFD}}$ | **0.20** | Delivers acoustic shock value and bass fidelity. |
| **Crowd Kinetic Energy & Motion Entropy** | $S_{\text{CKE-MVE}}$ | **0.15** | Drives psychological contagion and shareability. |
| **Lighting Transition & Strobe Sync** | $S_{\text{LTSS}}$ | **0.15** | Provides visual dopamine and professional production value. |
| **Total** | | **1.00** | Standardized 0.0 – 100.0 Scale |

### 3.2 Non-Linear Killswitch Modifiers ($K_k \in [0.0, 1.0]$)
1. **Audio Integrity Killswitch ($K_{\text{audio}}$)**:
   - If audio is muted, completely silent, or exhibits severe continuous digital clipping distortion $>30\%$ of runtime $\implies K_{\text{audio}} = 0.1$.
2. **Aspect Ratio & Resolution Killswitch ($K_{\text{format}}$)**:
   - Vertical 9:16 format ($1080\times 1920$ or $2160\times 3840$) $\implies K_{\text{format}} = 1.0$.
   - Horizontal 16:9 with letterboxing $\implies K_{\text{format}} = 0.65$.
3. **Runtime Bounds Killswitch ($K_{\text{duration}}$)**:
   - Optimal short-form duration $T \in [12\text{s}, 38\text{s}] \implies K_{\text{duration}} = 1.0$.
   - $T < 5\text{s}$ or $T > 60\text{s} \implies K_{\text{duration}} = 0.5$.

---

## 4. Gemini Omni / Gemini Video API Multimodal Extraction Specification

To extract these parameters deterministically from raw 4K `.mp4` video files in GCP Spark/Dataproc jobs, we utilize the **Gemini 2.0 Flash / 1.5 Pro Video Multimodal API** with strict `response_schema` enforcement.

### 4.1 Pydantic Schema Specification (`ViralGradingSchema`)

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class TransientEvent(BaseModel):
    timestamp_seconds: float = Field(..., description="Exact timestamp of the event in seconds")
    event_type: str = Field(..., description="Type of transient: 'audio_drop', 'laser_burst', 'pyro_blast', 'crowd_jump', 'vocal_pocket', 'camera_zoom'")
    intensity: float = Field(..., ge=0.0, le=1.0, description="Normalized intensity of the event (0.0 to 1.0)")
    description: str = Field(..., description="Concise descriptive detail of what occurred")

class HookAnalysis(BaseModel):
    hook_onset_latency_seconds: float = Field(..., description="Delay before first engaging audio/visual element")
    transient_count_first_3s: int = Field(..., description="Number of visual/audio pattern interrupts in first 3.0s")
    initial_visual_stimulus_score: float = Field(..., ge=0.0, le=100.0, description="Visual kinetic quality score of 0-3s")
    hrv_score: float = Field(..., ge=0.0, le=100.0, description="Computed 3-Second Hook Retention Velocity Score")

class DropPacingAnalysis(BaseModel):
    drop_detected: bool = Field(..., description="Whether an EDM bass drop was identified")
    drop_timestamp_seconds: Optional[float] = Field(None, description="Timestamp where the main drop hits")
    buildup_duration_seconds: Optional[float] = Field(None, description="Duration of build-up tension preceding drop")
    predrop_silence_duration_ms: Optional[float] = Field(None, description="Duration of vocal pocket / silence gap in milliseconds")
    drop_position_ratio: Optional[float] = Field(None, description="drop_timestamp / total_video_duration")
    dpaw_score: float = Field(..., ge=0.0, le=100.0, description="Computed Drop Pacing & Anticipation Window Score")

class AudioAcousticAnalysis(BaseModel):
    sub_bass_surge_ratio: float = Field(..., description="Ratio of low-end energy (30-90Hz) post-drop vs pre-drop")
    spectral_flux_delta: float = Field(..., description="Rate of spectral change at drop onset")
    loudness_jump_lufs_est: float = Field(..., description="Estimated perceptual loudness difference in LUFS")
    audio_clipping_detected: bool = Field(..., description="True if microphone distortion / blown-out audio is present")
    adr_sfd_score: float = Field(..., ge=0.0, le=100.0, description="Computed Audio Dynamic Range & Spectral Flux Score")

class CrowdDynamicsAnalysis(BaseModel):
    crowd_visible_percentage: float = Field(..., description="Percentage of frame area occupied by festival crowd")
    jump_synchronicity_coherence: float = Field(..., ge=0.0, le=1.0, description="Degree of unified vertical motion")
    energy_acceleration_factor: float = Field(..., description="Crowd motion kinetic energy ratio drop vs build")
    moshpit_or_intense_reaction: bool = Field(..., description="Presence of moshpits, rail riding, or frantic jumping")
    cke_mve_score: float = Field(..., ge=0.0, le=100.0, description="Computed Crowd Kinetic Energy Score")

class LightingProductionAnalysis(BaseModel):
    laser_co2_pyro_present: bool = Field(..., description="Presence of lasers, CO2 cryo cannons, flames, or pyrotechnics")
    strobe_frequency_hz: float = Field(..., description="Estimated strobe/flash frequency in Hertz")
    light_audio_sync_latency_ms: float = Field(..., description="Absolute timing offset between light burst and audio drop in ms")
    ltss_score: float = Field(..., ge=0.0, le=100.0, description="Computed Lighting Transition & Strobe Sync Score")

class EDMViralGradingReport(BaseModel):
    video_duration_seconds: float
    aspect_ratio: str = Field(..., description="e.g., '9:16', '16:9', '1:1'")
    key_transients: List[TransientEvent]
    hook_analysis: HookAnalysis
    drop_pacing_analysis: DropPacingAnalysis
    audio_analysis: AudioAcousticAnalysis
    crowd_analysis: CrowdDynamicsAnalysis
    lighting_analysis: LightingProductionAnalysis
    evpi_composite_score: float = Field(..., ge=0.0, le=100.0, description="Final weighted Trending Potential score (0-100)")
    trending_verdict: str = Field(..., description="'VIRAL_TIER_1', 'HIGH_POTENTIAL', 'MODERATE', 'LOW_REACH'")
    algorithmic_recommendation: str = Field(..., description="Specific editing instruction to improve short-form retention")
```

### 4.2 Gemini Omni System Prompt Specification

```text
You are an expert Short-Form Algorithmic Video Intelligence Engine specializing in EDM festival and club media evaluation.
Your task is to analyze the provided video and audio streams synchronously with microsecond precision and extract quantitative viral grading metrics according to the exact schema.

EVALUATION RULES:
1. Identify exact timestamps (in seconds) of hook onset, build-up start, pre-drop silence pocket, and the primary bass drop impact.
2. Measure vertical optical flow coherence and crowd jump synchronization.
3. Quantify audio spectral flux and sub-bass impact at drop point.
4. Assess visual production elements (lasers, CO2 cryo, pyro, strobes) and verify synchronization latency with the audio transients.
5. Compute the 5 sub-scores (0-100) and the composite EVPI score using the standardized formula:
   EVPI = (0.25 * HRV + 0.25 * DPAW + 0.20 * ADR_SFD + 0.15 * CKE_MVE + 0.15 * LTSS) * Killswitch_Modifiers.
```

---

## 5. BigQuery ML Autonomous Feedback Loop

### 5.1 BigQuery Schema Definition (`media_pipeline.video_grades`)

```sql
CREATE OR REPLACE TABLE `media_pipeline.video_grades` (
    video_id STRING NOT NULL,
    gcs_uri STRING NOT NULL,
    processed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    duration_seconds FLOAT64,
    aspect_ratio STRING,
    hrv_score FLOAT64,
    dpaw_score FLOAT64,
    adr_sfd_score FLOAT64,
    cke_mve_score FLOAT64,
    ltss_score FLOAT64,
    evpi_composite FLOAT64,
    drop_timestamp_seconds FLOAT64,
    buildup_duration_seconds FLOAT64,
    predrop_silence_ms FLOAT64,
    strobe_hz FLOAT64,
    trending_verdict STRING,
    -- Downstream Post-Publishing Telemetry (Sinked from YouTube Analytics / TikTok API)
    actual_vvsa_rate FLOAT64,          -- Viewed vs Swiped Away percentage (e.g. 0.82)
    actual_avg_percentage_viewed FLOAT64, -- e.g. 1.25 (125% retention)
    actual_share_count INT64,
    actual_viral_status INT64           -- 1 if viral (>100k views in 48h), else 0
);
```

### 5.2 BigQuery ML Model Training (`CREATE MODEL`)

To close the loop and optimize feature weights continuously as actual post-publishing analytics arrive:

```sql
-- 1. Boosted Tree Regressor for Predicting Actual Retention (APV)
CREATE OR REPLACE MODEL `media_pipeline.viral_retention_regressor`
OPTIONS(
    model_type='BOOSTED_TREE_REGRESSOR',
    input_label_cols=['actual_avg_percentage_viewed'],
    max_iterations=50,
    tree_method='HIST'
) AS
SELECT
    hrv_score,
    dpaw_score,
    adr_sfd_score,
    cke_mve_score,
    ltss_score,
    evpi_composite,
    duration_seconds,
    drop_timestamp_seconds,
    buildup_duration_seconds,
    predrop_silence_ms,
    strobe_hz,
    actual_avg_percentage_viewed
FROM
    `media_pipeline.video_grades`
WHERE
    actual_avg_percentage_viewed IS NOT NULL;

-- 2. K-Means Clustering to Categorize Video Style Archetypes
CREATE OR REPLACE MODEL `media_pipeline.video_archetype_clusters`
OPTIONS(
    model_type='KMEANS',
    num_clusters=4,
    standardize_features=TRUE
) AS
SELECT
    hrv_score,
    dpaw_score,
    adr_sfd_score,
    cke_mve_score,
    ltss_score
FROM
    `media_pipeline.video_grades`;
```

---

## 6. Synthesis & Downstream Implementation Plan

| Step | Downstream Module | Target Artifact / Script | Explorer Survey Specification Deliverable |
| :--- | :--- | :--- | :--- |
| **1** | Architecture Rule Artifact | `VIRAL_FORMULA.md` | Formalized 5 parameters, scoring bounds, formulas, weights. |
| **2** | PySpark Video Processor | `spark_grading_job.py` | Pydantic extraction schema, Gemini API invocation wrapper, EVPI math parser. |
| **3** | BigQuery ML Sink | `bigquery_ml_loop.sql` | Table DDL, feature column definitions, BQML training statements. |
