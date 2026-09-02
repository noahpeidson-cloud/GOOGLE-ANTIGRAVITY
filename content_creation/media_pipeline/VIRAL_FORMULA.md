# EDM Short-Form Viral Formula Specification (EVPI-5)
**Authoritative Architectural Specification & Mathematical Grading Model for Short-Form Media**
*Target Platforms: YouTube Shorts, TikTok, Instagram Reels*  
*Target Media: 4K/HDR Uncompressed EDM Festival & Club Video Footage*  
*Version: 1.0.0-PROD*

---

## 1. Executive Summary & Algorithmic Foundations

In algorithmic short-form video distribution (YouTube Shorts, TikTok, Instagram Reels), video discovery is governed entirely by viewer retention, completion rates, and immediate engagement velocity rather than static click-through rates.

```
                  ┌─────────────────────────────────────────┐
                  │ 1. EXPLORE PHASE (Seed: 200-1,000 Views) │
                  │ Primary Gate: VVSA >= 75% in First 3.0s │
                  └────────────────────┬────────────────────┘
                                       │ Pass
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │ 2. EXPLOIT PHASE (1,000-50,000 Views)   │
                  │ Primary Gate: APV >= 100% (Rewatch loop)│
                  └────────────────────┬────────────────────┘
                                       │ Pass
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │ 3. VIRAL SCALE (50,000 - 10M+ Views)    │
                  │ Primary Gate: EVPI >= 85.0 + High Share │
                  └─────────────────────────────────────────┘
```

### 1.1 Algorithmic Funnel Thresholds
1. **Viewed vs. Swiped Away (VVSA)**:
   - Evaluated over the first $[0.0\text{s}, 3.0\text{s}]$ window.
   - **$\text{VVSA} \ge 75\%$**: Instant promotion to broad algorithmic distribution pools.
   - **$50\% \le \text{VVSA} < 75\%$**: Neutral retention; constrained distribution to niche affinity groups.
   - **$\text{VVSA} < 50\%$**: Terminal penalty; algorithmic suppression and dead-end impressions.
2. **Average Percentage Viewed (APV)**:
   - For short clips ($T \le 30\text{s}$), viral breakout requires **$\text{APV} \ge 110\%\text{--}130\%$**, indicating users watch the video through completion and loop at least 1.1 to 1.3 times.
   - For medium clips ($30\text{s} < T \le 60\text{s}$), **$\text{APV} \ge 85\%$** with high completion rate ($>70\%$).
3. **Loop Retention Multiplier ($M_{\text{loop}}$)**:
   - Defined as $M_{\text{loop}} = \frac{\text{Total Watch Time}}{\text{Duration } T \times \text{Unique Viewers}}$.
   - High $M_{\text{loop}}$ signals seamless audiovisual continuity between the final frame and opening frame.

### 1.2 The EDM Viral Physics Hypothesis
EDM live festival and club footage operates on unique psychoacoustic and visual stimulation dynamics:
- **Tension & Anticipation**: The cognitive expectation of a bass drop triggers dopamine release.
- **Sensory Overload Release**: The instantaneous explosion of sub-bass acoustic energy coupled with synchronized stage production (lasers, pyro, CO2 cryo jets, strobes).
- **Physical Mirroring (Crowd Contagion)**: Viewers subconsciously mirror the kinetic energy of an arena or club crowd jumping in rhythmic unison.

The **EDM Viral Potential Index (EVPI)** mathematically models and quantifies these dynamics across 5 distinct, orthogonal parameters.

---

## 2. The 5 Core Mathematical Viral Grading Parameters

| # | Parameter | Symbol | Weight ($w_i$) | Primary Algorithmic Objective |
|---|---|---|---|---|
| **P1** | **3-Second Hook Retention Velocity** | $S_{\text{HRV}}$ | **0.25** | Maximizes VVSA ($\ge 75\%$), eliminates early swipe-away. |
| **P2** | **Drop Pacing & Anticipation Window** | $S_{\text{DPAW}}$ | **0.25** | Optimizes APV and tension-release timing within short-form bounds. |
| **P3** | **Audio Dynamic Range & Spectral Flux Delta** | $S_{\text{ADR-SFD}}$ | **0.20** | Ensures visceral acoustic contrast and sub-bass impact. |
| **P4** | **Crowd Kinetic Energy & Motion Vector Entropy** | $S_{\text{CKE-MVE}}$ | **0.15** | Drives psychological contagion through synchronized crowd motion. |
| **P5** | **Lighting Transition & Strobe Peak Synchronicity** | $S_{\text{LTSS}}$ | **0.15** | Maximizes visual dopamine via exact audio-visual transient alignment. |

---

### Parameter 1: 3-Second Hook Retention Velocity (HRV)

#### 1. Domain Rationale
The first 3 seconds are the single point of failure in short-form media. A sluggish opening (dark screen, silence, unfocused ground shots, or slow fade-ins) causes immediate swipe-away. An elite hook must deliver:
- Audio presence within $\le 0.1\text{s}$ of playback.
- High visual kinetic density (camera motion or on-screen action).
- Multiple audiovisual pattern interrupts (jump cuts, zooms, on-screen text, riser sweeps).

