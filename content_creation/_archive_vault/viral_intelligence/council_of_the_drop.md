---
name: Council of the Drop — 5-Persona Creative Debate Model & Multi-Agent Arbitration Architecture
context_mapping: Extracted from `content_creation/council_ui.html`, `content_creation/agent_review_output.md`, and `content_creation/dashboard_backend.py`.
strengths: Replaces legacy film-style post-production roles (Compositor, Colorist, Critic) with 5 specialized short-form algorithmic personas grounded in dopamine anticipation cycles, BPM synchronization, and platform mechanics. Formulates multi-agent debates into a strictly arbitrated JSON contract (`CouncilDebateSession`, `ArbitratedConsensus`, `SyntheticPrompt`) that directly drives timeline trims, VFX markers, and social packaging.
weaknesses: In the legacy implementation, `council_ui.html` suffered from contract desynchronization where `dashboard_backend.py:277` was modified to return plain text, orphaning the rich animated UI and hardcoding divergent localhost ports (9051 vs 8000).
implementation_instructions: Dispatch the System Prompt defined in Section 4 to Gemini or Claude using structured outputs (`response_schema=CouncilDebateSession`). Parse the resulting `ArbitratedConsensus` and feed the `synthetic_prompt` downstream to DaVinci Resolve timeline generators or automated FFmpeg encoders.
---

# Council of the Drop: 5-Persona Creative Debate Model

## 1. Executive Summary & Architectural Paradigm

Traditional post-production workflows rely on a Hollywood film framework: *The Visionary, The Compositor, The Colorist, The Technical Lead, and The Critic*. 

When applied to algorithmic short-form platforms (YouTube Shorts, TikTok, Instagram Reels), this legacy framework **fails catastrophically**:
1. **Film vs. Dopamine**: A cinematic film aesthetic registers to social users as a sponsored commercial, triggering an immediate swipe-away. Short-form requires raw, high-kinetic authenticity.
2. **Visual vs. Audio Primacy**: Film editing is visually led. Dance music (EDM) short-form is strictly audio-led: visual cuts must align frame-accurately with the sub-bass kick, snare transient, and build-up riser.
3. **The "Critic" Bottleneck**: In algorithmic media, human review cycles kill publishing velocity. The recommendation algorithm is the sole arbiter of retention; multi-agent deliberation must simulate algorithmic incentives, not subjective taste.

The **Council of the Drop** replaces the film paradigm with a multi-agent cognitive architecture modeled on digital psychology, psychoacoustics, and platform mechanics.

```
┌────────────────────────────────────────────────────────────────────────┐
│                   COUNCIL OF THE DROP ARBITRATION                     │
└────────────────────────────────────────────────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         ▼                         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ 🪝 HOOK          │       │ ⚡ KINETIC       │       │ 🔮 VIBE          │
│ ARCHITECT       │       │ EDITOR          │       │ CURATOR         │
│ (Stop-Rate/0-3s)│       │ (BPM/Transient) │       │ (Subgenre/Aesth)│
└────────┬────────┘       └────────┬────────┘       └────────┬────────┘
         │                         │                         │
         │        ┌────────────────┴────────────────┐        │
         │        │                                 │        │
         ▼        ▼                                 ▼        ▼
┌─────────────────┐                                 ┌─────────────────┐
│ ⏱️ RETENTION     │                                 │ 🔥 SOUND         │
│ HACKER          │                                 │ SEEDER          │
│ (Loop/Drop Math)│                                 │ (Audio Virality)│
└────────┬────────┘                                 └────────┬────────┘
         │                                                   │
         └─────────────────────────┬─────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │    ARBITRATION CONSENSUS     │
                    │   • Optimal Trim Window      │
                    │   • Safe-Zone Text Anchor    │
                    │   • Beat Sync Jump Cuts      │
                    │   • Synthetic Action Prompt  │
                    └──────────────────────────────┘
```

---

## 2. The 5 Creative Personas

