#!/usr/bin/env python3
"""Bulk backfill cutoff voltages in cellscope.db from archived source files.

This script supports two recovery paths:
1) Direct filename matching from DB cell file_name -> archive file.
2) Experiment-level inference: fuzzy-match experiment token (e.g. N10d, T29a)
   to one or more XLSX files and use a consensus cutoff pair for all cells.

Usage examples:
  python3 backfill_cutoff_voltages.py --db cellscope.db --roots "/path/to/archive"
  python3 backfill_cutoff_voltages.py --db cellscope.db --roots "/path/a" "/path/b" --apply

By default this runs in dry-run mode and prints what would change.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import warnings
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from data_processing import (
    detect_file_type,
)


SUPPORTED_EXTS = {".xlsx", ".csv"}
XLSX_EXT = ".xlsx"
STOPWORDS = {"repaired", "remake", "remakes", "fresh", "chip", "study", "sample", "first"}

# openpyxl emits this for some vendor files; harmless for our use-case.
warnings.filterwarnings(
    "ignore",
    message="Workbook contains no default style, apply openpyxl's default",
)


def tokenize(text: str) -> List[str]:
    """Tokenize into lowercase alphanumeric chunks."""
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def canonical_experiment_tag(exp_name: str) -> Optional[str]:
    """Extract canonical experiment tag (e.g. n10d, t29a, n9) from experiment name."""
    if not exp_name:
        return None
    m = re.search(r"\b([a-z]+\d+[a-z]?)\b", exp_name.lower())
    return m.group(1) if m else None


def normalize_pair(lower: Optional[float], upper: Optional[float]) -> Optional[Tuple[float, float]]:
    """Return validated (lower, upper) pair normalized as ascending rounded floats."""
    if lower is None or upper is None:
        return None
    try:
        v1 = float(lower)
        v2 = float(upper)
    except (TypeError, ValueError):
        return None

    lo = min(v1, v2)
    hi = max(v1, v2)
    if lo < 0.0 or hi > 10:
        return None
    return round(lo, 4), round(hi, 4)


def is_noise_file(path: Path) -> bool:
    """Ignore Office temp files and macOS resource-fork artifacts."""
    name = path.name
    return name.startswith("~$") or name.startswith("._")


def build_file_indexes(roots: List[str]) -> Tuple[Dict[str, List[Path]], List[Dict[str, object]]]:
    """Build lookup indexes for archive files.

    Returns:
        basename_index: lowercase basename -> candidate paths
        xlsx_catalog: list of dicts for XLSX with tokenized searchable text
    """
    basename_index: Dict[str, List[Path]] = defaultdict(list)
    xlsx_catalog: List[Dict[str, object]] = []

    for root in roots:
        root_path = Path(root).expanduser().resolve()
        if not root_path.exists():
            print(f"[WARN] Archive root does not exist: {root_path}")
            continue
        for p in root_path.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in SUPPORTED_EXTS:
                continue
            if is_noise_file(p):
                continue

            basename_index[p.name.lower()].append(p)
            if p.suffix.lower() == XLSX_EXT:
                text = f"{p.name} {p.parent}".lower()
                xlsx_catalog.append(
                    {
                        "path": p,
                        "name_l": p.name.lower(),
                        "tokens": set(tokenize(text)),
                    }
                )
    return basename_index, xlsx_catalog


def choose_candidate(candidates: List[Path], experiment_name: str, cell_name: str) -> Optional[Path]:
    """Pick the best candidate path if multiple files share the same basename."""
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    exp_l = (experiment_name or "").lower()
    cell_l = (cell_name or "").lower()

    scored = []
    for p in candidates:
        path_l = str(p).lower()
        score = 0
        if exp_l and exp_l in path_l:
            score += 3
        if cell_l and cell_l in path_l:
            score += 2
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


def most_common_pair(pairs: List[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    """Return mode pair if available."""
    if not pairs:
        return None
    return Counter(pairs).most_common(1)[0][0]


def parse_mti_case_insensitive(path: Path) -> Optional[Tuple[float, float]]:
    """Extract cutoff voltages from MTI workbook, robust to sheet name case."""
    try:
        xl = pd.ExcelFile(path)
        ch_sheet = None
        for s in xl.sheet_names:
            s_norm = s.strip().lower()
            if s_norm == "ch info" or "ch info" in s_norm:
                ch_sheet = s
                break
        if not ch_sheet:
            return None
        df = pd.read_excel(path, sheet_name=ch_sheet, header=None)
        return extract_pair_from_rows(df)
    except Exception:
        return None


def parse_neware_case_insensitive(path: Path) -> Optional[Tuple[float, float]]:
    """Extract cutoff voltages from Neware workbook, robust to sheet variations."""
    try:
        xl = pd.ExcelFile(path)
        test_sheet = None
        for s in xl.sheet_names:
            s_norm = s.strip().lower()
            if s_norm == "test" or "test" in s_norm:
                test_sheet = s
                break
        if not test_sheet:
            return None
        df = pd.read_excel(path, sheet_name=test_sheet, header=None)
        pair = extract_pair_from_neware_step_table(df)
        if pair:
            return pair
        return extract_pair_from_rows(df)
    except Exception:
        return None


def _safe_float(val: object) -> Optional[float]:
    """Best-effort conversion to float."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(str(val).strip())
    except Exception:
        return None


