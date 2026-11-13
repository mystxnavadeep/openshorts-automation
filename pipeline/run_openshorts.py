#!/usr/bin/env python3
"""
Official OpenShorts Runner & Orchestrator
Executes the genuine OpenShorts engine (mutonby/openshorts/main.py) inside GitHub Actions or local environment.

This script does NOT replace or mock OpenShorts. It configures the CPU-safe execution
environment for GitHub Actions and invokes the genuine official OpenShorts CLI:
    python3 -u engine/main.py -u "<URL>" -o "<OUTPUT_DIR>" --format "<FORMAT>"
"""

import argparse
import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT_DIR / "engine"
ENGINE_MAIN = ENGINE_DIR / "main.py"


def main():
    parser = argparse.ArgumentParser(description="Official OpenShorts Runner")
    parser.add_argument("--url", "-u", required=True, help="YouTube video URL to process")
    parser.add_argument("--output-dir", "-o", default="output", help="Output directory for generated shorts")
    parser.add_argument("--format", default="vertical", choices=["vertical", "square", "horizontal", "auto"],
                        help="Output aspect ratio (default: vertical 9:16)")
    parser.add_argument("--gemini-model", default="gemini-3.1-flash-lite",
                        help="Gemini model for viral moment detection (e.g. gemini-3.1-flash-lite, gemini-3.5-flash)")
    parser.add_argument("--whisper-model", default="base",
                        help="Faster-Whisper model for CPU transcription (base, small, tiny)")
    parser.add_argument("--auto-hook", type=str, default="true",
                        help="Enable AI viral hook text overlays (true/false)")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of concurrent clip workers (default: 1 for CPU stability in CI)")

    args = parser.parse_args()

    print("=" * 65)
    print("       🚀 EXECUTING OFFICIAL OPENSHORTS PROCESSING ENGINE        ")
    print(f"       Upstream Source: https://github.com/mutonby/openshorts    ")
    print("=" * 65)

    # 1. Verify official OpenShorts engine exists
    if not ENGINE_MAIN.exists():
        print(f"❌ Error: Official OpenShorts engine not found at: {ENGINE_MAIN}")
        print("Please ensure the official OpenShorts codebase is present in engine/")
        sys.exit(1)

    print(f"✓ Found official OpenShorts engine: {ENGINE_MAIN}")

    # 2. Check GEMINI_API_KEY
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("❌ Error: GEMINI_API_KEY is not set in environment or secrets!")
        print("Official OpenShorts requires GEMINI_API_KEY for moment detection & hook generation.")
        print("Set it via: gh secret set GEMINI_API_KEY --repo <owner>/<repo>")
        sys.exit(1)
    else:
        print(f"✓ GEMINI_API_KEY detected (length: {len(gemini_key)} chars)")

    # 3. Configure environment for official OpenShorts CPU execution
    env = os.environ.copy()
    auto_hook_flag = "1" if args.auto_hook.lower() in ("true", "1", "yes") else "0"

    env["GPU_RENDER"] = "0"              # Disables NVENC Rust binary, forces FFmpeg CPU render
    env["FORCE_CPU"] = "1"               # Forces CPU execution
    env["TRANSCRIBE_BACKEND"] = "whisper"# Disables GPU Parakeet, uses faster-whisper
    env["WHISPER_DEVICE"] = "cpu"        # Runs Faster-Whisper on CPU
    env["WHISPER_COMPUTE"] = "int8"      # 8-bit quantization for fast CPU transcription
    env["WHISPER_MODEL"] = args.whisper_model
    env["GEMINI_MODEL"] = args.gemini_model
    env["CLIP_WORKERS"] = str(args.workers)
    env["AUTO_HOOK"] = auto_hook_flag
    env["WATERMARK"] = "0"               # Clean export without watermark
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    # Forward YouTube cookies under both variable names if present in environment
    yt_cookies = os.getenv("YOUTUBE_COOKIES") or os.getenv("YT_COOKIES")
    if yt_cookies:
        env["YOUTUBE_COOKIES"] = yt_cookies
        env["YT_COOKIES"] = yt_cookies
        print(f"✓ YouTube cookies detected in environment ({len(yt_cookies)} chars)")

    # Add engine directory to PYTHONPATH so its internal imports resolve cleanly
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{ENGINE_DIR}:{current_pythonpath}" if current_pythonpath else str(ENGINE_DIR)

    # Create output directory
    output_path = Path(args.output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    # 4. Prepare command for official main.py
    cmd = [
        sys.executable, "-u", str(ENGINE_MAIN),
        "-u", args.url,
        "-o", str(output_path),
        "--format", args.format
    ]

    print("\n📡 Execution Parameters:")
    print(f"  • Target URL:     {args.url}")
    print(f"  • Format:         {args.format}")
    print(f"  • Output Dir:     {output_path}")
    print(f"  • Gemini Model:   {args.gemini_model}")
    print(f"  • Whisper Model:  {args.whisper_model} (CPU int8)")
    print(f"  • Auto Hook:      {auto_hook_flag}")
    print(f"  • Workers:        {args.workers}")
    print(f"  • Command:        {' '.join(cmd)}\n")
    print("-" * 65)

    start_time = time.time()

    # 5. Run official OpenShorts process and stream output live
    process = subprocess.Popen(
        cmd,
        cwd=str(ENGINE_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    captured_output = []
    # Stream real-time logs to console
    for line in iter(process.stdout.readline, ''):
        print(line, end='', flush=True)
        captured_output.append(line)

    process.stdout.close()
    return_code = process.wait()

    elapsed = time.time() - start_time
    print("-" * 65)

    if return_code != 0:
        full_text = "".join(captured_output)
        if any(err in full_text for err in ["Sign in to confirm", "HTTP Error 429", "HTTP Error 403", "Failed to extract any player response"]):
            print("\n" + "=" * 65)
            print("💡 YOUTUBE CLOUD RUNNER DIAGNOSTIC:")
            print("YouTube blocked unauthenticated access from the GitHub Actions runner IP.")
            print("To enable seamless YouTube downloads on GitHub Actions:")
            print("  1. Export your YouTube cookies using the browser extension 'Get cookies.txt LOCALLY'")
            print("  2. Run: gh secret set YOUTUBE_COOKIES --repo mystxnavadeep/openshorts-automation")
            print("  3. Re-dispatch the workflow from the dashboard!")
            print("=" * 65 + "\n")
        print(f"\n❌ Official OpenShorts exited with error code {return_code} (took {elapsed:.1f}s)")
        sys.exit(return_code)

    print(f"\n✅ Official OpenShorts execution finished successfully in {elapsed:.1f}s!")

    # 6. Audit generated outputs
    all_files = list(output_path.glob("*"))
    video_clips = [f for f in all_files if f.suffix.lower() == ".mp4"]
    metadata_files = [f for f in all_files if f.name.endswith(".json")]

    print(f"\n📦 Generated Files Audit ({len(all_files)} total files):")
    for f in all_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  • {f.name} ({size_mb:.2f} MB)")

    if not video_clips:
        print("⚠️ Warning: No .mp4 clips found in output directory!")
    else:
        print(f"🎉 Successfully produced {len(video_clips)} genuine OpenShorts video clips!")

    # Standardize a combined metadata.json if OpenShorts emitted a title-prefixed metadata file
    summary_metadata = {
        "engine": "Official OpenShorts (mutonby/openshorts)",
        "source_url": args.url,
        "format": args.format,
        "duration_seconds": round(elapsed, 2),
        "total_clips": len(video_clips),
        "clips": [{"name": c.name, "size_mb": round(c.stat().st_size / (1024 * 1024), 2)} for c in video_clips]
    }
    with open(output_path / "metadata_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary_metadata, f, indent=2)


if __name__ == "__main__":
    main()