### Persona 1: The Hook Architect (🪝 `#ff3366`)
- **Focus**: The opening 3.0-second retention gate ($[0.0\text{s}, 3.0\text{s}]$).
- **Core Metric**: Stop-Rate / Viewed vs. Swiped Away ($\text{VVSA} \ge 75\%$).
- **Role & Directives**:
  - Eliminates slow fade-ins, dead audio air ($>0.1\text{s}$), or unengaging wide shots.
  - Formulates curiosity anchors and psychological text hooks (e.g., *"Wait for the second drop..."*, *"POV: You're at the rail when the lasers hit"*).
  - Demands at least 3 pattern interrupts (cut, camera push, on-screen text, riser flash) in the opening 3 seconds.

### Persona 2: The Kinetic Editor (⚡ `#00f0ff`)
- **Focus**: Percussive rhythm, beat alignment, and dynamic velocity.
- **Core Metric**: Audio-Visual Transient Coherence ($S_{\text{coherence}}$) and cut density.
- **Role & Directives**:
  - Computes exact BPM frame rates ($128\,\text{BPM} \approx 14\,\text{frames/beat}$ at $30\,\text{fps}$).
  - Aligns visual cuts, strobe flashes, and optical zoom punches to the musical grid (downbeat, 8th-note build, 16th-note pre-drop roll).
  - Enforces the signature "Push-Pull" camera transition exactly on drop impact to simulate physical bass displacement.

### Persona 3: The Vibe Curator (🔮 `#bf00ff`)
- **Focus**: Cultural subgenre aesthetics and atmospheric authenticity.
- **Core Metric**: Visual Engagement ($S_{\text{visual}}$) and community tribal resonance.
- **Role & Directives**:
  - Validates that the visual treatment matches the music subgenre:
    - *Techno / Peak-Time*: Gritty industrial contrast, high-frequency green/white lasers, desaturated shadows, raw warehouse perspective.
    - *Dubstep / Bass Music*: Heavy camera shake, explosive pyro/flame cannons, rail-riding crowd pits, saturated reds/purples.
    - *Melodic House*: Warm golden-hour tones, sweeping atmospheric canopies, festival sunset vibes.
  - Rejects over-polished commercial grades in favor of authentic live-concert sensory immersion.

### Persona 4: The Retention Hacker (⏱️ `#00ff66`)
- **Focus**: Algorithmic mechanics, infinite looping, and platform safety.
- **Core Metric**: Average Percentage Viewed ($\text{APV} \ge 110\%$) and Safe-Zone Compliance.
- **Role & Directives**:
  - Structures footage so the outro bleeds seamlessly back into the intro, triggering continuous rewatch loops.
  - Clamps total duration strictly to $\le 59.0\text{s}$ to avoid YouTube Shorts Content ID muting.
  - Audits text and subject placement against YouTube Shorts ($900\times 1270\,\text{px}$) and TikTok ($920\times 1310\,\text{px}$) UI exclusion safe zones.

### Persona 5: The Sound Seeder (🔥 `#ffaa00`)
- **Focus**: Audio virality, UGC reuse incentives, and comment velocity.
- **Core Metric**: Sound saves, shares, and track ID comment inquiries.
- **Role & Directives**:
  - Pins high-friction engagement hooks in comments (e.g., Track ID bounties, binary 1-to-10 rating prompts).
  - Identifies whether the clip serves as a transition audio trend, a festival anthem reveal, or an unreleased ID teaser.
  - Ensures the audio mix adheres to broadcast loudness ($-14.0 \pm 1.0\,\text{LUFS}$, True Peak $\le -1.5\,\text{dBTP}$) without digital clipping.

---

## 3. Structured JSON Debate Arbitration Flow

The deliberation operates through a 2-stage multi-agent loop:
1. **Debate Phase**: Each of the 5 personas inspects the footage metadata, waveforms, and drop points, submitting a domain-specific observation, score (0-10), and requested edit.
2. **Arbitration Phase**: An impartial Arbitration Director evaluates conflicting requests (e.g., Hook Architect wants an immediate jump cut, while Vibe Curator wants a slow atmospheric build), strikes a consensus, and outputs an executable `SyntheticPrompt`.

### Schema Contract (Pydantic V2 / JSON Schema)

