r"""
---
Name: Dynamic Atempo Filter Compiler & PTS Speed Retiming Engine
Context Mapping: Originally developed in `baptism_of_music_brain/src/renderer/filtergraph.py` to overcome FFmpeg's hard constraint where a single `atempo` filter rejects speed values outside the range [0.5, 2.0].
Strengths:
  - Recursive Atempo Filter Decomposition: Automatically decomposes arbitrary playback speed factors into cascaded chains of compliant `atempo` filters:
      * Fast motion (> 2.0x): Chained 2.0x multipliers with remainder (e.g. 4.0x -> `atempo=2.0,atempo=2.0`; 5.0x -> `atempo=2.0,atempo=2.0,atempo=1.25`).
      * Slow motion (< 0.5x): Chained 0.5x multipliers with remainder (e.g. 0.25x -> `atempo=0.5,atempo=0.5`; 0.1x -> `atempo=0.5,atempo=0.5,atempo=0.5,atempo=0.8`).
      * Normal range (0.5x - 2.0x): Single cleanly formatted `atempo` filter.
      * Identity (1.0x): Passthrough `anull` with zero audio resampling overhead.
  - Audio/Video PTS Synchronization: Calculates reciprocal video timestamp scaling `setpts=(1/speed)*(PTS-STARTPTS)` and audio timestamp re-indexing `asetpts=PTS-STARTPTS`, ensuring lip-sync and audio waveform alignment remain sample-accurate.
  - Multi-Segment Speed Ramp Compilation: Compiles complex multi-segment speed ramps with source trims (`trim=start=...:end=...` / `atrim=start=...:end=...`) and automated stream concatenation (`concat=n=N:v=1:a=1`).
  - Zero-dependency: Pure Python standard library implementation with robust numeric formatting and mathematical validation.
Weaknesses:
  - Extreme speed multipliers (> 8x or < 0.125x) cascade many WSOLA (Waveform Similarity Overlap-Add) filters, which can introduce metallic phase smearing or audible comb filtering.
  - Slow-motion video requires optical flow interpolation (e.g., `minterpolate`) to avoid duplicated frames if source footage was shot at standard frame rates (24-30 fps).
Implementation Instructions:
  - Use `build_atempo_chain(speed)` to get the audio filter string.
  - Use `compile_speed_filter(speed)` to obtain a `SpeedFilterResult` containing both video and audio filter directives with PTS scaling.
  - Use `compile_multi_segment_speed_ramp(segments)` to build multi-cut retimed filtergraphs with concatenation.
  - CLI supports dry-run preview: `python atempo_filter_compiler.py --speed 4.0`.
---
"""

from dataclasses import dataclass, field
import json
import logging
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("atempo_filter_compiler")


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass(frozen=True)
class SpeedSegment:
    """Represents a discrete media segment with trimming and retiming parameters."""
    segment_id: str
    source_in_sec: float
    source_out_sec: float
    speed_multiplier: float = 1.0
    volume_multiplier: float = 1.0

    @property
    def source_duration_sec(self) -> float:
        return max(0.0, self.source_out_sec - self.source_in_sec)

    @property
    def target_duration_sec(self) -> float:
        if self.speed_multiplier <= 0.0:
            return 0.0
        return self.source_duration_sec / self.speed_multiplier


@dataclass(frozen=True)
class SpeedFilterResult:
    """Encapsulates compiled video and audio filter directives for a retimed stream."""
    speed_multiplier: float
    video_filter: str
    audio_filter: str
    video_pts_factor: float
    atempo_chain: str
    is_passthrough: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "speed_multiplier": self.speed_multiplier,
            "video_filter": self.video_filter,
            "audio_filter": self.audio_filter,
            "video_pts_factor": self.video_pts_factor,
            "atempo_chain": self.atempo_chain,
            "is_passthrough": self.is_passthrough,
        }


# ============================================================================
# CORE ALGORITHMS
# ============================================================================

def format_float(val: float, precision: int = 4) -> str:
    """Formats float cleanly without redundant trailing zeros (e.g. 2.0 -> '2.0', 1.2500 -> '1.25')."""
    if val == int(val):
        return f"{val:.1f}" if abs(val) < 1000 else f"{int(val)}"
    rounded = round(val, precision)
    # Convert :g to avoid scientific notation for typical speeds
    return f"{rounded:g}"


