"""
Gemini AI Viral Moment Detector for OpenShorts Pipeline.
Analyzes full video transcript and word-level timestamps to extract
high-retention viral moments with hook text, titles, and descriptions.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

VIRAL_PROMPT_TEMPLATE = """
You are an expert viral short-form video editor specializing in YouTube Shorts, TikTok, and Instagram Reels.
Analyze the following transcript and word-level timestamps from a long video to identify the top {target_clips} MOST VIRAL, engaging, high-retention moments.

⚠️ STRICT TIME & FORMAT CONTRACT:
1. Return timestamps in ABSOLUTE SECONDS from video start (floating point numbers, e.g., 14.520, 48.900).
2. Ensure 0 <= start < end <= {video_duration}.
3. Each clip duration MUST be between {min_seconds} and {max_seconds} seconds.
4. Prefer starting 0.2-0.4s BEFORE the hook phrase starts, and ending 0.2-0.4s AFTER the punchline or conclusion.
5. NEVER cut in the middle of a spoken sentence or word.
6. Order clips by viral potential (most viral first).

VIDEO DURATION: {video_duration} seconds

TRANSCRIPT:
{transcript_text}

WORD TIMESTAMPS (sample):
{words_sample}

OUTPUT REQUIREMENTS:
Return ONLY a valid JSON object matching this schema (no markdown formatting, no code fences):
{{
  "shorts": [
    {{
      "start": 12.340,
      "end": 42.100,
      "video_title_for_youtube_short": "Catchy Title (max 80 chars) 🤯",
      "video_description_for_tiktok": "High-retention caption with call-to-action #shorts #viral",
      "video_description_for_instagram": "IG caption with hashtags",
      "viral_hook_text": "HOOK TEXT (max 8 words with emoji) 😳"
    }}
  ]
}}
"""


def detect_viral_moments(
    transcript_text: str,
    segments: List[Dict[str, Any]],
    video_duration: float,
    target_clips: int = 3,
    min_seconds: int = 15,
    max_seconds: int = 60,
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Uses Google Gemini API to analyze transcript segments and extract viral shorts.
    """
    gemini_key = api_key or os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        print("⚠️ GEMINI_API_KEY not found. Falling back to heuristic moment extraction.")
        return fallback_heuristic_moments(segments, video_duration, target_clips, min_seconds, max_seconds)

    # Prepare words sample
    words_sample = []
    for s in segments[:100]:
        for w in s.get("words", [])[:50]:
            words_sample.append({
                "w": w.get("word", "").strip(),
                "s": round(float(w.get("start", 0)), 2),
                "e": round(float(w.get("end", 0)), 2)
            })

    prompt = VIRAL_PROMPT_TEMPLATE.format(
        target_clips=target_clips,
        video_duration=round(video_duration, 2),
        min_seconds=min_seconds,
        max_seconds=max_seconds,
        transcript_text=transcript_text[:12000],  # keep within context
        words_sample=json.dumps(words_sample[:150])
    )

    raw_response = None

    # Try google-genai library (official 2025/2026 client)
    try:
        from google import genai
        client = genai.Client(api_key=gemini_key)
        for model_name in ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                raw_response = response.text
                if raw_response:
                    break
            except Exception as e:
                print(f"ℹ️ Model {model_name} attempt: {e}")
    except Exception as e:
        print(f"ℹ️ google.genai client exception: {e}")

    # Fallback to google-generativeai legacy library if needed
    if not raw_response:
        try:
            import google.generativeai as gai
            gai.configure(api_key=gemini_key)
            for model_name in ["gemini-1.5-flash", "gemini-pro"]:
                try:
                    model = gai.GenerativeModel(model_name)
                    res = model.generate_content(prompt)
                    raw_response = res.text
                    if raw_response:
                        break
                except Exception:
                    continue
        except Exception:
            pass

    # Parse JSON from response
    if raw_response:
        moments = parse_gemini_json(raw_response)
        if moments:
            valid_moments = []
            for m in moments:
                start = float(m.get("start", 0))
                end = float(m.get("end", 0))
                duration = end - start
                if 0 <= start < end <= (video_duration + 2) and duration >= min_seconds:
                    m["start"] = max(0.0, start)
                    m["end"] = min(video_duration, end)
                    valid_moments.append(m)
            if valid_moments:
                return valid_moments[:target_clips]

    print("⚠️ Gemini analysis returned no valid clips. Using heuristic moments.")
    return fallback_heuristic_moments(segments, video_duration, target_clips, min_seconds, max_seconds)


def parse_gemini_json(text: str) -> Optional[List[Dict[str, Any]]]:
    """Clean markdown code blocks and parse JSON."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "shorts" in data:
            return data["shorts"]
        if isinstance(data, list):
            return data
    except Exception:
        # Search for first { and last }
        m = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                if isinstance(data, dict) and "shorts" in data:
                    return data["shorts"]
            except Exception:
                pass
    return None


def fallback_heuristic_moments(
    segments: List[Dict[str, Any]],
    video_duration: float,
    target_clips: int,
    min_seconds: int,
    max_seconds: int
) -> List[Dict[str, Any]]:
    """Generates evenly spaced high-speech clips if AI is unavailable."""
    target_len = min(45.0, (min_seconds + max_seconds) / 2.0)
    clips = []

    if video_duration <= target_len:
        return [{
            "start": 0.0,
            "end": video_duration,
            "video_title_for_youtube_short": "Top Highlight 🎬",
            "video_description_for_tiktok": "Best moment from this video! #shorts",
            "video_description_for_instagram": "Best moment #reels",
            "viral_hook_text": "Watch till the end! 🤯"
        }]

    # Divide video into slots
    step = (video_duration - target_len) / max(1, target_clips)
    for i in range(target_clips):
        start = round(i * step, 2)
        end = min(video_duration, round(start + target_len, 2))
        clips.append({
            "start": start,
            "end": end,
            "video_title_for_youtube_short": f"Highlight Part {i + 1} 🔥",
            "video_description_for_tiktok": f"Must watch highlight part {i + 1}! #shorts #viral",
            "video_description_for_instagram": f"Part {i + 1} #reels",
            "viral_hook_text": f"Wait for this... Part {i + 1} 😳"
        })

    return clips