#### 2. Continuous Mathematical Formulation
Let $t \in [0, 3.0]$ seconds be the hook evaluation window.
- **Normalized RMS Audio Amplitude Envelope**: $A(t) \in [0, 1]$.
- **Mean Optical Flow Magnitude Across Frame Pixels**:
  $$V_{\text{opt}}(t) = \frac{1}{W \cdot H} \sum_{x=1}^W \sum_{y=1}^H \sqrt{u(x,y,t)^2 + v(x,y,t)^2}$$
  where $(u, v)$ are horizontal and vertical pixel motion vectors, normalized by $V_{\text{norm}} = 25.0\,\text{px/frame}$.
- **Transient Pattern Interrupt Count**: $N_{\text{transients}} \in \mathbb{N}$ (discrete bass hits, camera zooms, scene cuts, text pop-ins in $[0, 3.0]\text{s}$).
- **Initial Audiovisual Onset Latency**: $t_{\text{onset}} \in [0, 3.0]\text{s}$ (timestamp of first perceptual stimulus).

Hook Kinetic Density ($D_{\text{hook}}$):
$$D_{\text{hook}} = \int_{0}^{3.0} \left( 0.55 \cdot A(t) + 0.45 \cdot \min\left(1.0, \frac{V_{\text{opt}}(t)}{V_{\text{norm}}}\right) \right) dt$$

Raw HRV Score ($\text{HRV}_{\text{raw}} \in [0, 1.0]$):
$$\text{HRV}_{\text{raw}} = 0.40 \cdot \left(\frac{D_{\text{hook}}}{3.0}\right) + 0.35 \cdot \min\left(1.0, \frac{N_{\text{transients}}}{3.0}\right) + 0.25 \cdot \max\left(0.0, 1.0 - \frac{t_{\text{onset}}}{0.5}\right)$$

#### 3. 0–100 Scaled Scoring Function
$$S_{\text{HRV}} = 100.0 \times \text{Clamp}_{[0.0, 1.0]}(\text{HRV}_{\text{raw}})$$

#### 4. Benchmark Thresholds
- **90–100 (Viral Master)**: Immediate audio onset ($t_{\text{onset}} < 0.05\text{s}$), $\ge 3$ rapid pattern interrupts, high kinetic motion, instant curiosity hook.
- **70–89 (Strong Engagement)**: Audio hits within $0.3\text{s}$, steady kinetic movement, $\ge 2$ pattern interrupts.
- **40–69 (Average)**: Sluggish start ($t_{\text{onset}} \approx 0.5\text{--}1.0\text{s}$), low visual motion, predictable pan.
- **0–39 (Instant Swipe)**: Dead air ($>1.0\text{s}$ silence/black frame), shaky floor shot, no clear focal point.

---

### Parameter 2: Drop Pacing & Anticipation Window (DPAW)

#### 1. Domain Rationale
Full EDM track arrangements feature 30–60 second build-ups, which produce near 100% viewer churn on short-form platforms. Viral short-form clips require condensed micro-builds (3.5s to 6.5s), a clean pre-drop vocal/silence pocket (150ms to 450ms), and a drop placement centered at 45% to 60% of total video duration ($T$), leaving ample time for post-drop payoff and loop transition.

#### 2. Continuous Mathematical Formulation
Let $T$ be the total video duration in seconds ($10\text{s} \le T \le 60\text{s}$).
- $t_{\text{drop}}$: Exact timestamp of the primary bass drop impact.
- $W_{\text{build}} = t_{\text{drop}} - t_{\text{build\_start}}$: Measured build-up tension window in seconds.
- $\Delta t_{\text{pocket}}$: Duration of pre-drop micro-pause / vocal sample silence gap in seconds.

**Drop Position Factor ($P_{\text{pos}}$)**: Modeled as a Gaussian centered at optimal position ratio $\mu_{\text{pos}} = 0.52, \sigma_{\text{pos}} = 0.12$:
$$P_{\text{pos}} = \exp\left( -\frac{\left(\frac{t_{\text{drop}}}{T} - 0.52\right)^2}{2 \cdot (0.12)^2} \right)$$

**Build-up Duration Factor ($B_{\text{window}}$)**: Modeled as a Gaussian centered at optimal build duration $\mu_{\text{build}} = 4.5\text{s}, \sigma_{\text{build}} = 1.5\text{s}$:
$$B_{\text{window}} = \exp\left( -\frac{(W_{\text{build}} - 4.5)^2}{2 \cdot (1.5)^2} \right)$$

**Pre-Drop Pocket Factor ($Q_{\text{pocket}}$)**:
$$Q_{\text{pocket}} = \begin{cases} 
1.0 & \text{if } 0.15 \le \Delta t_{\text{pocket}} \le 0.45 \\
0.5 + 0.5 \cdot \left(\frac{\Delta t_{\text{pocket}}}{0.15}\right) & \text{if } 0.0 \le \Delta t_{\text{pocket}} < 0.15 \\
\max\left(0.0, 1.0 - \frac{\Delta t_{\text{pocket}} - 0.45}{0.50}\right) & \text{if } \Delta t_{\text{pocket}} > 0.45 
\end{cases}$$