def build_atempo_chain(speed: float) -> str:
    """
    Recursively decomposes any speed factor into a chain of FFmpeg atempo filters
    satisfying the strict constraint: 0.5 <= atempo <= 2.0.

    Examples:
      - speed=1.0  -> "anull"
      - speed=2.0  -> "atempo=2.0"
      - speed=4.0  -> "atempo=2.0,atempo=2.0"
      - speed=5.0  -> "atempo=2.0,atempo=2.0,atempo=1.25"
      - speed=0.5  -> "atempo=0.5"
      - speed=0.25 -> "atempo=0.5,atempo=0.5"
      - speed=0.1  -> "atempo=0.5,atempo=0.5,atempo=0.5,atempo=0.8"
    """
    if speed <= 0.0:
        raise ValueError(f"Speed multiplier must be strictly positive, got {speed}")

    # Passthrough identity
    if math.isclose(speed, 1.0, rel_tol=1e-5):
        return "anull"

    filters: List[str] = []
    current = float(speed)

    # Accelerate (> 2.0x)
    while current > 2.0:
        filters.append("atempo=2.0")
        current /= 2.0

    # Decelerate (< 0.5x)
    while current < 0.5:
        filters.append("atempo=0.5")
        current /= 0.5

    # Remainder filter
    if not math.isclose(current, 1.0, rel_tol=1e-5):
        filters.append(f"atempo={format_float(current)}")

    # Edge case: If all reductions resulted in exactly 1.0 (e.g. 4.0 / 2 / 2 = 1.0)
    if not filters:
        return "anull"

    return ",".join(filters)


def compile_speed_filter(
    speed: float,
    trim_start: Optional[float] = None,
    trim_end: Optional[float] = None,
    volume_multiplier: float = 1.0,
) -> SpeedFilterResult:
    """
    Compiles synchronized video and audio filters for a retimed segment.
    Synchronizes video PTS using `setpts=(1/speed)*(PTS-STARTPTS)` and audio using `asetpts=PTS-STARTPTS`.
    """
    if speed <= 0.0:
        raise ValueError(f"Speed multiplier must be positive, got {speed}")

    pts_factor = 1.0 / speed
    is_identity = math.isclose(speed, 1.0, rel_tol=1e-5)

    # 1. Video Filters
    v_filters: List[str] = []
    if trim_start is not None and trim_end is not None:
        v_filters.append(f"trim=start={format_float(trim_start)}:end={format_float(trim_end)}")

    if not is_identity:
        v_filters.append(f"setpts={format_float(pts_factor)}*(PTS-STARTPTS)")
    else:
        v_filters.append("setpts=PTS-STARTPTS")

    video_filter_str = ",".join(v_filters)

    # 2. Audio Filters
    a_filters: List[str] = []
    if trim_start is not None and trim_end is not None:
        a_filters.append(f"atrim=start={format_float(trim_start)}:end={format_float(trim_end)}")

    a_filters.append("asetpts=PTS-STARTPTS")

    atempo_chain = build_atempo_chain(speed)
    if atempo_chain != "anull":
        a_filters.append(atempo_chain)

    if not math.isclose(volume_multiplier, 1.0, rel_tol=1e-5):
        a_filters.append(f"volume={format_float(volume_multiplier)}")

    audio_filter_str = ",".join(a_filters)

    return SpeedFilterResult(
        speed_multiplier=speed,
        video_filter=video_filter_str,
        audio_filter=audio_filter_str,
        video_pts_factor=pts_factor,
        atempo_chain=atempo_chain,
        is_passthrough=is_identity,
    )


def compile_multi_segment_speed_ramp(
    segments: List[SpeedSegment],
    input_video_label: str = "[0:v]",
    input_audio_label: str = "[0:a]",
    output_video_label: str = "[vout]",
    output_audio_label: str = "[aout]",
) -> str:
    """
    Compiles a complete FFmpeg filter_complex script representing multiple trimmed,
    speed-adjusted segments concatenated into a single seamless output stream.
    """
    if not segments:
        raise ValueError("Segments list cannot be empty.")

    filter_chains: List[str] = []
    num_segments = len(segments)

    for i, seg in enumerate(segments):
        v_out = f"[v{i}]"
        a_out = f"[a{i}]"

        compiled = compile_speed_filter(
            speed=seg.speed_multiplier,
            trim_start=seg.source_in_sec,
            trim_end=seg.source_out_sec,
            volume_multiplier=seg.volume_multiplier,
        )

        filter_chains.append(f"{input_video_label}{compiled.video_filter}{v_out}")
        filter_chains.append(f"{input_audio_label}{compiled.audio_filter}{a_out}")

    # Concatenation stage
    if num_segments > 1:
        concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(num_segments))
        concat_directive = f"{concat_inputs}concat=n={num_segments}:v=1:a=1{output_video_label}{output_audio_label}"
        filter_chains.append(concat_directive)
    else:
        # Single segment alias to final output labels
        filter_chains.append(f"[v0]null{output_video_label}")
        filter_chains.append(f"[a0]anull{output_audio_label}")

    return ";".join(filter_chains)