def extract_pair_from_neware_step_table(df: pd.DataFrame) -> Optional[Tuple[float, float]]:
    """Extract cutoffs from Neware step-plan table using named columns.

    This avoids mixing current values with voltage values and supports low-voltage
    anode cutoffs (e.g., 0.01 V) that generic regex logic can miss.
    """
    header_idx = None
    header_map: Dict[str, int] = {}

    for ridx in range(min(len(df), 120)):
        row = df.iloc[ridx].tolist()
        labels = [str(v).strip().lower() for v in row if pd.notna(v)]
        if not labels:
            continue
        joined = " | ".join(labels)
        if "step index" in joined and "step name" in joined:
            header_idx = ridx
            for cidx, v in enumerate(row):
                if pd.isna(v):
                    continue
                header_map[str(v).strip().lower()] = cidx
            break

    if header_idx is None:
        return None

    def col_for(*needles: str) -> Optional[int]:
        for key, idx in header_map.items():
            if all(n in key for n in needles):
                return idx
        return None

    c_step = col_for("step", "name")
    c_volt = col_for("voltage", "(v)")
    c_cutoff_v = col_for("cut-off", "voltage")

    if c_step is None:
        return None

    upper_candidates: List[float] = []
    lower_candidates: List[float] = []

    for ridx in range(header_idx + 1, min(len(df), header_idx + 200)):
        row = df.iloc[ridx]
        step_name_raw = row.iloc[c_step] if c_step < len(row) else None
        if pd.isna(step_name_raw):
            continue
        step_name = str(step_name_raw).strip().lower()
        if not step_name:
            continue
        # Ignore summary/meta rows
        if step_name in {"cycle", "end", "rest"}:
            continue

        v_col = _safe_float(row.iloc[c_volt]) if c_volt is not None and c_volt < len(row) else None
        cutoff_col = _safe_float(row.iloc[c_cutoff_v]) if c_cutoff_v is not None and c_cutoff_v < len(row) else None

        is_charge = any(k in step_name for k in ["chg", "charge"])
        is_discharge = any(k in step_name for k in ["dchg", "discharge", "ccd"])

        if is_charge:
            # Prefer explicit cutoff column for CC-Chg; fall back to voltage for CV/CCCV.
            cand = cutoff_col if cutoff_col is not None and cutoff_col > 0 else v_col
            if cand is not None and 0.0 <= cand <= 10:
                upper_candidates.append(cand)

        if is_discharge:
            cand = cutoff_col if cutoff_col is not None else v_col
            if cand is not None and 0.0 <= cand <= 10:
                lower_candidates.append(cand)

    if not upper_candidates or not lower_candidates:
        return None

    upper = Counter(round(v, 4) for v in upper_candidates).most_common(1)[0][0]
    lower = Counter(round(v, 4) for v in lower_candidates).most_common(1)[0][0]
    return normalize_pair(lower, upper)


def extract_voltages_from_text(text: str) -> List[float]:
    """Extract explicit voltage values from text."""
    values: List[float] = []
    for pat in [
        r"(\d+(?:\.\d+)?)\s*V\b",
        r"V\s*[<>]=?\s*(\d+(?:\.\d+)?)",
    ]:
        for m in re.findall(pat, text, flags=re.IGNORECASE):
            try:
                values.append(float(m))
            except ValueError:
                continue
    return [v for v in values if 0.0 <= v <= 10]