#### 3. 0–100 Scaled Scoring Function
$$S_{\text{DPAW}} = 100.0 \times \left( 0.45 \cdot P_{\text{pos}} + 0.35 \cdot B_{\text{window}} + 0.20 \cdot Q_{\text{pocket}} \right)$$

*If no drop is present in the video, $S_{\text{DPAW}} = 25.0$ (constant groove clip baseline).*

#### 4. Benchmark Thresholds
- **90–100 (Optimal Tension Curve)**: Drop occurs at $48\%\text{--}55\%$ of duration, build is $4.0\text{--}5.5\text{s}$, crisp $250\text{ms}$ pre-drop silence pocket.
- **70–89 (Solid Pacing)**: Drop occurs between $40\%\text{--}65\%$, build duration is $3.0\text{--}7.5\text{s}$.
- **40–69 (Suboptimal Timing)**: Drop occurs too early ($<2.5\text{s}$, no anticipation) or too late ($>75\%$ of clip, high drop-off before payoff).
- **0–39 (Unstructured)**: Endless build-up without drop, or video cuts off before drop lands.

---

### Parameter 3: Audio Dynamic Range & Spectral Flux Delta (ADR-SFD)

#### 1. Domain Rationale
A viral EDM drop must deliver immediate acoustic shock value. The acoustic transition between build and drop requires a massive surge in **sub-bass energy ($30\text{--}90\,\text{Hz}$)**, high-frequency transient brightness (cymbals, supersaws, white noise sweeps), and a perceptual loudness increase of $+4\text{ to }+8\,\text{LUFS}$ without harsh digital clipping.

#### 2. Continuous Mathematical Formulation
Let $X(t, f)$ denote the Short-Time Fourier Transform (STFT) magnitude of the audio signal at time $t$ and frequency bin $f$.
- **Spectral Flux ($\text{SF}(t)$)**:
  $$\text{SF}(t) = \sum_{f} \mathcal{H}\left( |X(t, f)| - |X(t - \Delta t, f)| \right)$$
  where $\mathcal{H}(x) = \max(0, x)$ is half-wave rectification.
- **Sub-Bass Energy ($E_{\text{sub}}(t)$)**:
  $$E_{\text{sub}}(t) = \int_{30\,\text{Hz}}^{90\,\text{Hz}} |X(t, f)|^2 df$$
- **Sub-Bass Surge Ratio ($R_{\text{sub}}$)**:
  $$R_{\text{sub}} = \frac{\frac{1}{\Delta T_{\text{post}}} \int_{t_{\text{drop}}}^{t_{\text{drop}} + 2.0} E_{\text{sub}}(t)\,dt}{\frac{1}{\Delta T_{\text{pre}}} \int_{t_{\text{drop}} - 2.0}^{t_{\text{drop}}} E_{\text{sub}}(t)\,dt + \epsilon}$$
- **Integrated Loudness Jump ($\Delta \text{LUFS}$)**:
  $$\Delta \text{LUFS} = \text{LUFS}(t_{\text{drop}} \to t_{\text{drop}}+3.0) - \text{LUFS}(t_{\text{drop}}-3.0 \to t_{\text{drop}})$$

**Normalized Components**:
$$\text{SFD}_{\text{norm}} = \text{Clamp}_{[0.0, 1.0]}\left( \frac{\max_{t \in [t_{\text{drop}}, t_{\text{drop}}+0.5]} \text{SF}(t) - \text{mean}_{t \in \text{build}} \text{SF}(t)}{2.5 \cdot \sigma_{\text{SF}} + \epsilon} \right)$$
$$R_{\text{norm}} = \text{Clamp}_{[0.0, 1.0]}\left( \frac{\log_{10}(R_{\text{sub}} + 1.0)}{\log_{10}(8.0)} \right)$$
$$L_{\text{norm}} = \text{Clamp}_{[0.0, 1.0]}\left( \frac{\Delta \text{LUFS}}{6.0} \right)$$

#### 3. 0–100 Scaled Scoring Function
$$S_{\text{ADR-SFD}} = 100.0 \times \left( 0.40 \cdot R_{\text{norm}} + 0.35 \cdot \text{SFD}_{\text{norm}} + 0.25 \cdot L_{\text{norm}} \right)$$

#### 4. Benchmark Thresholds
- **90–100 (Acoustic Perfection)**: Sub-bass surge $>6\times$, crisp spectral transient spike, $+5\text{ to }+7\,\text{LUFS}$ punch, zero clipping.
- **70–89 (High Impact)**: Solid bass kick, clean high-end transients, good dynamic punch.
- **40–69 (Flat Audio)**: Moderate dynamics, weak sub-bass, or aggressive phone mic limiter pumping.
- **0–39 (Distorted / Lifeless)**: Extreme digital peaking/clipping distortion ($>30\%$ duration) or tinny, bass-free audio.

---

### Parameter 4: Crowd Kinetic Energy & Motion Vector Entropy (CKE-MVE)

