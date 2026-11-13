"""
OpenShorts Subtitle Quality & Script Validator
Enforces strict character set validation on generated subtitle files (.ass and .srt)
prior to video burning:
- In "romanized" mode: Enforces 100% ASCII-only English letters (A-Z, a-z, 0-9, basic punctuation).
- Strictly prohibits Telugu Unicode (U+0C00-U+0C7F), Devanagari Unicode (U+0900-U+097F),
  and any non-Latin scripts from appearing in the rendered video.
- Preserves all ASS override tags ({\\...}) and timing coordinates intact.
- Automatically fixes and cleanses residual invalid characters before failing.
"""

import os
import re
from typing import List, Tuple

try:
    from transliterate import transliterate_text, is_pure_ascii, sanitize_to_ascii
except ImportError:
    from .transliterate import transliterate_text, is_pure_ascii, sanitize_to_ascii


class SubtitleValidationError(Exception):
    """Raised when subtitle text fails strict script validation."""
    pass


# Regex pattern to match ASS override tags like {\an5}, {\c&H00D7FF&}, {\r}, etc.
ASS_TAG_PATTERN = re.compile(r'(\{[^}]*\})')

# Regex pattern to match ASS Dialogue lines
# Dialogue: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
ASS_DIALOGUE_PATTERN = re.compile(
    r'^(Dialogue:\s*\d+,\s*([^,]+),\s*([^,]+),\s*([^,]*),\s*([^,]*),\s*\d+,\s*\d+,\s*\d+,\s*[^,]*,\s*)(.*)$'
)

# Regex to detect Indic or non-Latin Unicode characters
NON_LATIN_PATTERN = re.compile(r'[\u0900-\u097F\u0C00-\u0C7F\u0600-\u06FF\u4E00-\u9FFF\u3040-\u30FF\u0400-\u04FF]')


def validate_ass_text_content(text_content: str, mode: str = "romanized") -> Tuple[bool, str, List[str]]:
    """
    Validate the text portion of an ASS event, separating ASS tags from visible words.
    Returns (is_valid, sanitized_text, error_messages).
    """
    parts = ASS_TAG_PATTERN.split(text_content)
    cleaned_parts = []
    errors = []

    for part in parts:
        # Keep ASS tags exactly as is
        if part.startswith('{') and part.endswith('}'):
            cleaned_parts.append(part)
        else:
            if not part:
                continue

            cleaned_part = part
            if mode == "romanized":
                if not is_pure_ascii(cleaned_part):
                    # Attempt automatic transliteration & ASCII sanitization
                    cleaned_part = transliterate_text(cleaned_part)
                    cleaned_part = sanitize_to_ascii(cleaned_part)

                # Recheck
                if not is_pure_ascii(cleaned_part):
                    bad_chars = [f"U+{ord(c):04X} ({c})" for c in cleaned_part if ord(c) > 127]
                    errors.append(f"Non-ASCII characters detected in romanized subtitle: {', '.join(bad_chars[:5])}")

            cleaned_parts.append(cleaned_part)

    final_text = "".join(cleaned_parts)
    is_valid = len(errors) == 0
    return is_valid, final_text, errors


def validate_and_sanitize_ass_file(ass_path: str, mode: str = "romanized") -> bool:
    """
    Scan every dialogue event in an .ass file:
    - Verifies timestamps and formatting tags are preserved.
    - If non-ASCII / non-Latin characters exist in Romanized mode:
        Automatically cleans and transliterates them.
    - If characters remain invalid, raises SubtitleValidationError to prevent
      rendering invalid subtitles onto the video.
    """
    if not os.path.exists(ass_path):
        raise FileNotFoundError(f"Subtitle file not found: {ass_path}")

    # Read UTF-8 (handling BOM if present)
    with open(ass_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()

    modified = False
    new_lines = []
    all_errors = []

    for idx, line in enumerate(lines):
        m = ASS_DIALOGUE_PATTERN.match(line)
        if m:
            prefix, start_time, end_time, style, name, text_content = m.groups()
            is_valid, cleaned_text, errors = validate_ass_text_content(text_content, mode=mode)

            if errors:
                for err in errors:
                    all_errors.append(f"Line {idx + 1} ({start_time} --> {end_time}): {err}")

            if cleaned_text != text_content:
                modified = True
                new_lines.append(f"{prefix}{cleaned_text}\n")
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if all_errors:
        raise SubtitleValidationError(
            f"Strict subtitle validation failed for {os.path.basename(ass_path)} ({len(all_errors)} errors):\n"
            + "\n".join(all_errors[:10])
        )

    # Save sanitized file if any characters were fixed
    if modified:
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

    return True


def validate_and_sanitize_srt_file(srt_path: str, mode: str = "romanized") -> bool:
    """
    Validate and sanitize an .srt subtitle file.
    Ensures Romanized mode contains strictly ASCII English characters.
    """
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f"Subtitle file not found: {srt_path}")

    with open(srt_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    if mode != "romanized":
        return True

    if is_pure_ascii(content):
        return True

    # Sanitize and revalidate
    sanitized_content = transliterate_text(content)
    sanitized_content = sanitize_to_ascii(sanitized_content)

    if not is_pure_ascii(sanitized_content):
        bad_chars = [f"U+{ord(c):04X} ({c})" for c in sanitized_content if ord(c) > 127]
        raise SubtitleValidationError(
            f"Strict SRT validation failed: non-ASCII characters remain: {', '.join(bad_chars[:5])}"
        )

    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write(sanitized_content)

    return True
