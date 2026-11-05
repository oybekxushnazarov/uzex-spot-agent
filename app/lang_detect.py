# -*- coding: utf-8 -*-
"""Language detection, spam filter, and prompt injection defense."""

import re

UZBEK_LATIN_MARKERS = {
    "qancha", "nechta", "bitim", "bitimlar", "bitimi", "bitimni",
    "yil", "yili", "yilda", "narxi", "narx", "som", "so'm", "so‘m",
    "paxta", "shakar", "sement", "un", "bug'doy", "benzin", "moy", "yog'", "yog‘i",
    "bormi", "kim", "haqida", "sotilgan", "tuzilgan", "imzolangan",
    "bekor", "qilingan", "shartnoma", "barcha", "davr", "katta",
    "viloyat", "viloyati", "viloyatlarda", "shahri", "hudud", "hududlarda",
    "xaridor", "xaridorlar", "sotuvchi", "orqali", "korxona", "eng",
    "amalga", "oshirilgan", "yetkazib", "berish", "kechikish", "muddati",
    "buzilgan", "jami", "mavjud", "bolgan", "bo'lgan", "bo‘lgan",
    "bepul", "royxatga", "ro'yxatga", "ro‘yxatga", "olingan", "dona"
}

UZBEK_CYRILLIC_CHARS = set("ўқғҳЎҚҒҲ")

UZBEK_CYRILLIC_MARKERS = {
    "қанча", "нечта", "битим", "битимлар", "битими", "битимни",
    "йил", "йили", "йилда", "нархи", "нарх", "сўм", "сом",
    "пахта", "шакар", "семент", "ун", "буғдой", "бензин",
    "борми", "ким", "ҳақида", "сотилган", "тузилган", "имзоланган",
    "бекор", "қилинган", "шартнома", "барча", "давр", "катта",
    "вилоят", "вилояти", "вилоятларда", "шаҳри", "ҳудуд", "ҳудудларда",
    "харидор", "харидорлар", "сотувчи", "орқали", "корхона", "энг",
    "амалга", "оширилган", "етказиб", "бериш", "кечикиш", "муддати",
    "бузилган", "жами", "мавжуд", "бўлган", "рўйхатга", "олинган"
}

INJECTION_PATTERNS = [
    r"забудь\s+(?:все\s+)?инструкци",
    r"игнорируй\s+(?:все\s+)?правил",
    r"напиши\s*,\s*что\b",
    r"скажи\s*,\s*что\b",
    r"придумай\b",
    r"выдумай\b",
    r"barcha\s+qoidalarni\s+unut",
    r"ko['‘`]?rsatmalarni\s+unut",
    r"barcha\s+yo['‘`]?riqnomalarni\s+bekor\s+qil",
    r"ignore\s+(?:all\s+)?instructions",
    r"disregard\s+(?:all\s+)?rules",
    r"pretend\s+you\s+are",
    r"act\s+as\s+if",
    r"system\s*prompt",
    r"delete\s+from",
    r"drop\s+table",
]

def check_injection(text: str) -> bool:
    """Return True if prompt injection / jailbreak is detected."""
    t = text.lower()
    for pat in INJECTION_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return True
    return False

def is_empty_or_spam(text: str) -> tuple[bool, str]:
    """Validate query length and non-empty content."""
    if not text or not text.strip():
        return True, "EMPTY"
    t = text.strip()
    if len(t) > 2000:
        return True, "TOO_LONG"
    # Check if string contains alphanumeric characters
    if not re.search(r"[\w\d]", t, re.UNICODE):
        return True, "NO_TEXT"
    return False, ""

def detect_language(text: str) -> str:
    """Detect language of query: returns 'uz' or 'ru'."""
    t = text.lower()
    
    # 1. Uzbek apostrophes
    if any(ch in t for ch in ["o'", "g'", "o‘", "g‘", "oʻ", "gʻ", "o`", "g`"]):
        return "uz"
        
    # 2. Specific Uzbek Cyrillic letters
    if any(ch in UZBEK_CYRILLIC_CHARS for ch in t):
        return "uz"
        
    # 3. Tokenize words
    words = set(re.findall(r"[a-zа-яёўқғҳ\']+", t))
    
    # Check word intersection
    uz_lat_matches = len(words.intersection(UZBEK_LATIN_MARKERS))
    uz_cyr_matches = len(words.intersection(UZBEK_CYRILLIC_MARKERS))
    
    if uz_lat_matches > 0 or uz_cyr_matches > 0:
        return "uz"
        
    # Check Russian characters
    ru_chars = len(re.findall(r"[а-яё]", t))
    lat_chars = len(re.findall(r"[a-z]", t))
    
    if ru_chars > lat_chars:
        return "ru"
    elif lat_chars > ru_chars and uz_lat_matches > 0:
        return "uz"
        
    # Default to Russian if mostly Cyrillic, otherwise check for Latin Uzbek words
    return "ru"