#### 1. Domain Rationale
Festival virality is driven by emotional and physiological mirror neurons. Videos capturing thousands of individuals moving in synchronized vertical harmony (jumping on beat, rail-riding, mosh pit eruptions) evoke high arousal and drive shares/comments.

#### 2. Continuous Mathematical Formulation
Let $\vec{v}(x,y,t) = (u, v)$ represent dense optical flow velocity vectors for all pixels within the detected audience region $\Omega_{\text{crowd}}$.
- **Audience Region Area Fraction**: $\alpha_{\text{crowd}} = \frac{|\Omega_{\text{crowd}}|}{W \cdot H}$.
- **Vertical Jump Coherence ($C_{\text{jump}}(t)$)**:
  $$C_{\text{jump}}(t) = \frac{\left| \sum_{(x,y) \in \Omega_{\text{crowd}}} v(x,y,t) \right|}{\sum_{(x,y) \in \Omega_{\text{crowd}}} |v(x,y,t)| + \epsilon}$$
  ($C_{\text{jump}} \to 1.0$ when the entire crowd moves strictly up/down in unison; $C_{\text{jump}} \to 0$ for chaotic horizontal jitter).
- **Kinetic Energy Burst Multiplier ($\Delta E_{\text{kinetic}}$)**:
  $$E_k(t) = \frac{1}{|\Omega_{\text{crowd}}|} \sum_{(x,y) \in \Omega_{\text{crowd}}} \left( u(x,y,t)^2 + v(x,y,t)^2 \right)$$
  $$\Delta E_{\text{kinetic}} = \frac{\text{mean}_{t \in [t_{\text{drop}}, t_{\text{drop}}+3.0]} E_k(t)}{\text{mean}_{t \in [t_{\text{drop}}-3.0, t_{\text{drop}}]} E_k(t) + \epsilon}$$
- **BPM Motion Phase Coupling ($\Phi_{\text{BPM}}$)**:
  Normalized cross-correlation between vertical crowd velocity oscillation $v_y(t)$ and the musical beat tempo ($f_{\text{BPM}} \in [120, 175]\,\text{BPM}$):
  $$\Phi_{\text{BPM}} = \max_{\tau} \frac{\int_{t_{\text{drop}}}^{t_{\text{drop}}+4.0} v_y(t) \cdot \cos(2\pi f_{\text{BPM}} (t + \tau))\,dt}{\|v_y\|_2 \cdot \|\cos\|_2 + \epsilon}$$

#### 3. 0–100 Scaled Scoring Function
$$S_{\text{CKE-MVE}} = 100.0 \times \left( 0.40 \cdot \min\left(1.0, \frac{\Delta E_{\text{kinetic}}}{4.0}\right) + 0.35 \cdot C_{\text{jump}}(t_{\text{drop}}) + 0.25 \cdot \max(0.0, \Phi_{\text{BPM}}) \right)$$

*If crowd is not visible ($\alpha_{\text{crowd}} < 0.05$, e.g. DJ close-up), fallback to performer kinetic intensity.*

#### 4. Benchmark Thresholds
- **90–100 (Hypnotic Synchronization)**: Unified stadium-wide jumping ($C_{\text{jump}} > 0.85$), massive energy explosion at drop ($>4\times$), perfect BPM lock.
- **70–89 (High Crowd Energy)**: Clear audience movement, active hand pumping, visible energy jump on drop.
- **40–69 (Passive Audience)**: Low motion, people standing still holding phones, low coherence.
- **0–39 (Static / Disconnected)**: Empty crowd, stationary silhouettes, zero kinetic response to drop.

---

### Parameter 5: Lighting Transition & Strobe Peak Synchronicity (LTSS)

#### 1. Domain Rationale
High-end stage production—moving-head beams, laser arrays, CO2 cryo bursts, flame pyro cannons, and high-frequency strobes—creates visual dopamine. The visual transients must hit within $\pm 33\text{ms}$ ($\pm 1$ video frame at 30 fps) of the musical downbeat to achieve peak perceptual impact.

#### 2. Continuous Mathematical Formulation
Let $Y(x,y,t)$ be the ITU-R BT.709 frame luminance channel:
- **Mean Frame Luminance**: $L(t) = \frac{1}{W \cdot H} \sum_{x,y} Y(x,y,t)$.
- **Strobe Modulation Frequency ($f_{\text{strobe}}$)**: Dominant spectral peak of $\left|\frac{dL(t)}{dt}\right|$ in the strobe band $[6.0\,\text{Hz}, 25.0\,\text{Hz}]$.
- **Transient Alignment Offset ($\tau_{\text{sync}}$)**:
  $$\tau_{\text{sync}} = |t_{\text{visual\_burst}} - t_{\text{audio\_transient}}| \quad (\text{in seconds})$$
- **Production Element Multiplier ($F_{\text{prod}}$)**:
  $$F_{\text{prod}} = \min\left(1.0, 0.30 \cdot \mathbb{I}_{\text{lasers}} + 0.30 \cdot \mathbb{I}_{\text{pyro}} + 0.20 \cdot \mathbb{I}_{\text{CO2\_cryo}} + 0.20 \cdot \mathbb{I}_{\text{LED\_visuals}}\right)$$
  where $\mathbb{I}_{\text{feature}} \in \{0, 1\}$ is an indicator variable for detected production elements.