```python
from typing import List, Literal, Tuple, Optional
from pydantic import BaseModel, Field

class PersonaDialogueEntry(BaseModel):
    persona: Literal[
        "Hook Architect", 
        "Kinetic Editor", 
        "Vibe Curator", 
        "Retention Hacker", 
        "Sound Seeder"
    ]
    avatar_color: str = Field(..., description="Hex color: #ff3366, #00f0ff, #bf00ff, #00ff66, #ffaa00")
    domain_focus: str
    observed_strength: str
    observed_defect: str
    proposed_edit: str
    domain_score: float = Field(..., ge=0.0, le=10.0)

class ArbitratedConsensus(BaseModel):
    consensus_drop_window: Tuple[float, float] = Field(
        ..., description="(start_time_sec, end_time_sec) for final timeline cut"
    )
    recommended_duration: float = Field(..., ge=10.0, le=59.0)
    hook_strategy: str = Field(..., description="Opening 3s execution directive")
    safe_zone_anchor_y: int = Field(350, description="Recommended Y position (px) for on-screen text")
    pacing_strategy: str = Field(..., description="Transition and cut density directive")
    loop_transition_point: float = Field(..., description="Timestamp of loop foldback")
    synthetic_prompt: str = Field(
        ..., description="Complete consolidated prompt to feed downstream DaVinci/transcoder"
    )

class CouncilDebateSession(BaseModel):
    session_id: str
    video_id: str
    raw_duration_sec: float
    detected_bpm: Optional[float] = None
    dialogue: List[PersonaDialogueEntry] = Field(..., min_length=5, max_length=5)
    consensus: ArbitratedConsensus
```

---

## 4. Master Multi-Agent System Prompt

Use the following system prompt when querying Gemini or Claude for Council of the Drop execution:

```text
You are the "Council of the Drop" Autonomous Media Arbitration Engine for short-form EDM video production (YouTube Shorts, TikTok, Instagram Reels).

You must simulate a rigorous, technical creative debate between 5 specialized personas, resolve their creative tensions, and output an arbitrated consensus in strict JSON adhering to the CouncilDebateSession schema.

THE 5 PERSONAS:
1. Hook Architect (Color: #ff3366):
   - Obsessed with stop-rate in [0.0s, 3.0s]. Demands immediate audio hit, text hook, and 3 pattern interrupts.
2. Kinetic Editor (Color: #00f0ff):
   - Obsessed with percussive cutting and beat sync. Demands cuts on snare/drop, speed ramps, and push-pull drop zooms.
3. Vibe Curator (Color: #bf00ff):
   - Obsessed with EDM subculture authenticity. Aligns laser/light colorways and camera grit with subgenre tribes.
4. Retention Hacker (Color: #00ff66):
   - Obsessed with APV (>100%), seamless looping, duration ceiling (<59.0s), and UI safe-zone compliance.
5. Sound Seeder (Color: #ffaa00):
   - Obsessed with sound re-use, engagement velocity, and pinned comment hooks.

DEBATE DIRECTIVES:
- Each persona MUST evaluate the video from their strict domain perspective.
- Each persona MUST propose one concrete, timestamp-accurate edit.
- The Arbitration Consensus must balance their opposing goals into a unified timeline decision.
- The output MUST be valid JSON conforming strictly to the CouncilDebateSession schema.
```

---

## 5. Downstream Integration Blueprint

```python
# Example downstream consumption in Python pipeline:
from council_schema import CouncilDebateSession
from google import genai
from google.genai import types

def run_council_of_the_drop(client: genai.Client, video_uri: str, prompt: str) -> CouncilDebateSession:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_uri(file_uri=video_uri, mime_type="video/mp4"),
            f"Analyze this raw footage and execute the Council of the Drop debate: {prompt}"
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CouncilDebateSession,
            temperature=0.3,
        )
    )
    session = CouncilDebateSession.model_validate_json(response.text)
    
    # 1. Feed consensus drop window into DaVinci Resolve Timeline Builder
    start_sec, end_sec = session.consensus.consensus_drop_window
    # resolve_builder.append_subclip(start_sec, end_sec)
    
    # 2. Feed text hook into Safe-Zone Overlay Generator
    # safe_zone_auditor.render_hook_text(session.consensus.hook_strategy, y=session.consensus.safe_zone_anchor_y)
    
    return session
```