# ============================================================================
# COMPILER CLASS
# ============================================================================

class AtempoFilterCompiler:
    """
    High-level compiler interface for generating atempo audio filter chains
    and synchronized PTS speed filtergraphs.
    """

    @staticmethod
    def chain(speed: float) -> str:
        """Generates atempo filter string for given speed."""
        return build_atempo_chain(speed)

    @staticmethod
    def compile_speed(
        speed: float,
        trim_start: Optional[float] = None,
        trim_end: Optional[float] = None,
        volume: float = 1.0,
    ) -> SpeedFilterResult:
        """Compiles synchronized video and audio speed filter."""
        return compile_speed_filter(speed=speed, trim_start=trim_start, trim_end=trim_end, volume_multiplier=volume)

    @staticmethod
    def compile_ramp(segments: List[SpeedSegment]) -> str:
        """Compiles multi-segment speed ramp filtergraph."""
        return compile_multi_segment_speed_ramp(segments)


# ============================================================================
# CLI ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Dynamic Atempo Filter Compiler & PTS Retiming Engine")
    parser.add_argument("--speed", type=float, default=None, help="Target playback speed multiplier (e.g. 0.25, 1.5, 4.0)")
    parser.add_argument("--trim-start", type=float, default=None, help="Trim start time in seconds")
    parser.add_argument("--trim-end", type=float, default=None, help="Trim end time in seconds")
    parser.add_argument("--volume", type=float, default=1.0, help="Volume multiplier (default: 1.0)")
    parser.add_argument("--test-speeds", action="store_true", help="Run automated test suite verifying decomposition across speed range")
    parser.add_argument("--test-ramp", action="store_true", help="Generate sample 3-stage EDM speed ramp filtergraph")

    args = parser.parse_args()

    if args.test_speeds:
        test_cases = [0.1, 0.25, 0.33, 0.5, 0.75, 1.0, 1.5, 2.0, 3.5, 4.0, 8.0, 10.0]
        print("=== ATEMPO FILTER CHAIN DECOMPOSITION TEST ===")
        all_passed = True
        for s in test_cases:
            chain = build_atempo_chain(s)
            comp = compile_speed_filter(s)
            # Verify each filter in chain is within [0.5, 2.0]
            if chain != "anull":
                filters = chain.split(",")
                for f in filters:
                    val = float(f.split("=")[1])
                    if not (0.5 <= val <= 2.0):
                        print(f"[FAIL] Speed {s}: Filter {f} violates 0.5 <= atempo <= 2.0 constraint!")
                        all_passed = False
            print(f"Speed {s:>5.2f}x -> {chain:<45} | Video PTS: {comp.video_pts_factor:.4f}*(PTS-STARTPTS)")

        if all_passed:
            print("\n[PASS] All atempo chains strictly obey FFmpeg's 0.5 <= atempo <= 2.0 constraints!")
            sys.exit(0)
        else:
            sys.exit(1)

    if args.test_ramp:
        segments = [
            SpeedSegment(segment_id="intro", source_in_sec=0.0, source_out_sec=10.0, speed_multiplier=1.0),
            SpeedSegment(segment_id="buildup", source_in_sec=10.0, source_out_sec=20.0, speed_multiplier=2.5),
            SpeedSegment(segment_id="drop_slowmo", source_in_sec=20.0, source_out_sec=25.0, speed_multiplier=0.25),
            SpeedSegment(segment_id="outro", source_in_sec=25.0, source_out_sec=35.0, speed_multiplier=1.0),
        ]
        fg = compile_multi_segment_speed_ramp(segments)
        print("=== COMPILED 4-SEGMENT SPEED RAMP FILTERGRAPH ===")
        print(fg)
        sys.exit(0)

    if args.speed is not None:
        comp = compile_speed_filter(
            speed=args.speed,
            trim_start=args.trim_start,
            trim_end=args.trim_end,
            volume_multiplier=args.volume,
        )
        print("COMPILED RETIMING RESULT:")
        print(f"  Speed Multiplier: {comp.speed_multiplier}x")
        print(f"  Atempo Chain:     {comp.atempo_chain}")
        print(f"  Video Filter:     {comp.video_filter}")
        print(f"  Audio Filter:     {comp.audio_filter}")
        sys.exit(0)

    parser.print_help()