**Synchronicity Alignment Score ($\text{Sync}_{\text{score}}$)**:
$$\text{Sync}_{\text{score}} = \exp\left( -\frac{\tau_{\text{sync}}^2}{2 \cdot (0.033)^2} \right)$$

#### 3. 0–100 Scaled Scoring Function
$$S_{\text{LTSS}} = 100.0 \times \left( 0.40 \cdot \text{Sync}_{\text{score}} + 0.35 \cdot F_{\text{prod}} + 0.25 \cdot \text{Clamp}_{[0.0, 1.0]}\left(\frac{f_{\text{strobe}} - 4.0}{12.0}\right) \right)$$

#### 4. Benchmark Thresholds
- **90–100 (Arena Grade Spectacle)**: Frame-perfect ($\le 33\text{ms}$) laser/pyro/cryo burst on drop, intense strobe modulation ($12\text{--}18\,\text{Hz}$).
- **70–89 (Dynamic Club Production)**: Well-timed lighting shifts ($\le 100\text{ms}$), active beam movement, visible CO2 or strobes.
- **40–69 (Dim / Out-of-Sync)**: Lighting changes delayed by $>200\text{ms}$, basic static wash lights.
- **0–39 (Zero Production)**: Flat daylight, completely dark scene, or zero lighting variation on drop.

---

## 3. Composite EDM Viral Potential Index (EVPI)

### 3.1 Composite Formula
The **EDM Viral Potential Index (EVPI)** combines the 5 parameter scores using baseline regression weights, multiplied by non-linear algorithmic killswitches:

$$\text{EVPI}_{\text{raw}} = \sum_{i=1}^5 w_i \cdot S_i = 0.25 \cdot S_{\text{HRV}} + 0.25 \cdot S_{\text{DPAW}} + 0.20 \cdot S_{\text{ADR-SFD}} + 0.15 \cdot S_{\text{CKE-MVE}} + 0.15 \cdot S_{\text{LTSS}}$$

$$\text{EVPI} = \text{Clamp}_{[0.0, 100.0]}\left( \text{EVPI}_{\text{raw}} \times K_{\text{audio}} \times K_{\text{format}} \times K_{\text{duration}} \right)$$

```
┌─────────┐      ┌──────────┐      ┌─────────────┐      ┌─────────────┐      ┌──────────┐
│  S_HRV  │      │  S_DPAW  │      │  S_ADR-SFD  │      │  S_CKE-MVE  │      │  S_LTSS  │
│ (w=0.25)│      │ (w=0.25) │      │  (w=0.20)   │      │  (w=0.15)   │      │ (w=0.15) │
└────┬────┘      └────┬─────┘      └──────┬──────┘      └──────┬──────┘      └────┬─────┘
     │                │                   │                    │                  │
     └────────────────┼───────────────────┼────────────────────┼──────────────────┘
                      │                   │                    │
                      ▼                   ▼                    ▼
                   ┌──────────────────────────────────────────────┐
                   │    Weighted Linear Combination (EVPI_raw)    │
                   └──────────────────────┬───────────────────────┘
                                          │
                                          ▼
                   ┌──────────────────────────────────────────────┐
                   │  Non-Linear Killswitches (K_aud, K_fmt, K_dur)│
                   └──────────────────────┬───────────────────────┘
                                          │
                                          ▼
                   ┌──────────────────────────────────────────────┐
                   │        Final EVPI Composite (0.0 - 100.0)    │
                   └──────────────────────────────────────────────┘
```

### 3.2 Non-Linear Killswitch Multipliers ($K_k \in [0.0, 1.0]$)

1. **Audio Integrity Killswitch ($K_{\text{audio}}$)**:
   - Evaluates audio track viability:
     $$K_{\text{audio}} = \begin{cases}
     1.0 & \text{if audio is clean and unclipped} \\
     0.6 & \text{if moderate clipping is detected in } <20\% \text{ of runtime} \\
     0.1 & \text{if audio is muted, silent, or severely clipped } >30\% \text{ of runtime}
     \end{cases}$$
2. **Aspect Ratio & Framing Killswitch ($K_{\text{format}}$)**:
   - Short-form recommendation feeds severely downrank horizontal letterboxing:
     $$K_{\text{format}} = \begin{cases}
     1.0 & \text{if aspect ratio is Vertical 9:16 } (1080\times 1920 \text{ or } 2160\times 3840) \\
     0.85 & \text{if aspect ratio is Square 1:1 } (1080\times 1080) \\
     0.50 & \text{if aspect ratio is Horizontal 16:9 with letterboxing}
     \end{cases}$$
3. **Runtime Bounds Killswitch ($K_{\text{duration}}$)**:
   - Optimal viral retention window is $12\text{s} \le T \le 38\text{s}$:
     $$K_{\text{duration}} = \begin{cases}
     1.0 & \text{if } 12.0 \le T \le 38.0\,\text{seconds} \\
     0.85 & \text{if } 8.0 \le T < 12.0 \text{ or } 38.0 < T \le 60.0\,\text{seconds} \\
     0.40 & \text{if } T < 8.0 \text{ or } T > 60.0\,\text{seconds}
     \end{cases}$$

