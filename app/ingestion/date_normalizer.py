"""Indian legal date parsing and normalization engine.

Handles:
- Numeric formats: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, YYYY-MM-DD
- English textual formats: 'dated 5th of March, 2023', '15th March 2023', 'March 15, 2023'
- Hindi Devanagari month formats: '15 मार्च 2023', 'दिनांक 20 जनवरी 2024', '12 फ़रवरी 2023'
- Ordinal indicators: 1st, 2nd, 3rd, 4th, 5th, etc.
"""

import re
from datetime import datetime
from typing import Optional, Tuple

HINDI_MONTH_MAP = {
    "जनवरी": "01",
    "फ़रवरी": "02",
    "फरवरी": "02",
    "मार्च": "03",
    "अप्रैल": "04",
    "मई": "05",
    "जून": "06",
    "जुलाई": "07",
    "अगस्त": "08",
    "सितम्बर": "09",
    "सितंबर": "09",
    "अक्टूबर": "10",
    "नवम्बर": "11",
    "नवंबर": "11",
    "दिसम्बर": "12",
    "दिसंबर": "12",
}

ENGLISH_MONTH_MAP = {
    "january": "01", "jan": "01",
    "february": "02", "feb": "02",
    "march": "03", "mar": "03",
    "april": "04", "apr": "04",
    "may": "05",
    "june": "06", "jun": "06",
    "july": "07", "jul": "07",
    "august": "08", "aug": "08",
    "september": "09", "sep": "09", "sept": "09",
    "october": "10", "oct": "10",
    "november": "11", "nov": "11",
    "december": "12", "dec": "12",
}


def normalize_legal_date(raw_date_str: str) -> Tuple[Optional[str], Optional[datetime]]:
    """Parse and normalize diverse Indian legal date representations into ISO YYYY-MM-DD.

    Returns:
        Tuple[Optional[str], Optional[datetime]]: (ISO_formatted_string, datetime_object)
    """
    if not raw_date_str or not isinstance(raw_date_str, str):
        return None, None

    text = raw_date_str.strip()
    if not text:
        return None, None

    # Remove boilerplate phrases like 'dated', 'दिनांक', 'on or about', 'the'
    text = re.sub(r"\b(?:dated|date|on\s+or\s+about|as\s+on|दिनांक|तारीख|the|day\s+of)\b", " ", text, flags=re.IGNORECASE)

    # 1. Check for Hindi month names
    for hi_month, mm in HINDI_MONTH_MAP.items():
        if hi_month in text:
            # Match patterns like: DD <HindiMonth> YYYY or <HindiMonth> DD, YYYY
            match = re.search(r"(\d{1,2})\s*" + re.escape(hi_month) + r"\s*[,.]?\s*(\d{4})", text)
            if match:
                day, year = int(match.group(1)), int(match.group(2))
                try:
                    dt = datetime(year, int(mm), day)
                    return dt.strftime("%Y-%m-%d"), dt
                except ValueError:
                    pass

            # Match year first or month first
            match_rev = re.search(re.escape(hi_month) + r"\s*(\d{1,2})\s*[,.]?\s*(\d{4})", text)
            if match_rev:
                day, year = int(match_rev.group(1)), int(match_rev.group(2))
                try:
                    dt = datetime(year, int(mm), day)
                    return dt.strftime("%Y-%m-%d"), dt
                except ValueError:
                    pass

    # 2. Check for English textual month names with optional ordinals (e.g. 5th of March, 2023)
    # Strip ordinal suffixes: 1st, 2nd, 3rd, 4th -> 1, 2, 3, 4
    cleaned_en = re.sub(r"(\d{1,2})(?:st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)
    cleaned_en = re.sub(r"\bof\b", " ", cleaned_en, flags=re.IGNORECASE)

    # Search for English month
    for en_month, mm in sorted(ENGLISH_MONTH_MAP.items(), key=lambda x: -len(x[0])):
        pattern_d_m_y = r"\b(\d{1,2})\s+" + re.escape(en_month) + r"\s*[,.]?\s*(\d{4})\b"
        m1 = re.search(pattern_d_m_y, cleaned_en, flags=re.IGNORECASE)
        if m1:
            day, year = int(m1.group(1)), int(m1.group(2))
            try:
                dt = datetime(year, int(mm), day)
                return dt.strftime("%Y-%m-%d"), dt
            except ValueError:
                pass

        pattern_m_d_y = r"\b" + re.escape(en_month) + r"\s+(\d{1,2})\s*[,.]?\s*(\d{4})\b"
        m2 = re.search(pattern_m_d_y, cleaned_en, flags=re.IGNORECASE)
        if m2:
            day, year = int(m2.group(1)), int(m2.group(2))
            try:
                dt = datetime(year, int(mm), day)
                return dt.strftime("%Y-%m-%d"), dt
            except ValueError:
                pass

    # 3. Numeric formats (DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, YYYY-MM-DD)
    numeric_clean = re.sub(r"[^\d/.-]", " ", text).strip()
    match_num = re.search(r"\b(\d{1,4})[./-](\d{1,2})[./-](\d{2,4})\b", numeric_clean)
    if match_num:
        p1, p2, p3 = match_num.group(1), match_num.group(2), match_num.group(3)

        # Case A: YYYY-MM-DD
        if len(p1) == 4:
            year, month, day = int(p1), int(p2), int(p3)
            try:
                dt = datetime(year, month, day)
                return dt.strftime("%Y-%m-%d"), dt
            except ValueError:
                pass

        # Case B: DD-MM-YYYY or DD/MM/YY
        if len(p3) == 4 or len(p3) == 2:
            day, month = int(p1), int(p2)
            year = int(p3) if len(p3) == 4 else (2000 + int(p3) if int(p3) < 50 else 1900 + int(p3))
            try:
                dt = datetime(year, month, day)
                return dt.strftime("%Y-%m-%d"), dt
            except ValueError:
                pass

    # 4. Standard ISO string parsing fallback
    for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y/%m/%d"]:
        try:
            dt = datetime.strptime(numeric_clean, fmt)
            return dt.strftime("%Y-%m-%d"), dt
        except ValueError:
            pass

    return None, None


def format_display_date(iso_date: str) -> str:
    """Format an ISO date string (YYYY-MM-DD) into standard Indian court display format."""
    if not iso_date or len(iso_date) < 10:
        return iso_date or "Undated"
    try:
        dt = datetime.strptime(iso_date[:10], "%Y-%m-%d")
        return dt.strftime("%d %b %Y")
    except Exception:
        return iso_date