def extract_pair_from_rows(df: pd.DataFrame) -> Optional[Tuple[float, float]]:
    """Extract lower/upper cutoffs by scanning step-like rows for charge/discharge cues."""
    upper_candidates: List[float] = []
    lower_candidates: List[float] = []
    range_pairs: List[Tuple[float, float]] = []

    for _, row in df.iterrows():
        cells = [str(v).strip() for v in row.tolist() if pd.notna(v) and str(v).strip()]
        if not cells:
            continue
        row_text = " | ".join(cells).lower()

        # Explicit ranges like 3.0-4.2V
        for a, b in re.findall(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*V?", row_text):
            pair = normalize_pair(float(a), float(b))
            if pair:
                range_pairs.append(pair)

        text_voltages = extract_voltages_from_text(row_text)
        numeric_voltages: List[float] = []
        for v in row.tolist():
            if isinstance(v, (int, float)):
                fv = float(v)
                if 0.1 <= fv <= 10:
                    numeric_voltages.append(fv)
        # Prefer explicit textual voltage mentions ("...V") when present.
        all_voltages = text_voltages if text_voltages else (text_voltages + numeric_voltages)
        if not all_voltages:
            continue

        is_charge = ("cc chg" in row_text) or ("cc-cvc" in row_text) or ("cv chg" in row_text) or ("charge" in row_text and "discharge" not in row_text and "dchg" not in row_text and "ccd" not in row_text)
        is_discharge = ("cc dchg" in row_text) or ("ccd" in row_text) or ("discharge" in row_text) or ("dchg" in row_text)

        # Drop obvious non-cutoff numbers (e.g. tiny currents); keep plausible voltages.
        plausible = [v for v in all_voltages if 0.0 <= v <= 5.5]
        if not plausible:
            continue

        if is_charge:
            upper_candidates.append(max(plausible))
        if is_discharge:
            lower_candidates.append(min(plausible))

    if range_pairs:
        return most_common_pair(range_pairs)

    if upper_candidates and lower_candidates:
        upper = Counter(round(v, 3) for v in upper_candidates).most_common(1)[0][0]
        lower = Counter(round(v, 3) for v in lower_candidates).most_common(1)[0][0]
        return normalize_pair(lower, upper)

    return None


def extract_pair_from_xlsx(path: Path) -> Optional[Tuple[float, float]]:
    """Extract cutoff pair from MTI/Neware XLSX with robust fallbacks."""
    try:
        with path.open("rb") as fh:
            file_type = detect_file_type(fh)
    except Exception:
        return None

    if file_type == "mti_xlsx":
        return parse_mti_case_insensitive(path)
    if file_type == "neware_xlsx":
        return parse_neware_case_insensitive(path)
    return None


@lru_cache(maxsize=4096)
def extract_pair_from_xlsx_cached(path_str: str) -> Optional[Tuple[float, float]]:
    """Memoized wrapper to avoid re-parsing the same XLSX repeatedly."""
    return extract_pair_from_xlsx(Path(path_str))


def consensus_pair(pairs: List[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    """Return the most common valid pair in a set."""
    if not pairs:
        return None
    return Counter(pairs).most_common(1)[0][0]


def experiment_search_tokens(exp_name: str) -> Tuple[Optional[str], List[str]]:
    """Create experiment-level fuzzy-match tokens for archive lookup."""
    raw_tokens = [t for t in tokenize(exp_name) if t not in STOPWORDS]
    primary = canonical_experiment_tag(exp_name or "")
    if primary and primary not in raw_tokens:
        raw_tokens.insert(0, primary)
    # Keep small useful tokens like b2, n9, n10d; drop single-char noise.
    tokens = [t for t in raw_tokens if len(t) >= 2]
    return primary, tokens


def infer_pair_for_experiment(exp_name: str, xlsx_catalog: List[Dict[str, object]]) -> Optional[Tuple[float, float]]:
    """Infer a single cutoff pair for an experiment from fuzzy-matched XLSX files."""
    primary, tokens = experiment_search_tokens(exp_name or "")
    if not tokens and not primary:
        return None

    scored: List[Tuple[int, Path]] = []
    for item in xlsx_catalog:
        path = item["path"]
        token_set = item["tokens"]

        score = 0
        if primary and primary in token_set:
            score += 15
        for tok in tokens:
            if tok in token_set:
                score += 3

        if score > 0:
            scored.append((score, path))

    if not scored:
        return None

    scored.sort(key=lambda x: (x[0], -len(str(x[1]))), reverse=True)
    best_score = scored[0][0]
    # Keep high-confidence cohort around the best score.
    candidate_paths = [p for s, p in scored if s >= max(3, best_score - 4)]
    candidate_paths = candidate_paths[:20]

    extracted_pairs: List[Tuple[float, float]] = []
    for p in candidate_paths:
        pair = extract_pair_from_xlsx_cached(str(p))
        if pair:
            extracted_pairs.append(pair)

    if not extracted_pairs:
        return None

    counts = Counter(extracted_pairs).most_common()
    if len(counts) > 1 and counts[0][1] == counts[1][1]:
        return None
    return counts[0][0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill cutoff voltages from archived files")
    parser.add_argument("--db", required=True, help="Path to cellscope.db")
    parser.add_argument(
        "--roots",
        nargs="+",
        required=True,
        help="One or more directories to recursively scan for source CSV/XLSX files",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates to the database (default is dry-run)",
    )
    args = parser.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    file_index, xlsx_catalog = build_file_indexes(args.roots)
    total_indexed = sum(len(v) for v in file_index.values())
    print(
        f"Indexed {total_indexed} files across {len(args.roots)} root(s). "
        f"XLSX candidates: {len(xlsx_catalog)}"
    )

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, cell_name, data_json, cutoff_voltage_lower, cutoff_voltage_upper
        FROM cell_experiments
        ORDER BY id
        """
    )
    rows = cur.fetchall()

    experiments_seen = 0
    experiments_updated = 0
    cells_seen = 0
    cells_updated_from_file = 0
    cells_filled_from_experiment = 0
    xlsx_missing = 0
    xlsx_ambiguous = 0
    xlsx_no_cutoff_found = 0
    csv_skipped = 0
    experiments_inferred = 0

    for exp_id, exp_name, data_json, exp_lower, exp_upper in rows:
        experiments_seen += 1
        try:
            payload = json.loads(data_json) if data_json else {}
        except json.JSONDecodeError:
            continue

        cells = payload.get("cells", [])
        if not isinstance(cells, list) or not cells:
            continue

        changed = False
        exp_pairs: List[Tuple[float, float]] = []
        existing_exp_pair = normalize_pair(exp_lower, exp_upper)
        if existing_exp_pair:
            exp_pairs.append(existing_exp_pair)

        for cell in cells:
            cells_seen += 1
            cell_existing = normalize_pair(
                cell.get("cutoff_voltage_lower"),
                cell.get("cutoff_voltage_upper"),
            )
            if cell_existing:
                exp_pairs.append(cell_existing)
                continue

            file_name = (cell.get("file_name") or "").strip()
            if not file_name:
                continue

            ext = Path(file_name).suffix.lower()
            if ext == ".csv":
                csv_skipped += 1
                continue
            if ext != ".xlsx":
                continue

            candidates = file_index.get(file_name.lower(), [])
            chosen = choose_candidate(candidates, exp_name or "", cell.get("cell_name", ""))
            if chosen is None:
                if not candidates:
                    xlsx_missing += 1
                else:
                    xlsx_ambiguous += 1
                continue

            extracted = extract_pair_from_xlsx_cached(str(chosen))
            if not extracted:
                xlsx_no_cutoff_found += 1
                continue

            cell["cutoff_voltage_lower"] = extracted[0]
            cell["cutoff_voltage_upper"] = extracted[1]
            exp_pairs.append(extracted)
            cells_updated_from_file += 1
            changed = True

        # If still no pair, infer one pair for the experiment from fuzzy XLSX matches.
        if not exp_pairs:
            inferred = infer_pair_for_experiment(exp_name or "", xlsx_catalog)
            if inferred:
                exp_pairs.append(inferred)
                experiments_inferred += 1

        # Propagate a consensus pair across cells still missing values.
        pair = consensus_pair(exp_pairs)
        if pair:
            for cell in cells:
                cell_pair = normalize_pair(
                    cell.get("cutoff_voltage_lower"),
                    cell.get("cutoff_voltage_upper"),
                )
                if cell_pair is None:
                    cell["cutoff_voltage_lower"] = pair[0]
                    cell["cutoff_voltage_upper"] = pair[1]
                    cells_filled_from_experiment += 1
                    changed = True

            # Ensure experiment-level columns are set as well.
            if normalize_pair(exp_lower, exp_upper) != pair:
                exp_lower = pair[0]
                exp_upper = pair[1]
                changed = True

        if changed:
            experiments_updated += 1
            if args.apply:
                cur.execute(
                    """
                    UPDATE cell_experiments
                    SET data_json = ?, cutoff_voltage_lower = ?, cutoff_voltage_upper = ?
                    WHERE id = ?
                    """,
                    (json.dumps(payload), exp_lower, exp_upper, exp_id),
                )

    if args.apply:
        conn.commit()
    conn.close()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print("\n=== Backfill Summary ({}) ===".format(mode))
    print(f"Experiments scanned: {experiments_seen}")
    print(f"Experiments updated: {experiments_updated}")
    print(f"Cells scanned: {cells_seen}")
    print(f"Cells recovered from files: {cells_updated_from_file}")
    print(f"Cells filled by experiment consensus: {cells_filled_from_experiment}")
    print(f"Experiments inferred from fuzzy XLSX matching: {experiments_inferred}")
    print(f"CSV cells skipped (no extractable protocol): {csv_skipped}")
    print(f"XLSX missing from archive roots: {xlsx_missing}")
    print(f"XLSX ambiguous matches: {xlsx_ambiguous}")
    print(f"XLSX found but no cutoff extracted: {xlsx_no_cutoff_found}")


if __name__ == "__main__":
    main()
