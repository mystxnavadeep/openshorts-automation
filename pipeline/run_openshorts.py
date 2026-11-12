#!/usr/bin/env python3
"""
OpenShorts Video Processing Orchestrator
Executes the full pipeline inside GitHub Actions or local environment:
1. YouTube Download (yt-dlp)
2. Audio Extraction & Faster-Whisper Transcription (CPU int8)
3. Gemini AI Viral Moment Detection & Hook Generation
4. 9:16 Vertical Reframing, Subtitle Burning & Hook Overlay
5. Export & Metadata Packaging for Google Drive & Artifacts
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
# Ensure pipeline modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.moment_detector import detect_viral_moments
from pipeline.video_processor import create_ass_subtitles, render_short_clip

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def run_command(cmd, timeout=300):
    """Executes a system shell command with logging."""
    print(f"⚙️ Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    if res.returncode != 0:
        print(f"⚠️ Command stderr: {res.stderr[-300:]}")
    return res


def download_youtube_video(url: str, output_dir: str) -> dict:
    """Downloads YouTube video using yt-dlp and extracts metadata."""
    import yt_dlp

    os.makedirs(output_dir, exist_ok=True)
    temp_template = os.path.join(output_dir, "source.%(ext)s")

    ydl_opts = {
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': temp_template,
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'quiet': False,
        'no_warnings': True,
        # yt-dlp client choices to avoid bot detection
        'extractor_args': {
            'youtube': {
                'player_client': ['default', 'mweb']
            }
        }
    }

    # Optional cookies if configured in environment
    cookies_env = os.getenv("YT_COOKIES")
    cookie_file = None
    if cookies_env:
        cookie_file = os.path.join(output_dir, "cookies.txt")
        with open(cookie_file, "w") as f:
            f.write(cookies_env)
        ydl_opts['cookiefile'] = cookie_file

    print(f"📥 Downloading video from {url}...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # Ensure mp4 extension after merge
        if not filename.endswith(".mp4"):
            filename = os.path.splitext(filename)[0] + ".mp4"

    return {
        "title": info.get("title", "YouTube Video"),
        "duration": float(info.get("duration", 0)),
        "author": info.get("uploader", "Unknown"),
        "id": info.get("id"),
        "filepath": filename
    }


def transcribe_video(video_path: str, temp_dir: str, model_name: str = "base") -> dict:
    """Extracts 16kHz audio and transcribes with faster-whisper on CPU."""
    from faster_whisper import WhisperModel

    audio_path = os.path.join(temp_dir, "extracted_audio.wav")
    print("🎙️ Extracting audio for Whisper transcription...")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise RuntimeError("Failed to extract audio using ffmpeg")

    print(f"🧠 Loading Faster-Whisper ({model_name}, CPU, int8)...")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")

    segments_generator, info = model.transcribe(
        audio_path,
        beam_size=3,
        word_timestamps=True,
        vad_filter=True
    )

    print(f"📝 Detected language: {info.language} (probability: {info.language_probability:.2f})")

    segments = []
    full_text_list = []

    for seg in segments_generator:
        words = []
        if seg.words:
            for w in seg.words:
                words.append({
                    "word": w.word,
                    "start": round(w.start, 2),
                    "end": round(w.end, 2),
                    "probability": round(w.probability, 2)
                })

        segments.append({
            "id": seg.id,
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
            "words": words
        })
        full_text_list.append(seg.text.strip())

    full_text = " ".join(full_text_list)
    return {
        "text": full_text,
        "language": info.language,
        "duration": info.duration,
        "segments": segments
    }


def main():
    parser = argparse.ArgumentParser(description="OpenShorts Video Processing Orchestrator")
    parser.add_argument("--url", "-u", required=True, help="YouTube video URL")
    parser.add_argument("--output-dir", "-o", default="output", help="Output directory for generated shorts")
    parser.add_argument("--format", default="vertical", choices=["vertical", "square", "horizontal", "auto"],
                        help="Output aspect ratio (default: vertical 9:16)")
    parser.add_argument("--target-clips", type=int, default=3, help="Number of shorts to generate (1-10)")
    parser.add_argument("--min-seconds", type=int, default=15, help="Minimum clip duration in seconds")
    parser.add_argument("--max-seconds", type=int, default=60, help="Maximum clip duration in seconds")
    parser.add_argument("--auto-hook", type=str, default="true", help="Generate viral hook overlay (true/false)")
    parser.add_argument("--whisper-model", default="base", help="Faster-Whisper model (tiny, base, small)")
    parser.add_argument("--fast-mode", type=str, default="true", help="Use fast CPU presets")

    args = parser.parse_args()

    format_type = "vertical" if args.format == "auto" else args.format
    auto_hook = args.auto_hook.lower() in ("true", "1", "yes")
    fast_mode = args.fast_mode.lower() in ("true", "1", "yes")

    start_time = time.time()
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(args.output_dir, exist_ok=True)

    print("==========================================================")
    print("           OpenShorts Video Processing Pipeline           ")
    print("==========================================================")
    print(f"🎬 Target URL:     {args.url}")
    print(f"📱 Format:         {format_type} (9:16 vertical shorts)")
    print(f"🎯 Target Clips:   {args.target_clips}")
    print(f"⏱️ Clip Bounds:    {args.min_seconds}s - {args.max_seconds}s")
    print(f"✨ Viral Hook:     {auto_hook}")
    print(f"⚡ CPU Fast Mode:  {fast_mode}")
    print("==========================================================")

    # Step 1: Download Video
    dl_info = download_youtube_video(args.url, temp_dir)
    source_video = dl_info["filepath"]
    video_duration = dl_info["duration"]
    print(f"✓ Downloaded: '{dl_info['title']}' ({video_duration:.1f}s)")

    # Step 2: Transcribe
    transcription = transcribe_video(source_video, temp_dir, model_name=args.whisper_model)
    print(f"✓ Transcribed {len(transcription['segments'])} segments ({len(transcription['text'].split())} words)")

    # Step 3: Viral Moment Detection with Gemini AI
    print("🧠 Analyzing viral moments with Gemini AI...")
    moments = detect_viral_moments(
        transcript_text=transcription["text"],
        segments=transcription["segments"],
        video_duration=video_duration,
        target_clips=args.target_clips,
        min_seconds=args.min_seconds,
        max_seconds=args.max_seconds
    )
    print(f"✓ Selected {len(moments)} viral clips!")

    # Step 4: Render Shorts
    rendered_clips = []
    for i, m in enumerate(moments):
        clip_index = i + 1
        clip_name = f"short_{clip_index:02d}.mp4"
        clip_output_path = os.path.join(args.output_dir, clip_name)
        ass_sub_path = os.path.join(temp_dir, f"subtitles_{clip_index}.ass")

        start_s = float(m.get("start", 0))
        end_s = float(m.get("end", 0))
        duration_s = end_s - start_s
        title = m.get("video_title_for_youtube_short", f"Short Clip {clip_index}")
        hook_text = m.get("viral_hook_text") if auto_hook else None

        print(f"\n✂️ Rendering Clip {clip_index}/{len(moments)}: [{start_s:.2f}s -> {end_s:.2f}s] ({duration_s:.1f}s)")
        print(f"   📌 Title: {title}")
        if hook_text:
            print(f"   ✨ Hook:  {hook_text}")

        # Subtitles
        has_subs = create_ass_subtitles(transcription["segments"], start_s, end_s, ass_sub_path)

        # Render
        success = render_short_clip(
            input_video=source_video,
            clip_start=start_s,
            clip_end=end_s,
            output_path=clip_output_path,
            format_type=format_type,
            hook_text=hook_text,
            subtitles_ass=ass_sub_path if has_subs else None,
            fast_mode=fast_mode
        )

        if success:
            file_size_mb = os.path.getsize(clip_output_path) / (1024 * 1024)
            print(f"   ✅ Saved: {clip_name} ({file_size_mb:.2f} MB)")
            rendered_clips.append({
                "clip_index": clip_index,
                "filename": clip_name,
                "file_path": clip_output_path,
                "size_mb": round(file_size_mb, 2),
                "start": start_s,
                "end": end_s,
                "duration": round(duration_s, 2),
                "title": title,
                "tiktok_description": m.get("video_description_for_tiktok", ""),
                "instagram_description": m.get("video_description_for_instagram", ""),
                "viral_hook": hook_text
            })
        else:
            print(f"   ❌ Failed to render clip {clip_index}")

    # Step 5: Save Metadata JSON
    metadata = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": {
            "url": args.url,
            "title": dl_info["title"],
            "author": dl_info["author"],
            "id": dl_info["id"],
            "duration": video_duration
        },
        "settings": {
            "format": format_type,
            "auto_hook": auto_hook,
            "fast_mode": fast_mode
        },
        "total_clips": len(rendered_clips),
        "clips": rendered_clips
    }

    metadata_path = os.path.join(args.output_dir, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # Cleanup temporary downloads
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass

    total_time = time.time() - start_time
    print("\n==========================================================")
    print(f"🎉 Pipeline Completed Successfully in {total_time:.1f}s!")
    print(f"📦 Total Generated Shorts: {len(rendered_clips)}")
    print(f"📁 Destination Directory:   {args.output_dir}")
    print("==========================================================")


if __name__ == "__main__":
    main()