### 3.3 Viral Verdict Classification Matrix
| EVPI Range | Trending Verdict | Expected Distribution Tier | Algorithmic Action |
|---|---|---|---|
| **$\ge 85.0$** | `VIRAL_TIER_1` | Tier 1 (100k – 10M+ views) | Immediate automated publishing & cross-platform syndication. |
| **$70.0\text{--}84.9$** | `HIGH_POTENTIAL` | Tier 2 (10k – 100k views) | Ready for publishing; optional micro-trimming on hook. |
| **$50.0\text{--}69.9$** | `MODERATE` | Tier 3 (1k – 10k views) | Requires re-editing (tighten build-up, add text anchor). |
| **$< 50.0$** | `LOW_REACH` | Tier 4 (< 1k views) | Reject / Archive; do not publish to primary feeds. |

---

## 4. Pydantic Structured Extraction Schema (`viral_schema.py`)

This schema forms the strict data contract between Gemini Omni/Video API, PySpark processing nodes, and BigQuery ML storage.

```python
"""
Strict Pydantic V2 Models for Multimodal EDM Video Viral Grading.
Module: media_pipeline.grading.viral_schema
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class TransientEvent(BaseModel):
    timestamp_seconds: float = Field(
        ..., ge=0.0, description="Exact timestamp of the detected event in seconds."
    )
    event_type: Literal[
        "audio_drop", "buildup_start", "predrop_pocket", "laser_burst",
        "pyro_blast", "co2_cryo", "crowd_jump", "camera_zoom", "scene_cut"
    ] = Field(..., description="Categorical classification of the transient event.")
    intensity: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized physical intensity (0.0 to 1.0)."
    )
    description: str = Field(
        ..., max_length=256, description="Concise technical description of event."
    )


class HookAnalysis(BaseModel):
    hook_onset_latency_seconds: float = Field(
        ..., ge=0.0, description="Delay before first engaging audio/visual stimulus."
    )
    transient_count_first_3s: int = Field(
        ..., ge=0, description="Number of visual/audio pattern interrupts in [0, 3.0]s."
    )
    initial_visual_stimulus_score: float = Field(
        ..., ge=0.0, le=100.0, description="Visual kinetic quality score in [0, 3.0]s."
    )
    hrv_score: float = Field(
        ..., ge=0.0, le=100.0, description="Computed 3-Second Hook Retention Velocity Score."
    )


class DropPacingAnalysis(BaseModel):
    drop_detected: bool = Field(
        ..., description="Whether an EDM bass drop was identified."
    )
    drop_timestamp_seconds: Optional[float] = Field(
        None, ge=0.0, description="Timestamp where the main bass drop hits."
    )
    buildup_duration_seconds: Optional[float] = Field(
        None, ge=0.0, description="Duration of build-up tension preceding drop."
    )
    predrop_silence_duration_ms: Optional[float] = Field(
        None, ge=0.0, description="Duration of vocal pocket / silence gap in ms."
    )
    drop_position_ratio: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="drop_timestamp / total_video_duration."
    )
    dpaw_score: float = Field(
        ..., ge=0.0, le=100.0, description="Computed Drop Pacing & Anticipation Window Score."
    )


class AudioAcousticAnalysis(BaseModel):
    sub_bass_surge_ratio: float = Field(
        ..., ge=0.0, description="Ratio of low-end energy (30-90Hz) post-drop vs pre-drop."
    )
    spectral_flux_delta: float = Field(
        ..., ge=0.0, description="Rate of spectral change at drop onset."
    )
    loudness_jump_lufs_est: float = Field(
        ..., description="Estimated perceptual loudness difference in LUFS."
    )
    audio_clipping_detected: bool = Field(
        ..., description="True if severe microphone distortion or clipping is present."
    )
    adr_sfd_score: float = Field(
        ..., ge=0.0, le=100.0, description="Computed Audio Dynamic Range & Spectral Flux Score."
    )


class CrowdDynamicsAnalysis(BaseModel):
    crowd_visible_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Percentage of frame area occupied by crowd."
    )
    jump_synchronicity_coherence: float = Field(
        ..., ge=0.0, le=1.0, description="Unified vertical optical flow coherence (0.0 to 1.0)."
    )
    energy_acceleration_factor: float = Field(
        ..., ge=0.0, description="Crowd kinetic energy multiplier post-drop vs pre-drop."
    )
    moshpit_or_intense_reaction: bool = Field(
        ..., description="Presence of moshpits, rail riding, or frantic jumping."
    )
    cke_mve_score: float = Field(
        ..., ge=0.0, le=100.0, description="Computed Crowd Kinetic Energy & Motion Entropy Score."
    )


class LightingProductionAnalysis(BaseModel):
    laser_co2_pyro_present: bool = Field(
        ..., description="Presence of lasers, CO2 cryo cannons, flame pyro, or stage FX."
    )
    strobe_frequency_hz: float = Field(
        ..., ge=0.0, le=50.0, description="Estimated strobe/flash modulation frequency in Hz."
    )
    light_audio_sync_latency_ms: float = Field(
        ..., ge=0.0, description="Absolute offset between light burst and audio drop in ms."
    )
    ltss_score: float = Field(
        ..., ge=0.0, le=100.0, description="Computed Lighting Transition & Strobe Sync Score."
    )


class EDMViralGradingReport(BaseModel):
    video_id: str = Field(..., description="Unique alphanumeric identifier of the video.")
    gcs_uri: str = Field(..., description="Cloud Storage URI (gs://...) of raw video.")
    video_duration_seconds: float = Field(..., ge=1.0, le=300.0)
    aspect_ratio: str = Field(..., pattern=r"^\d+:\d+$", description="Aspect ratio string, e.g. '9:16'.")
    key_transients: List[TransientEvent] = Field(default_factory=list)
    hook_analysis: HookAnalysis
    drop_pacing_analysis: DropPacingAnalysis
    audio_analysis: AudioAcousticAnalysis
    crowd_analysis: CrowdDynamicsAnalysis
    lighting_analysis: LightingProductionAnalysis
    evpi_composite_score: float = Field(
        ..., ge=0.0, le=100.0, description="Final weighted Trending Potential score."
    )
    trending_verdict: Literal["VIRAL_TIER_1", "HIGH_POTENTIAL", "MODERATE", "LOW_REACH"]
    algorithmic_recommendation: str = Field(
        ..., max_length=512, description="Actionable editing advice for retention optimization."
    )

    @field_validator("evpi_composite_score")
    @classmethod
    def validate_evpi(cls, v: float) -> float:
        return round(v, 2)
```

