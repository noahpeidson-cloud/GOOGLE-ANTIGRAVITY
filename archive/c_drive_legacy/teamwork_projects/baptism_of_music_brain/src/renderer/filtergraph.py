"""Complex FFmpeg Filtergraph Compiler for Edit Decision Lists (EDL).

Translates EDL trims, speed ramps, parametric color grades (eq), scaling/padding
with aspect ratio preservation, audio normalization (EBU R128 loudnorm), volume adjustments,
and multi-segment concatenation into clean, deterministic filtergraph scripts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.models.schemas import (
    AudioMasteringSettings,
    ClipSegment,
    ColorGradeSettings,
    EditDecisionList,
    MediaProbeResult,
)

logger = logging.getLogger(__name__)


@dataclass
class FiltergraphCompilationResult:
    """Encapsulates compiled filtergraph string, required input files, and output stream mappings."""
    filter_complex_str: str
    input_files: List[str]
    map_video_label: str = "[vout]"
    map_audio_label: str = "[aout]"
    segment_count: int = 1
    has_video: bool = True
    has_audio: bool = True

    def __str__(self) -> str:
        return self.filter_complex_str


def _format_float(val: float) -> str:
    """Format float cleanly without unnecessary trailing zeros (e.g. 1.35 -> '1.35', 1.0 -> '1.0' or '1')."""
    if val == int(val):
        return f"{val:.1f}" if abs(val) < 1000 else f"{int(val)}"
    return f"{round(val, 4):g}"


def _build_atempo_chain(speed: float) -> str:
    """
    Build chain of atempo filters to accommodate FFmpeg's 0.5 to 2.0 per-filter speed constraint.
    """
    if speed <= 0.0:
        return "atempo=1.0"

    filters: List[str] = []
    current = speed

    # Handle fast speed > 2.0
    while current > 2.0:
        filters.append("atempo=2.0")
        current /= 2.0

    # Handle slow motion < 0.5
    while current < 0.5:
        filters.append("atempo=0.5")
        current /= 0.5

    filters.append(f"atempo={_format_float(current)}")
    return ",".join(filters)


def compile_filtergraph(
    edl: EditDecisionList,
    probe_map: Optional[Dict[str, Any]] = None,
) -> FiltergraphCompilationResult:
    """
    Compile an EditDecisionList into a complete FiltergraphCompilationResult
    with explicit filter graph directives, stream routing, and input indexes.
    """
    # 1. Resolve source input files mapping
    input_files: List[str] = []
    source_to_index: Dict[str, int] = {}

    def get_input_index(file_path: Optional[str]) -> int:
        target = file_path or edl.source_video_path
        if target not in source_to_index:
            idx = len(input_files)
            source_to_index[target] = idx
            input_files.append(target)
        return source_to_index[target]

    # Ensure main source video is always index 0
    get_input_index(edl.source_video_path)

    # 2. Segments processing
    segments = edl.segments
    if not segments:
        segments = [
            ClipSegment(
                clip_id="seg_default",
                source_in_sec=0.0,
                source_out_sec=5.0,
                timeline_in_sec=0.0,
                speed_multiplier=1.0,
                volume_multiplier=1.0,
            )
        ]

    num_segments = len(segments)
    filter_chains: List[str] = []

    width, height = edl.target_resolution
    # Ensure even macroblock dimensions
    width = (width // 2) * 2
    height = (height // 2) * 2

    # Color grading filter
    cg = edl.color_grade
    eq_parts = [
        f"contrast={_format_float(cg.contrast)}",
        f"brightness={_format_float(cg.brightness)}",
        f"saturation={_format_float(cg.saturation)}",
        f"gamma={_format_float(cg.gamma)}",
    ]
    if cg.gamma_r is not None:
        eq_parts.append(f"gamma_r={_format_float(cg.gamma_r)}")
    if cg.gamma_g is not None:
        eq_parts.append(f"gamma_g={_format_float(cg.gamma_g)}")
    if cg.gamma_b is not None:
        eq_parts.append(f"gamma_b={_format_float(cg.gamma_b)}")
    eq_filter = f"eq={':'.join(eq_parts)}"

    # Scale & Pad filter
    scale_pad_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
    )

    for i, seg in enumerate(segments):
        input_idx = 0
        v_in_label = f"[{input_idx}:v]"
        a_in_label = f"[{input_idx}:a]"

        v_out_label = f"[v{i}]"
        a_out_label = f"[a{i}]"

        start_s = _format_float(seg.source_in_sec)
        end_s = _format_float(seg.source_out_sec)

        # Video Filter Chain
        v_filters: List[str] = [f"trim=start={start_s}:end={end_s}"]

        if seg.speed_multiplier != 1.0:
            pts_factor = _format_float(1.0 / seg.speed_multiplier)
            v_filters.append(f"setpts={pts_factor}*(PTS-STARTPTS)")
        else:
            v_filters.append("setpts=PTS-STARTPTS")

        v_filters.append(eq_filter)
        v_filters.append(scale_pad_filter)

        filter_chains.append(f"{v_in_label}{','.join(v_filters)}{v_out_label}")

        # Audio Filter Chain
        a_filters: List[str] = [
            f"atrim=start={start_s}:end={end_s}",
            "asetpts=PTS-STARTPTS",
        ]

        if seg.speed_multiplier != 1.0:
            a_filters.append(_build_atempo_chain(seg.speed_multiplier))

        if seg.volume_multiplier != 1.0:
            a_filters.append(f"volume={_format_float(seg.volume_multiplier)}")

        filter_chains.append(f"{a_in_label}{','.join(a_filters)}{a_out_label}")

    # 3. Concatenation & Mastering Routing
    if num_segments > 1:
        concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(num_segments))
        concat_filter = f"{concat_inputs}concat=n={num_segments}:v=1:a=1[v_concat][a_concat]"
        filter_chains.append(concat_filter)
        v_final_src = "[v_concat]"
        a_final_src = "[a_concat]"
    else:
        v_final_src = "[v0]"
        a_final_src = "[a0]"

    # Video output rename/passthrough
    filter_chains.append(f"{v_final_src}null[vout]")

    # Audio Mastering
    am = edl.audio_mastering
    master_audio_filters: List[str] = []

    if am.gain_db != 0.0:
        master_audio_filters.append(f"volume={_format_float(am.gain_db)}dB")

    if am.normalize_lufs:
        master_audio_filters.append(
            f"loudnorm=I={_format_float(am.target_lufs)}:TP={_format_float(am.peak_limit_db)}:LRA=11"
        )

    if master_audio_filters:
        filter_chains.append(f"{a_final_src}{','.join(master_audio_filters)}[aout]")
    else:
        filter_chains.append(f"{a_final_src}anull[aout]")

    full_filtergraph = ";".join(filter_chains)

    return FiltergraphCompilationResult(
        filter_complex_str=full_filtergraph,
        input_files=input_files,
        map_video_label="[vout]",
        map_audio_label="[aout]",
        segment_count=num_segments,
    )


def build_filtergraph(
    edl: EditDecisionList,
    probe_map: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Primary interface returning compiled FFmpeg filtergraph string for an EDL.
    """
    res = compile_filtergraph(edl, probe_map)
    return res.filter_complex_str
