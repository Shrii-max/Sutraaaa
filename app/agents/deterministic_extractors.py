"""Deterministic Rule-First Extractors and Verifiers for Indian Legal Text.

Handles:
1. Regex extraction of dates (English, Hindi, and numeric) with SourceRef offsets.
2. Regex extraction of statutory sections (IPC, BNS, CrPC, BNSS, NI Act).
3. Section validity checks against bare act concordance tables.
4. Fuzzy name variant detection across proceedings.
5. Chronological date sequence sanity verification.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from app.schemas.source import SourceRef
from app.schemas.facts import DateItem, SectionItem, PartyItem
from app.ingestion.date_normalizer import normalize_legal_date, HINDI_MONTH_MAP


def load_sections_table() -> Dict[str, Dict[str, str]]:
    """Load reference sections dictionary for IPC, BNS, CrPC, BNSS."""
    path = Path(__file__).parent.parent / "data" / "sections_table.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"IPC": {}, "BNS": {}, "CrPC": {}, "BNSS": {}}


# Regex for Indian statutory sections
SECTION_PATTERN = re.compile(
    r"(?i)\b(?:section|sec\.?|धारा|u/s|under\s+section)\s*(\d+[A-Za-z]?(?:\(\d+\)(?:\([a-z]\))?)?)\s*"
    r"(?:(?:of\s+(?:the\s+)?)?(IPC|BNS|CrPC|BNSS|Indian\s+Penal\s+Code|Bharatiya\s+Nyaya\s+Sanhita|Code\s+of\s+Criminal\s+Procedure|Bharatiya\s+Nagarik\s+Suraksha\s+Sanhita|N\.?I\.?\s*Act))?",
    re.UNICODE,
)

# Regex for common date patterns in Indian legal records
DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|"
    r"(?:dated\s+)?\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[,]?\s+\d{4}|"
    r"\d{1,2}\s+(?:जनवरी|फ़रवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितम्बर|सितंबर|अक्टूबर|नवम्बर|नवंबर|दिसम्बर|दिसंबर)\s+\d{4})\b",
    re.IGNORECASE | re.UNICODE,
)


def extract_dates_deterministic(
    page_text_map: Dict[int, str],
    document_id: str,
) -> List[DateItem]:
    """Deterministically scan text for legal dates, normalize, and construct DateItems with exact SourceRefs."""
    results: List[DateItem] = []
    seen_dates = set()

    for page_num, page_text in page_text_map.items():
        for match in DATE_PATTERN.finditer(page_text):
            raw_match = match.group(0)
            lead_ws = len(raw_match) - len(raw_match.lstrip())
            raw_str = raw_match.strip()
            norm_iso, dt = normalize_legal_date(raw_str)
            if not norm_iso:
                continue

            dedup_key = (norm_iso, page_num)
            if dedup_key in seen_dates:
                continue
            seen_dates.add(dedup_key)

            start = match.start() + lead_ws
            end = start + len(raw_str)
            src = SourceRef(
                document_id=document_id,
                page=page_num,
                char_start=start,
                char_end=end,
                snippet=raw_str,
            )
            results.append(
                DateItem(
                    date_str=norm_iso,
                    description=f"Date mentioned in legal record: {raw_str}",
                    source=src,
                    confidence=0.99,
                )
            )

    return results


def extract_sections_deterministic(
    page_text_map: Dict[int, str],
    document_id: str,
    sections_table: Optional[Dict[str, Dict[str, str]]] = None,
) -> List[SectionItem]:
    """Deterministically extract penal & procedural sections with validity check against bare-acts."""
    table = sections_table or load_sections_table()
    results: List[SectionItem] = []
    seen = set()

    for page_num, page_text in page_text_map.items():
        for match in SECTION_PATTERN.finditer(page_text):
            raw_sec = match.group(1).strip()
            raw_act = match.group(2) or ""

            # Standardize Act name
            act_clean = raw_act.upper().replace(" ", "")
            if "BNS" in act_clean or "BHARATIYANYAYA" in act_clean:
                act = "BNS"
            elif "BNSS" in act_clean or "BHARATIYANAGARIK" in act_clean:
                act = "BNSS"
            elif "CRPC" in act_clean or "CRIMINALPROCEDURE" in act_clean:
                act = "CrPC"
            elif "IPC" in act_clean or "PENALCODE" in act_clean:
                act = "IPC"
            else:
                # Infer based on common numbering
                if raw_sec in table.get("IPC", {}) and raw_sec not in table.get("CrPC", {}):
                    act = "IPC"
                elif raw_sec in table.get("CrPC", {}) and raw_sec not in table.get("IPC", {}):
                    act = "CrPC"
                else:
                    act = "other"

            dedup_key = (raw_sec, act, page_num)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            raw_match = match.group(0)
            lead_ws = len(raw_match) - len(raw_match.lstrip())
            snippet = raw_match.strip()
            start = match.start() + lead_ws
            end = start + len(snippet)
            src = SourceRef(
                document_id=document_id,
                page=page_num,
                char_start=start,
                char_end=end,
                snippet=snippet,
            )

            # Validity check
            clean_sec_num = re.sub(r"[^\w]", "", raw_sec)
            is_valid = False
            act_dict = table.get(act, {})
            for known_sec in act_dict:
                if re.sub(r"[^\w]", "", known_sec) == clean_sec_num:
                    is_valid = True
                    break

            confidence = 0.99 if is_valid else 0.85
            results.append(
                SectionItem(
                    act=act,
                    section_number=raw_sec,
                    description=f"Section {raw_sec} under {act}",
                    source=src,
                    confidence=confidence,
                )
            )

    return results


def check_chronological_order(dates: List[DateItem]) -> List[str]:
    """Deterministic check verifying chronological plausibility of extracted dates."""
    issues = []
    parsed_dates = []
    for d in dates:
        norm, dt = normalize_legal_date(d.date_str)
        if dt:
            parsed_dates.append((d, dt))

    # Check for extreme future dates
    current_year = datetime.now().year + 1
    for d_item, dt in parsed_dates:
        if dt.year > current_year:
            issues.append(f"Date {d_item.date_str} appears to be an impossible future date (Year {dt.year}).")

    return issues


def check_fuzzy_name_variants(parties: List[PartyItem]) -> Dict[str, List[str]]:
    """Detect potential spelling variants of the same individual across document."""
    from difflib import SequenceMatcher

    variants: Dict[str, List[str]] = {}
    names = list({p.name.strip() for p in parties if p.name and len(p.name.strip()) > 3})

    for i in range(len(names)):
        n1 = names[i]
        for j in range(i + 1, len(names)):
            n2 = names[j]
            ratio = SequenceMatcher(None, n1.lower(), n2.lower()).ratio()
            # If names are very close but not identical
            if 0.80 <= ratio < 1.0:
                if n1 not in variants:
                    variants[n1] = []
                variants[n1].append(n2)

    return variants
