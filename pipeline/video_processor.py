"""
Video Processor for OpenShorts Pipeline.
Handles 9:16 vertical reframing, subtitle generation, and viral hook overlays using FFmpeg.
"""

import os
import subprocess
from typing import Any, Dict, List, Optional


def create_ass_subtitles(
    segments: List[Dict[str, Any]],
    clip_start: float,
    clip_end: float,
    output_ass_path: str
) -> bool:
    """
    Creates an ASS subtitle file with styled, high-impact captions for the clip.
    """
    header = """[Script Info]
Title: OpenShorts Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,40,40,240,1
Style: Highlight,Arial,64,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,40,40,240,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []

    def format_ts(seconds: float) -> str:
        s = max(0.0, seconds)
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = s % 60
        return f"{h:01d}:{m:02d}:{sec:05.2f}"

    has_content = False
    for seg in segments:
        s_start = float(seg.get("start", 0))
        s_end = float(seg.get("end", 0))

        # Check overlap with clip
        if s_end < clip_start or s_start > clip_end:
            continue

        text = seg.get("text", "").strip()
        if not text:
            continue

        # Adjust relative to clip start
        rel_start = max(0.0, s_start - clip_start)
        rel_end = min(clip_end - clip_start, s_end - clip_start)

        if rel_end > rel_start:
            has_content = True
            clean_text = text.replace("{", "").replace("}", "")
            events.append(
                f"Dialogue: 0,{format_ts(rel_start)},{format_ts(rel_end)},Default,,0,0,0,,{clean_text}"
            )

    if not has_content:
        return False

    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events))

    return True


def render_short_clip(
    input_video: str,
    clip_start: float,
    clip_end: float,
    output_path: str,
    format_type: str = "vertical",
    hook_text: Optional[str] = None,
    subtitles_ass: Optional[str] = None,
    fast_mode: bool = True
) -> bool:
    """
    Cuts clip from input_video, applies 9:16 vertical layout (blurred background + centered video),
    draws the viral hook text overlay, and applies subtitles.
    """
    duration = clip_end - clip_start
    if duration <= 0:
        return False

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Base filtergraph for 9:16 vertical output (1080x1920)
    if format_type == "vertical":
        # Professional Split/Blur Vertical:
        # Background: scale to fill 1080x1920, heavy boxblur, slightly darkened
        # Foreground: scale to width 1080 preserving ratio, centered vertically
        vf_filters = [
            "[0:v]split=2[bg][fg]",
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5,eq=brightness=-0.1[bgblur]",
            "[fg]scale=1080:-2[fgscaled]",
            "[bgblur][fgscaled]overlay=(W-w)/2:(H-h)/2[base]"
        ]
        last_out = "[base]"
    elif format_type == "square":
        vf_filters = [
            "[0:v]split=2[bg][fg]",
            "[bg]scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080,boxblur=20:5,eq=brightness=-0.1[bgblur]",
            "[fg]scale=1080:-2[fgscaled]",
            "[bgblur][fgscaled]overlay=(W-w)/2:(H-h)/2[base]"
        ]
        last_out = "[base]"
    else:  # horizontal
        vf_filters = ["[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[base]"]
        last_out = "[base]"

    # Subtitle burning
    if subtitles_ass and os.path.exists(subtitles_ass):
        # Escape path for FFmpeg filter
        escaped_ass = subtitles_ass.replace("\\", "/").replace(":", "\\:")
        vf_filters.append(f"{last_out}subtitles='{escaped_ass}'[with_sub]")
        last_out = "[with_sub]"

    # Hook text overlay in top portion of screen for first 3.5 seconds
    if hook_text:
        clean_hook = hook_text.replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")
        hook_filter = (
            f"{last_out}drawtext=text='{clean_hook}':"
            f"fontsize=52:fontcolor=yellow:borderw=4:bordercolor=black:"
            f"x=(w-text_w)/2:y=340:"
            f"box=1:boxcolor=black@0.65:boxborderw=14:"
            f"enable='between(t,0,3.5)'[with_hook]"
        )
        vf_filters.append(hook_filter)
        last_out = "[with_hook]"

    filtergraph = ";".join(vf_filters)
    # Remove final bracket for -map
    final_stream = last_out

    preset = "veryfast" if fast_mode else "medium"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(clip_start),
        "-t", str(duration),
        "-i", input_video,
        "-filter_complex", filtergraph,
        "-map", final_stream,
        "-map", "0:a?",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
        else:
            print(f"⚠️ FFmpeg error for {output_path}: {res.stderr[-400:]}")
            # Try fallback without complex filters if failed
            return fallback_simple_cut(input_video, clip_start, duration, output_path)
    except Exception as e:
        print(f"❌ Render exception: {e}")
        return fallback_simple_cut(input_video, clip_start, duration, output_path)


def fallback_simple_cut(input_video: str, start: float, duration: float, output_path: str) -> bool:
    """Fallback simple ffmpeg cut when complex filter fails."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", input_video,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        output_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
        return res.returncode == 0 and os.path.exists(output_path)
    except Exception:
        return False
