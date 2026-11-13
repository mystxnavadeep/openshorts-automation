"""
OpenShorts Indic & Multilingual Transliteration Engine
Provides automatic language detection and transliteration for:
  - Telugu ("te") -> Pure Tenglish (Roman Telugu using ONLY English letters)
  - Hindi ("hi")   -> Pure Hinglish (Roman Hindi using ONLY English letters)
  - English ("en") -> Pure English subtitles (preserved unchanged)
  - Code-mixed speech (e.g. Telugu-English "నేను coding చేస్తున్నాను", Hindi-English "मैं coding कर रहा हूँ")

Strict Rule: Transliteration ONLY, NOT translation.
Preserves grammar, vocabulary, word-level timestamps, and sentence synchronization.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

try:
    import anyascii
    _HAS_ANYASCII = True
except ImportError:
    _HAS_ANYASCII = False


# ============================================================================
# TELUGU SCRIPT PHONETIC DEFINITIONS (U+0C00 - U+0C7F)
# ============================================================================

TELUGU_VOWELS = {
    '\u0C05': 'a', '\u0C06': 'aa', '\u0C07': 'i', '\u0C08': 'ee',
    '\u0C09': 'u', '\u0C0A': 'oo', '\u0C0B': 'ru', '\u0C60': 'roo',
    '\u0C0E': 'e', '\u0C0F': 'e', '\u0C10': 'ai',
    '\u0C12': 'o', '\u0C13': 'o', '\u0C14': 'au'
}

TELUGU_MATRAS = {
    '\u0C3E': 'aa', '\u0C3F': 'i', '\u0C40': 'ee',
    '\u0C41': 'u', '\u0C42': 'oo', '\u0C43': 'ru', '\u0C44': 'roo',
    '\u0C46': 'e', '\u0C47': 'e', '\u0C48': 'ai',
    '\u0C4A': 'o', '\u0C4B': 'o', '\u0C4C': 'au'
}

TELUGU_CONSONANTS = {
    '\u0C15': 'k', '\u0C16': 'kh', '\u0C17': 'g', '\u0C18': 'gh', '\u0C19': 'ng',
    '\u0C1A': 'ch', '\u0C1B': 'chh', '\u0C1C': 'j', '\u0C1D': 'jh', '\u0C1E': 'ny',
    '\u0C1F': 't', '\u0C20': 'th', '\u0C21': 'd', '\u0C22': 'dh', '\u0C23': 'n',
    '\u0C24': 't', '\u0C25': 'th', '\u0C26': 'd', '\u0C27': 'dh', '\u0C28': 'n',
    '\u0C2A': 'p', '\u0C2B': 'ph', '\u0C2C': 'b', '\u0C2D': 'bh', '\u0C2E': 'm',
    '\u0C2F': 'y', '\u0C30': 'r', '\u0C31': 'r', '\u0C32': 'l', '\u0C33': 'l',
    '\u0C35': 'v', '\u0C36': 'sh', '\u0C37': 'sh', '\u0C38': 's', '\u0C39': 'h'
}

# ============================================================================
# DEVANAGARI SCRIPT PHONETIC DEFINITIONS (U+0900 - U+097F)
# ============================================================================

DEVA_VOWELS = {
    '\u0905': 'a', '\u0906': 'aa', '\u0907': 'i', '\u0908': 'ee',
    '\u0909': 'u', '\u090A': 'oo', '\u090B': 'ri',
    '\u090F': 'e', '\u0910': 'ai', '\u0913': 'o', '\u0914': 'au'
}

DEVA_MATRAS = {
    '\u093E': 'aa', '\u093F': 'i', '\u0940': 'ee',
    '\u0941': 'u', '\u0942': 'oo', '\u0943': 'ri',
    '\u0947': 'e', '\u0948': 'ai', '\u094B': 'o', '\u094C': 'au'
}

DEVA_CONSONANTS = {
    '\u0915': 'k', '\u0916': 'kh', '\u0917': 'g', '\u0918': 'gh', '\u0919': 'ng',
    '\u091A': 'ch', '\u091B': 'chh', '\u091C': 'j', '\u091D': 'jh', '\u091E': 'ny',
    '\u091F': 't', '\u0920': 'th', '\u0921': 'd', '\u0922': 'dh', '\u0923': 'n',
    '\u0924': 't', '\u0925': 'th', '\u0926': 'd', '\u0927': 'dh', '\u0928': 'n',
    '\u092A': 'p', '\u092B': 'ph', '\u092C': 'b', '\u092D': 'bh', '\u092E': 'm',
    '\u092F': 'y', '\u0930': 'r', '\u0932': 'l', '\u0935': 'v',
    '\u0936': 'sh', '\u0937': 'sh', '\u0938': 's', '\u0939': 'h',
    '\u0958': 'q', '\u0959': 'kh', '\u095A': 'gh', '\u095B': 'z',
    '\u095C': 'r', '\u095D': 'rh', '\u095E': 'f'
}

LABIALS = {
    '\u0C2A', '\u0C2B', '\u0C2C', '\u0C2D', '\u0C2E',
    '\u092A', '\u092B', '\u092C', '\u092D', '\u092E'
}

# High-frequency natural conversational lexicon for colloquial perfection
TELUGU_COLLOQUIAL_LEXICON = {
    'నువ్వు': 'nuvvu',
    'నువ్వా': 'nuvva',
    'ఎలా': 'ela',
    'ఎలాగ': 'elaaga',
    'ఉన్నావు': 'unnavu',
    'ఉన్నావా': 'unnava',
    'ఉన్నారా': 'unnara',
    'ఉన్నాను': 'unnanu',
    'ఉంది': 'undi',
    'ఉన్నాడు': 'unnadu',
    'ఉన్నారు': 'unnaru',
    'ఉండండి': 'undandi',
    'నేను': 'nenu',
    'నాకు': 'naaku',
    'నాతో': 'naatho',
    'నన్ను': 'nannu',
    'బాగున్నాను': 'baagunnanu',
    'బాగున్నారా': 'baagunnara',
    'బాగుంది': 'baagundi',
    'బాగున్నాయి': 'baagunnayi',
    'ఇది': 'idi',
    'ఇలా': 'ila',
    'ఇక్కడ': 'ikkada',
    'ఇప్పుడు': 'ippudu',
    'ఇవ్వండి': 'ivvandi',
    'చాలా': 'chaala',
    'చేస్తున్నాను': 'chestunnanu',
    'చేస్తున్నా': 'chestunna',
    'చేస్తున్నారా': 'chestunnara',
    'చేస్తున్నాడు': 'chestunnadu',
    'చేస్తున్నారు': 'chestunnaru',
    'చేయండి': 'cheyandi',
    'చేస్తాను': 'chestanu',
    'ఏంటి': 'enti',
    'ఏమిటి': 'emiti',
    'ఎందుకు': 'enduku',
    'ఎక్కడ': 'ekkada',
    'ఎప్పుడు': 'eppudu',
    'ఎవరు': 'evaru',
    'ఎవరికి': 'evariki',
    'వస్తున్నాను': 'vastunnanu',
    'వస్తున్నారు': 'vastunnaru',
    'రండి': 'randi',
    'రా': 'raa',
    'వెళ్తున్నాను': 'veltunnanu',
    'వెళ్లండి': 'vellandi',
    'వెళ్లు': 'vellu',
    'చెప్పు': 'cheppu',
    'చెప్పండి': 'cheppandi',
    'అవును': 'avunu',
    'కాదు': 'kaadu',
    'లేదు': 'ledu',
    'మీరు': 'meeru',
    'మీకు': 'meeku',
    'మన': 'mana',
    'మనం': 'manam',
    'మాకు': 'maaku',
    'మాతో': 'maatho',
    'అందరికీ': 'andariki',
    'అందరూ': 'andaru',
    'నమస్కారం': 'namaskaram',
    'ధన్యవాదాలు': 'dhanyavaadaalu',
    'మరియు': 'mariyu',
    'కానీ': 'kaani',
    'అయితే': 'aithe',
    'కోసం': 'kosam',
    'చూడండి': 'choodandi',
    'చూడు': 'choodu',
    'వినండి': 'vinandi',
    'తెలుసా': 'telusa',
    'తెలుసు': 'telusu',
    'తెలియదు': 'teliyadu',
}

HINDI_COLLOQUIAL_LEXICON = {
    'आप': 'aap',
    'आपको': 'aapko',
    'आपका': 'aapka',
    'आपकी': 'aapki',
    'आपके': 'aapke',
    'कैसे': 'kaise',
    'कैसा': 'kaisa',
    'कैसी': 'kaisi',
    'हो': 'ho',
    'मुझे': 'mujhe',
    'मुझसे': 'mujhse',
    'मेरा': 'mera',
    'मेरी': 'meri',
    'मेरे': 'mere',
    'यह': 'yah',
    'ये': 'ye',
    'वह': 'vah',
    'वो': 'woh',
    'बहुत': 'bahut',
    'पसंद': 'pasand',
    'है': 'hai',
    'हैं': 'hain',
    'क्या': 'kya',
    'क्यों': 'kyun',
    'कहाँ': 'kahan',
    'कब': 'kab',
    'कौन': 'kaun',
    'मदद': 'madad',
    'कर': 'kar',
    'करो': 'karo',
    'कीजिए': 'kijiye',
    'सकते': 'sakte',
    'सकता': 'sakta',
    'सकती': 'sakti',
    'मैं': 'main',
    'हम': 'hum',
    'रहा': 'raha',
    'रही': 'rahi',
    'रहे': 'rahe',
    'हूँ': 'hoon',
    'हू': 'hoon',
    'नहीं': 'nahin',
    'हाँ': 'haan',
    'नमस्ते': 'namaste',
    'धन्यवाद': 'dhanyavad',
    'शुक्रिया': 'shukriya',
    'दोस्त': 'dost',
    'दोस्तों': 'doston',
    'लोग': 'log',
    'लोगों': 'logon',
    'बात': 'baat',
    'काम': 'kaam',
    'समय': 'samay',
    'दिन': 'din',
    'घर': 'ghar',
    'देख': 'dekh',
    'देखो': 'dekho',
    'देखिए': 'dekhiye',
    'सुन': 'sun',
    'सुनो': 'suno',
    'जानिए': 'jaaniye',
    'अच्छा': 'achha',
    'अच्छी': 'achhi',
    'अच्छे': 'achhe',
    'लेकिन': 'lekin',
    'अगर': 'agar',
    'क्योंकि': 'kyunki',
    'सब': 'sab',
    'सभी': 'sabhi',
    'था': 'tha',
    'थी': 'thi',
    'थे': 'the',
}


# ============================================================================
# LANGUAGE DETECTION
# ============================================================================

def has_telugu(text: str) -> bool:
    """Check if string contains any Telugu Unicode characters."""
    return any(0x0C00 <= ord(c) <= 0x0C7F for c in text)


def has_devanagari(text: str) -> bool:
    """Check if string contains any Devanagari Unicode characters."""
    return any(0x0900 <= ord(c) <= 0x097F for c in text)


def detect_language(text: str, asr_hint: Optional[str] = None) -> str:
    """
    Detect the primary spoken language of the audio/text.
    Returns: 'te' (Telugu), 'hi' (Hindi), or 'en' (English).
    """
    # 1. Script-based inspection on actual transcribed words (ground truth)
    te_count = sum(1 for c in text if 0x0C00 <= ord(c) <= 0x0C7F)
    hi_count = sum(1 for c in text if 0x0900 <= ord(c) <= 0x097F)

    if te_count > 0 and te_count >= hi_count:
        return "te"
    if hi_count > 0 and hi_count > te_count:
        return "hi"

    # 2. Check ASR hint if no Indic scripts present
    if asr_hint:
        hint = str(asr_hint).lower().strip()
        if hint in ("te", "telugu"):
            return "te"
        if hint in ("hi", "hindi"):
            return "hi"
        if hint in ("en", "english"):
            return "en"

    # Default to English
    return "en"


# ============================================================================
# ALGORITHMIC TRANSLITERATORS
# ============================================================================

def transliterate_telugu_core(core: str) -> str:
    """Convert Telugu Unicode characters to phonetic English letters (Tenglish)."""
    if core in TELUGU_COLLOQUIAL_LEXICON:
        return TELUGU_COLLOQUIAL_LEXICON[core]

    res = []
    i = 0
    n = len(core)
    while i < n:
        c = core[i]
        if c in TELUGU_VOWELS:
            res.append(TELUGU_VOWELS[c])
            i += 1
        elif c in TELUGU_CONSONANTS:
            cons = TELUGU_CONSONANTS[c]
            if i + 1 < n:
                nxt = core[i + 1]
                if nxt == '\u0C4D':  # Virama (pollu)
                    res.append(cons)
                    i += 2
                elif nxt in TELUGU_MATRAS:
                    res.append(cons + TELUGU_MATRAS[nxt])
                    i += 2
                elif nxt == '\u0C02':  # Anusvara attached to consonant
                    if i + 2 < n and core[i + 2] in LABIALS:
                        res.append(cons + 'am')
                    elif i + 2 >= n:
                        res.append(cons + 'am')
                    else:
                        res.append(cons + 'an')
                    i += 2
                else:
                    res.append(cons + 'a')
                    i += 1
            else:
                res.append(cons + 'a')
                i += 1
        elif c == '\u0C02':  # Standalone Anusvara
            if i + 1 < n and core[i + 1] in LABIALS:
                res.append('m')
            elif i + 1 >= n:
                res.append('m')
            else:
                res.append('n')
            i += 1
        elif c == '\u0C03':  # Visarga
            res.append('h')
            i += 1
        else:
            # Fallback for numbers, symbols
            if _HAS_ANYASCII and ord(c) > 127:
                res.append(anyascii.anyascii(c))
            else:
                res.append(c)
            i += 1

    trans = ''.join(res)

    # Normalize double vowel at end for natural conversational Tenglish
    # e.g., 'unnavu' / 'unnava' rather than 'unnaavuu'
    if trans.endswith('aa') and len(trans) > 3 and not trans.endswith('chaa'):
        trans = trans[:-1]

    return trans


def transliterate_hindi_core(core: str) -> str:
    """Convert Devanagari characters to natural Roman Hindi (Hinglish)."""
    if core in HINDI_COLLOQUIAL_LEXICON:
        return HINDI_COLLOQUIAL_LEXICON[core]

    res = []
    i = 0
    n = len(core)
    while i < n:
        c = core[i]
        if c in DEVA_VOWELS:
            res.append(DEVA_VOWELS[c])
            i += 1
        elif c in DEVA_CONSONANTS:
            cons = DEVA_CONSONANTS[c]
            if i + 1 < n:
                nxt = core[i + 1]
                if nxt == '\u094D':  # Halant
                    res.append(cons)
                    i += 2
                elif nxt in DEVA_MATRAS:
                    res.append(cons + DEVA_MATRAS[nxt])
                    i += 2
                elif nxt in ('\u0902', '\u0901'):  # Anusvara / Candrabindu
                    res.append(cons + 'an')
                    i += 2
                else:
                    # Hindi schwa deletion logic
                    if i + 1 == n - 1 and core[i + 1] in DEVA_CONSONANTS:
                        # 2-consonant word e.g. kar -> ka + r
                        res.append(cons + 'a')
                    elif i + 2 == n and core[i + 1] in DEVA_CONSONANTS:
                        # 3-consonant word e.g. madad -> ma + da + d
                        res.append(cons + 'a')
                    elif i + 1 >= n - 1:
                        # Word-final consonant drops schwa in modern Hindi
                        res.append(cons)
                    else:
                        res.append(cons + 'a')
                    i += 1
            else:
                # Word-final consonant: schwa deleted in Hindi
                res.append(cons)
                i += 1
        elif c in ('\u0902', '\u0901'):
            res.append('n')
            i += 1
        elif c == '\u0903':
            res.append('h')
            i += 1
        else:
            if _HAS_ANYASCII and ord(c) > 127:
                res.append(anyascii.anyascii(c))
            else:
                res.append(c)
            i += 1

    return ''.join(res)


# ============================================================================
# TOKEN & WORD LEVEL TRANSLITERATION
# ============================================================================

def transliterate_word(token: str, lang_override: Optional[str] = None) -> str:
    """
    Transliterate a single word or token into pure English/Roman letters.
    - Preserves surrounding punctuation (e.g., '?', '.', ',', '!', '"').
    - English words are preserved untouched.
    - Mixed words (e.g. 'coding') remain in Latin script.
    - Replaces Hindi danda '।' with English period '.'.
    """
    if not token:
        return ""

    # Normalize Hindi/Indic dandas to standard English periods
    token = token.replace('।', '.').replace('॥', '.')

    # Separate leading/trailing punctuation
    # Regex separates non-word prefix, core word, non-word suffix
    m = re.match(r'^([^ఀ-౿ऀ-ॿa-zA-Z0-9]*)(.*?)([^ఀ-౿ऀ-ॿa-zA-Z0-9]*)$', token)
    if m:
        lead, core, trail = m.groups()
    else:
        lead, core, trail = '', token, ''

    # Normalize Hindi danda
    trail = trail.replace('।', '.')

    if not core:
        return lead + trail

    # 1. Pure ASCII / Latin word -> Keep exactly as is (e.g. 'coding', 'YouTube', 'How')
    if all(ord(c) < 128 for c in core):
        return lead + core + trail

    # 2. Check if Telugu script
    if has_telugu(core):
        # Special conversational question inflection: e.g. 'ఉన్నావు' with '?' -> 'unnavu' or 'unnava'
        if core == 'ఉన్నావు' and '?' in trail:
            trans = 'unnava'
        else:
            trans = transliterate_telugu_core(core)
        return lead + trans + trail

    # 3. Check if Devanagari script
    if has_devanagari(core):
        trans = transliterate_hindi_core(core)
        return lead + trans + trail

    # 4. Fallback for any other non-Latin characters
    if _HAS_ANYASCII:
        trans = anyascii.anyascii(core)
    else:
        trans = "".join(c for c in unicodedata.normalize('NFKD', core) if ord(c) < 128)

    return lead + trans + trail


# ============================================================================
# SENTENCE & TEXT LEVEL TRANSLITERATION
# ============================================================================

def transliterate_text(text: str, lang: Optional[str] = None) -> str:
    """
    Transliterate a full sentence or paragraph into natural Romanized subtitles.
    Preserves English words, punctuation, whitespace, and sentence casing.
    """
    if not text:
        return ""

    # Preserve leading/trailing whitespace
    lead_ws = text[:len(text) - len(text.lstrip())]
    trail_ws = text[len(text.rstrip()):] if text.rstrip() else ""

    clean_text = text.replace('।', '.').replace('॥', '.')
    tokens = clean_text.split()
    if not tokens:
        return text

    trans_tokens = [transliterate_word(tok, lang_override=lang) for tok in tokens]

    # Sentence casing: Capitalize first word of sentence and after period/question/exclamation
    res = []
    for i, w in enumerate(trans_tokens):
        if not w:
            continue
        if i == 0 or (res and res[-1].endswith(('.', '?', '!'))):
            # Capitalize the first alphabetical character
            for idx, ch in enumerate(w):
                if ch.isalpha():
                    w = w[:idx] + ch.upper() + w[idx + 1:]
                    break
        res.append(w)

    return lead_ws + ' '.join(res) + trail_ws


# ============================================================================
# TRANSCRIPT INTEGRATION
# ============================================================================

def transliterate_transcript(transcript: dict,
                             target_lang: str = "auto",
                             script_mode: str = "romanized") -> dict:
    """
    Transform a complete Faster-Whisper transcript data structure:
    - Automatically detects spoken language if target_lang is 'auto'.
    - If script_mode == 'romanized':
        Transliterates every word in segment['words'] with timestamps preserved.
        Reconstructs segment['text'] and transcript['text'].
    - Enforces pure English alphabet validation.
    """
    if not transcript or not transcript.get("segments"):
        return transcript

    # Detect language
    full_original_text = transcript.get("text", "")
    detected = detect_language(full_original_text, asr_hint=transcript.get("language"))
    effective_lang = detected if target_lang == "auto" else target_lang

    transcript["detected_language"] = detected
    transcript["effective_language"] = effective_lang
    transcript["subtitle_script"] = script_mode

    # If user selected original script, do not transliterate
    if script_mode == "original":
        return transcript

    # Transliterate each word and segment
    new_segments = []
    all_text_parts = []

    for seg in transcript["segments"]:
        new_words = []
        seg_word_texts = []
        for w in seg.get("words", []):
            orig_word = w.get("word", "")
            # Preserve leading space boundary marker if present
            has_leading_space = orig_word.startswith(" ")
            cleaned_word = orig_word.strip()

            trans_word = transliterate_word(cleaned_word, lang_override=effective_lang)
            final_word = (" " + trans_word) if has_leading_space else trans_word

            new_words.append({
                "word": final_word,
                "start": float(w.get("start", 0.0)),
                "end": float(w.get("end", 0.0)),
            })
            seg_word_texts.append(trans_word)

        new_seg_text = transliterate_text(seg.get("text", ""), lang=effective_lang)
        new_segments.append({
            "start": float(seg.get("start", 0.0)),
            "end": float(seg.get("end", 0.0)),
            "text": new_seg_text,
            "words": new_words,
        })
        all_text_parts.append(new_seg_text)

    transcript["segments"] = new_segments
    transcript["text"] = " ".join(part for part in all_text_parts if part)
    return transcript


# ============================================================================
# ASCII & STRICT VALIDATION HELPERS
# ============================================================================

def is_pure_ascii(text: str) -> bool:
    """Return True if text contains only standard ASCII characters."""
    return all(ord(c) < 128 for c in text)


def sanitize_to_ascii(text: str) -> str:
    """
    Sanitize text to strictly ASCII characters:
    - Normalizes smart quotes, em-dashes, non-breaking spaces.
    - Transliterates any remaining Unicode characters.
    - Strips disallowed characters.
    """
    # Replace common typographic Unicode characters
    replacements = {
        '\u2018': "'", '\u2019': "'",
        '\u201C': '"', '\u201D': '"',
        '\u2013': '-', '\u2014': '-',
        '\u2026': '...',
        '\u00A0': ' ',
        '।': '.',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # First pass: transliterate if Indic scripts remain
    if has_telugu(text) or has_devanagari(text):
        text = transliterate_text(text)

    # Second pass: anyascii or unicodedata normalization
    if not is_pure_ascii(text):
        if _HAS_ANYASCII:
            text = anyascii.anyascii(text)
        else:
            text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')

    # Final guarantee: filter to allowed character set
    # English A-Z, a-z, 0-9, basic English punctuation: . , ? ! ' " : ; - ( ) / % $ # @ & + =
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,?!'\"-:;()[]/\\%&$#@_+=~*<>`\r\n\t")
    return "".join(c for c in text if c in allowed)
