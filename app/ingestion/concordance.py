"""Statutory Concordance Mapping and Transition Validator (IPC <-> BNS, CrPC <-> BNSS).

Follows v2 Reliability Requirement 5:
Versioned `data/mappings/ipc_bns.json` and `crpc_bnss.json` with a validator.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class StatutoryConcordance:
    """Manages cross-reference lookups between historical and modern Indian criminal penal/procedural codes."""

    def __init__(self, mappings_dir: Optional[Path] = None):
        self.mappings_dir = mappings_dir or (Path(__file__).parent.parent.parent / "data" / "mappings")
        self.ipc_to_bns: Dict[str, Dict[str, Any]] = {}
        self.bns_to_ipc: Dict[str, Dict[str, Any]] = {}
        self.crpc_to_bnss: Dict[str, Dict[str, Any]] = {}
        self.bnss_to_crpc: Dict[str, Dict[str, Any]] = {}
        self._load_and_validate()

    def _load_and_validate(self) -> None:
        ipc_file = self.mappings_dir / "ipc_bns.json"
        crpc_file = self.mappings_dir / "crpc_bnss.json"

        if ipc_file.exists():
            try:
                data = json.loads(ipc_file.read_text(encoding="utf-8"))
                for item in data.get("mappings", []):
                    ipc_sec = str(item.get("ipc_section", "")).strip()
                    bns_sec = str(item.get("bns_section", "")).strip()
                    self.ipc_to_bns[ipc_sec] = item
                    self.bns_to_ipc[bns_sec] = item
            except Exception as e:
                logger.error(f"Failed to load IPC-BNS mapping: {e}")

        if crpc_file.exists():
            try:
                data = json.loads(crpc_file.read_text(encoding="utf-8"))
                for item in data.get("mappings", []):
                    crpc_sec = str(item.get("crpc_section", "")).strip()
                    bnss_sec = str(item.get("bnss_section", "")).strip()
                    self.crpc_to_bnss[crpc_sec] = item
                    self.bnss_to_crpc[bnss_sec] = item
            except Exception as e:
                logger.error(f"Failed to load CrPC-BNSS mapping: {e}")

    def lookup_bns(self, ipc_section: str) -> Optional[Dict[str, Any]]:
        clean_sec = ipc_section.strip().replace("Section", "").replace("sec", "").replace("धारा", "").strip()
        return self.ipc_to_bns.get(clean_sec)

    def lookup_bnss(self, crpc_section: str) -> Optional[Dict[str, Any]]:
        clean_sec = crpc_section.strip().replace("Section", "").replace("sec", "").replace("धारा", "").strip()
        return self.crpc_to_bnss.get(clean_sec)

    def validate_mappings(self) -> Tuple[bool, List[str]]:
        """Validate integrity, uniqueness, and completeness of concordance mapping files."""
        errors: List[str] = []
        ipc_file = self.mappings_dir / "ipc_bns.json"
        crpc_file = self.mappings_dir / "crpc_bnss.json"

        if not ipc_file.exists():
            errors.append(f"Missing concordance mapping file: {ipc_file}")
        else:
            try:
                d = json.loads(ipc_file.read_text(encoding="utf-8"))
                if not d.get("version"):
                    errors.append("ipc_bns.json missing 'version' key.")
                if not d.get("mappings"):
                    errors.append("ipc_bns.json 'mappings' list is empty.")
                seen = set()
                for m in d.get("mappings", []):
                    sec = m.get("ipc_section")
                    if not sec:
                        errors.append("ipc_bns.json mapping missing 'ipc_section'.")
                    if sec in seen:
                        errors.append(f"Duplicate IPC section in mapping: {sec}")
                    seen.add(sec)
            except Exception as e:
                errors.append(f"Invalid JSON in ipc_bns.json: {e}")

        if not crpc_file.exists():
            errors.append(f"Missing concordance mapping file: {crpc_file}")
        else:
            try:
                d = json.loads(crpc_file.read_text(encoding="utf-8"))
                if not d.get("version"):
                    errors.append("crpc_bnss.json missing 'version' key.")
                if not d.get("mappings"):
                    errors.append("crpc_bnss.json 'mappings' list is empty.")
                seen = set()
                for m in d.get("mappings", []):
                    sec = m.get("crpc_section")
                    if not sec:
                        errors.append("crpc_bnss.json mapping missing 'crpc_section'.")
                    if sec in seen:
                        errors.append(f"Duplicate CrPC section in mapping: {sec}")
                    seen.add(sec)
            except Exception as e:
                errors.append(f"Invalid JSON in crpc_bnss.json: {e}")

        is_valid = len(errors) == 0
        return is_valid, errors


_CONCORDANCE_INSTANCE: Optional[StatutoryConcordance] = None


def get_concordance() -> StatutoryConcordance:
    global _CONCORDANCE_INSTANCE
    if _CONCORDANCE_INSTANCE is None:
        _CONCORDANCE_INSTANCE = StatutoryConcordance()
    return _CONCORDANCE_INSTANCE

