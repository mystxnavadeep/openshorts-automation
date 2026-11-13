"""
Automated Unit Tests for Automatic Subtitle Language Detection,
Phonetic Transliteration (Tenglish / Hinglish), and Strict ASCII Validation.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add engine directory to path
ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

from transliterate import (
    detect_language,
    transliterate_text,
    transliterate_word,
    transliterate_transcript,
    is_pure_ascii,
    has_telugu,
    has_devanagari,
    sanitize_to_ascii,
)
from subtitle_validator import (
    validate_ass_text_content,
    validate_and_sanitize_ass_file,
    validate_and_sanitize_srt_file,
    SubtitleValidationError,
)


class TestLanguageDetection(unittest.TestCase):
    """Test accurate speech language identification."""

    def test_detect_telugu(self):
        self.assertEqual(detect_language("నువ్వు ఎలా ఉన్నావు?"), "te")
        self.assertEqual(detect_language("నేను బాగున్నాను."), "te")
        self.assertEqual(detect_language("నేను coding చేస్తున్నాను."), "te")

    def test_detect_hindi(self):
        self.assertEqual(detect_language("आप कैसे हो?"), "hi")
        self.assertEqual(detect_language("मुझे यह बहुत पसंद है।"), "hi")
        self.assertEqual(detect_language("मैं coding कर रहा हूँ।"), "hi")

    def test_detect_english(self):
        self.assertEqual(detect_language("How are you?"), "en")
        self.assertEqual(detect_language("I am learning Telugu."), "en")

    def test_detect_with_asr_hint(self):
        self.assertEqual(detect_language("Hello world", asr_hint="te"), "te")
        self.assertEqual(detect_language("Hello world", asr_hint="hi"), "hi")
        self.assertEqual(detect_language("Hello world", asr_hint="en"), "en")


class TestTeluguTransliteration(unittest.TestCase):
    """Test Telugu -> Pure Roman Telugu (Tenglish) phonetic conversion."""

    def test_telugu_greeting(self):
        result = transliterate_text("నువ్వు ఎలా ఉన్నావు?")
        self.assertIn("Nuvvu", result)
        self.assertIn("ela", result)
        self.assertTrue("unnava?" in result or "unnavu?" in result)
        self.assertTrue(is_pure_ascii(result))

    def test_telugu_response(self):
        result = transliterate_text("నేను బాగున్నాను.")
        self.assertEqual(result, "Nenu baagunnanu.")
        self.assertTrue(is_pure_ascii(result))

    def test_telugu_compliment(self):
        result = transliterate_text("ఇది చాలా బాగుంది.")
        self.assertEqual(result, "Idi chaala baagundi.")
        self.assertTrue(is_pure_ascii(result))

    def test_telugu_mixed_coding(self):
        result = transliterate_text("నేను coding చేస్తున్నాను.")
        self.assertEqual(result, "Nenu coding chestunnanu.")
        self.assertTrue(is_pure_ascii(result))


class TestHindiTransliteration(unittest.TestCase):
    """Test Hindi -> Pure Roman Hindi (Hinglish) phonetic conversion."""

    def test_hindi_question(self):
        result = transliterate_text("आप कैसे हो?")
        self.assertEqual(result, "Aap kaise ho?")
        self.assertTrue(is_pure_ascii(result))

    def test_hindi_statement(self):
        result = transliterate_text("मुझे यह बहुत पसंद है।")
        self.assertEqual(result, "Mujhe yah bahut pasand hai.")
        self.assertTrue(is_pure_ascii(result))

    def test_hindi_help_request(self):
        result = transliterate_text("क्या आप मेरी मदद कर सकते हैं?")
        self.assertEqual(result, "Kya aap meri madad kar sakte hain?")
        self.assertTrue(is_pure_ascii(result))

    def test_hindi_mixed_coding(self):
        result = transliterate_text("मैं coding कर रहा हूँ।")
        self.assertEqual(result, "Main coding kar raha hoon.")
        self.assertTrue(is_pure_ascii(result))


class TestEnglishPreservation(unittest.TestCase):
    """Test English text remains unchanged without translation."""

    def test_english_sentences(self):
        self.assertEqual(transliterate_text("How are you?"), "How are you?")
        self.assertEqual(transliterate_text("I am learning Telugu."), "I am learning Telugu.")
        self.assertEqual(transliterate_text("Official OpenShorts automation pipeline."), "Official OpenShorts automation pipeline.")


class TestStrictCharacterValidation(unittest.TestCase):
    """Test strict ASCII / English alphabet-only enforcement."""

    def test_no_telugu_unicode(self):
        result = transliterate_text("నువ్వు ఎలా ఉన్నావు? నేను బాగున్నాను.")
        self.assertFalse(has_telugu(result))
        self.assertTrue(is_pure_ascii(result))

    def test_no_devanagari_unicode(self):
        result = transliterate_text("आप कैसे हो? मुझे यह बहुत पसंद है।")
        self.assertFalse(has_devanagari(result))
        self.assertTrue(is_pure_ascii(result))

    def test_sanitize_unicode_quotes_and_dandas(self):
        text = "‘Hello’ “World” — Hindi। Telugu॥"
        sanitized = sanitize_to_ascii(text)
        self.assertTrue(is_pure_ascii(sanitized))
        self.assertNotIn("।", sanitized)
        self.assertNotIn("॥", sanitized)


class TestTranscriptTransliteration(unittest.TestCase):
    """Test that full transcript structures retain all timing coordinates."""

    def test_preserve_word_timestamps(self):
        mock_transcript = {
            "text": "నువ్వు ఎలా ఉన్నావు?",
            "language": "te",
            "segments": [
                {
                    "start": 0.5,
                    "end": 2.5,
                    "text": "నువ్వు ఎలా ఉన్నావు?",
                    "words": [
                        {"word": "నువ్వు", "start": 0.5, "end": 1.0},
                        {"word": "ఎలా", "start": 1.1, "end": 1.7},
                        {"word": "ఉన్నావు?", "start": 1.8, "end": 2.5},
                    ]
                }
            ]
        }

        result = transliterate_transcript(mock_transcript, script_mode="romanized")

        # Verify timestamps are 100% identical
        self.assertEqual(result["segments"][0]["start"], 0.5)
        self.assertEqual(result["segments"][0]["end"], 2.5)
        self.assertEqual(result["segments"][0]["words"][0]["start"], 0.5)
        self.assertEqual(result["segments"][0]["words"][0]["end"], 1.0)
        self.assertEqual(result["segments"][0]["words"][1]["start"], 1.1)
        self.assertEqual(result["segments"][0]["words"][1]["end"], 1.7)
        self.assertEqual(result["segments"][0]["words"][2]["start"], 1.8)
        self.assertEqual(result["segments"][0]["words"][2]["end"], 2.5)

        # Verify text is pure Romanized ASCII
        self.assertFalse(has_telugu(result["text"]))
        self.assertTrue(is_pure_ascii(result["text"]))


class TestASSFormattingAndKaraoke(unittest.TestCase):
    """Test ASS file validation and karaoke tag preservation."""

    def test_ass_dialogue_tag_preservation(self):
        line = r"{\an5}{\c&HFFE500&}నువ్వు{\r} ఎలా ఉన్నావు?"
        valid, cleaned, errors = validate_ass_text_content(line, mode="romanized")
        self.assertTrue(valid)
        self.assertIn(r"{\an5}", cleaned)
        self.assertIn(r"{\c&HFFE500&}", cleaned)
        self.assertIn(r"{\r}", cleaned)
        self.assertFalse(has_telugu(cleaned))
        self.assertTrue(is_pure_ascii(cleaned))

    def test_full_ass_file_validation(self):
        sample_ass = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "PlayResY: 288\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.50,Default,,0,0,0,,{\\an5}నేను coding చేస్తున్నాను.\n"
            "Dialogue: 0,0:00:02.50,0:00:04.00,Default,,0,0,0,,{\\an5}आप कैसे हो?\n"
            "Dialogue: 0,0:00:04.00,0:00:05.50,Default,,0,0,0,,{\\an5}How are you?\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ass", encoding="utf-8", delete=False) as f:
            f.write(sample_ass)
            temp_path = f.name

        try:
            validate_and_sanitize_ass_file(temp_path, mode="romanized")
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("Nenu coding chestunnanu.", content)
            self.assertIn("Aap kaise ho?", content)
            self.assertIn("How are you?", content)
            self.assertTrue(is_pure_ascii(content))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