---

## 5. Gemini Omni / Video Multimodal Prompt Specification

When dispatching 4K video clips to the Gemini Multimodal API via the `google-genai` SDK, the following system prompt and generation parameters must be utilized.

### 5.1 System Prompt
```text
You are the Autonomous Algorithmic Video Intelligence Engine for Google Antigravity, specializing in short-form EDM festival and club video optimization.

Your objective is to analyze the synchronous video and audio streams with microsecond precision and extract quantitative metrics matching the EDMViralGradingReport schema.

ANALYSIS DIRECTIVES:
1. TEMPORAL ACCURACY:
   - Identify the exact millisecond timestamps of:
     * Hook visual/audio onset latency.
     * Build-up initiation timestamp.
     * Pre-drop silence/vocal pocket duration (in ms).
     * Bass drop impact timestamp.
2. DYNAMIC SCORING (0.0 to 100.0):
   - HRV Score: Evaluate audio presence and kinetic interrupts in [0.0s, 3.0s].
   - DPAW Score: Evaluate drop placement relative to total duration and build-up length.
   - ADR-SFD Score: Evaluate sub-bass surge (30-90Hz) and dynamic loudness delta.
   - CKE-MVE Score: Quantify crowd vertical jump synchronicity and post-drop energy surge.
   - LTSS Score: Quantify laser/pyro/CO2 presence and transient synchronization alignment.
3. COMPOSITE EVPI EVALUATION:
   - Calculate EVPI_raw = 0.25*HRV + 0.25*DPAW + 0.20*ADR_SFD + 0.15*CKE_MVE + 0.15*LTSS.
   - Apply killswitch multipliers for audio clipping (0.1 if ruined), aspect ratio (0.5 if horizontal), and runtime bounds.
   - Assign verdict: VIRAL_TIER_1 (>=85), HIGH_POTENTIAL (70-84.9), MODERATE (50-69.9), LOW_REACH (<50).

Output must strictly conform to the EDMViralGradingReport JSON schema.
```

### 5.2 Python API Invocation Contract
```python
from google import genai
from google.genai import types
from media_pipeline.grading.viral_schema import EDMViralGradingReport

def grade_video_with_gemini(client: genai.Client, video_file_uri: str) -> EDMViralGradingReport:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_uri(file_uri=video_file_uri, mime_type="video/mp4"),
            "Analyze this EDM video footage and generate the complete EDMViralGradingReport."
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EDMViralGradingReport,
            temperature=0.1,
            max_output_tokens=2048,
        )
    )
    return EDMViralGradingReport.model_validate_json(response.text)
```

---

## 6. BigQuery Relational Schema & BQML Continuous Optimization Loop

### 6.1 Relational Storage Schema DDL (`bqml/schema.sql`)

```sql
-- Main Table: Stores PySpark Video Grading Extractions & Post-Publishing Performance Telemetry
CREATE OR REPLACE TABLE `media_pipeline.video_grades` (
    video_id STRING NOT NULL,
    gcs_uri STRING NOT NULL,
    processed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    duration_seconds FLOAT64 NOT NULL,
    aspect_ratio STRING NOT NULL,
    
    -- 5 Core Parameter Scores (0.0 to 100.0)
    hrv_score FLOAT64 NOT NULL,
    dpaw_score FLOAT64 NOT NULL,
    adr_sfd_score FLOAT64 NOT NULL,
    cke_mve_score FLOAT64 NOT NULL,
    ltss_score FLOAT64 NOT NULL,
    
    -- Composite Score and Model Classification
    evpi_composite FLOAT64 NOT NULL,
    trending_verdict STRING NOT NULL,
    
    -- Temporal Granular Features
    hook_onset_latency_seconds FLOAT64,
    drop_timestamp_seconds FLOAT64,
    buildup_duration_seconds FLOAT64,
    predrop_silence_ms FLOAT64,
    strobe_hz FLOAT64,
    
    -- Downstream Post-Publishing Telemetry (Sinked from YouTube / TikTok Analytics)
    actual_vvsa_rate FLOAT64,             -- Viewed vs Swiped Away percentage (e.g. 0.84)
    actual_avg_percentage_viewed FLOAT64,    -- Average Percentage Viewed (e.g. 1.28)
    actual_share_count INT64,             -- Total shares
    actual_completion_rate FLOAT64,        -- Fraction of viewers watching 100%
    actual_viral_status INT64             -- 1 if viral (>=100k views in 48h), else 0
);

-- Model Weights Table: Stores Active Dynamic Regression Weights
CREATE OR REPLACE TABLE `media_pipeline.model_parameter_weights` (
    version_id STRING NOT NULL,
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    weight_hrv FLOAT64 NOT NULL,
    weight_dpaw FLOAT64 NOT NULL,
    weight_adr_sfd FLOAT64 NOT NULL,
    weight_cke_mve FLOAT64 NOT NULL,
    weight_ltss FLOAT64 NOT NULL,
    model_r2_score FLOAT64 NOT NULL,
    is_active BOOLEAN NOT NULL
);
```

### 6.2 BigQuery ML Models DDL (`bqml/models.sql`)

```sql
-- ============================================================================
-- 1. Linear Regression Model for Parameter Weight Extraction (ML.WEIGHTS)
-- ============================================================================
CREATE OR REPLACE MODEL `media_pipeline.viral_weight_regressor`
OPTIONS(
    model_type='LINEAR_REG',
    input_label_cols=['actual_avg_percentage_viewed'],
    l1_reg=0.01,
    l2_reg=0.01,
    optimize_strategy='AUTO_STRATEGY'
) AS
SELECT
    hrv_score,
    dpaw_score,
    adr_sfd_score,
    cke_mve_score,
    ltss_score,
    actual_avg_percentage_viewed
FROM
    `media_pipeline.video_grades`
WHERE
    actual_avg_percentage_viewed IS NOT NULL;

-- ============================================================================
-- 2. Gradient Boosted Tree Regressor for Non-Linear Retention Prediction
-- ============================================================================
CREATE OR REPLACE MODEL `media_pipeline.viral_retention_tree_regressor`
OPTIONS(
    model_type='BOOSTED_TREE_REGRESSOR',
    input_label_cols=['actual_avg_percentage_viewed'],
    max_iterations=50,
    tree_method='HIST',
    subsample=0.85
) AS
SELECT
    hrv_score,
    dpaw_score,
    adr_sfd_score,
    cke_mve_score,
    ltss_score,
    duration_seconds,
    hook_onset_latency_seconds,
    drop_timestamp_seconds,
    buildup_duration_seconds,
    predrop_silence_ms,
    strobe_hz,
    actual_avg_percentage_viewed
FROM
    `media_pipeline.video_grades`
WHERE
    actual_avg_percentage_viewed IS NOT NULL;

-- ============================================================================
-- 3. K-Means Clustering for Video Archetype Categorization
-- ============================================================================
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

### 6.3 Automated Weight Extraction & Feedback Loop Query
```sql
-- Query to extract normalized linear weights from ML.WEIGHTS to recalibrate EVPI formula
WITH raw_weights AS (
    SELECT
        processed_input,
        weight
    FROM
        ML.WEIGHTS(MODEL `media_pipeline.viral_weight_regressor`)
    WHERE
        processed_input IN ('hrv_score', 'dpaw_score', 'adr_sfd_score', 'cke_mve_score', 'ltss_score')
),
positive_weights AS (
    SELECT
        processed_input,
        GREATEST(0.01, weight) AS safe_weight
    FROM
        raw_weights
),
normalized_weights AS (
    SELECT
        processed_input,
        safe_weight / SUM(safe_weight) OVER() AS normalized_weight
    FROM
        positive_weights
)
SELECT
    processed_input AS feature_name,
    ROUND(normalized_weight, 4) AS recalibrated_weight
FROM
    normalized_weights;
```

---

## 7. Downstream Consumption & Implementation Verification

This specification is directly consumed by:
1. **Milestone 2 (Ingestion Daemon)**: `media_pipeline/ingestion/`
   - Ingests 4K video files without quality loss, maintaining SHA-256 integrity for high-fidelity audio/visual feature extraction.
2. **Milestone 3 (PySpark Grading Engine)**: `media_pipeline/grading/`
   - Imports `viral_schema.py` for Pydantic response validation.
   - Evaluates the 5 scoring parameters and applies the EVPI formula.
3. **Milestone 4 (BigQuery ML Loop)**: `media_pipeline/bqml/`
   - Executes `schema.sql` and `models.sql` to sink grading results and train predictive models.
   - Extracts dynamic weights to close the ML optimization loop.
