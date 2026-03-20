import csv
import json
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import streamlit as st

from transform_event_data import transform_matchup_to_features

REPO_ROOT = Path(__file__).resolve().parent
EVENTS_DIR = REPO_ROOT / "events"
PREDICTIONS_DIR = REPO_ROOT / "predictions"
TRAINING_CSV = REPO_ROOT / "data" / "archive" / "UFC.csv"
FIGHTERS_CSV = REPO_ROOT / "data" / "archive" / "fighter_details.csv"
MODEL_DIR = REPO_ROOT / "models"

INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*]')
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def sanitize_event_filename(event_name: str) -> str:
    filename = INVALID_FILENAME_CHARS_RE.sub("_", event_name)
    filename = filename.strip(". ")
    return filename


def normalize_name(name: Optional[str]) -> str:
    if not name:
        return ""
    s = str(name).strip().lower()
    return NON_ALNUM_RE.sub("", s)


def parse_event_json(event_path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(event_path.read_text(encoding="utf-8"))
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def load_event_jsons() -> List[Dict[str, Any]]:
    if not EVENTS_DIR.exists():
        return []
    events: List[Dict[str, Any]] = []
    for p in sorted(EVENTS_DIR.glob("*.json")):
        data = parse_event_json(p)
        if data is not None:
            events.append(data)
    return events


def is_upcoming_event(event_data: Dict[str, Any]) -> bool:
    fights = event_data.get("fights", [])
    if not isinstance(fights, list) or not fights:
        return False
    for fight in fights:
        if not isinstance(fight, dict):
            continue
        if fight.get("winner", None) is not None:
            return False
    return True


@st.cache_data(show_spinner=False)
def load_predictions_index_for_event(event_name: str) -> Optional[Dict[Tuple[str, str], Dict[str, Any]]]:
    if not PREDICTIONS_DIR.exists():
        return None
    csv_path = PREDICTIONS_DIR / f"{sanitize_event_filename(event_name)}.csv"
    if not csv_path.exists():
        return None
    mapping: Dict[Tuple[str, str], Dict[str, Any]] = {}
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                f1 = row.get("fighter_1", "")
                f2 = row.get("fighter_2", "")
                predicted = row.get("predicted_winner", "") or ""
                try:
                    p1 = float(row.get("fighter_1_probability", "nan"))
                    p2 = float(row.get("fighter_2_probability", "nan"))
                except Exception:
                    continue
                key = (normalize_name(f1), normalize_name(f2))
                if key == ("", ""):
                    continue
                if not predicted:
                    continue
                mapping[key] = {
                    "predicted_winner": predicted,
                    "fighter_1_probability": p1,
                    "fighter_2_probability": p2,
                }
    except Exception:
        return None
    return mapping


def select_next_upcoming_event(events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    upcoming = [e for e in events if is_upcoming_event(e)]
    if not upcoming:
        return None
    upcoming.sort(key=lambda e: _event_date_sort_key(e, descending=False))
    return upcoming[0]


def list_upcoming_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    upcoming = [e for e in events if is_upcoming_event(e)]
    upcoming.sort(key=lambda e: _event_date_sort_key(e, descending=False))
    return upcoming


def list_past_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    past = [e for e in events if not is_upcoming_event(e)]
    past.sort(key=lambda e: _event_date_sort_key(e, descending=True))
    return past


def _parse_event_date(value: Any) -> Optional[datetime]:
    s = str(value or "").strip()
    if not s:
        return None
    formats = (
        "%B %d, %Y",   # March 21, 2026
        "%b %d, %Y",   # Mar 21, 2026
        "%Y-%m-%d",
        "%Y/%m/%d",
    )
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _event_date_sort_key(event_data: Dict[str, Any], descending: bool) -> Tuple[int, float]:
    dt = _parse_event_date(event_data.get("date", ""))
    if dt is None:
        sentinel = float("-inf") if descending else float("inf")
        return (1, sentinel)
    ts = dt.timestamp()
    return (0, ts if not descending else -ts)


@st.cache_data(show_spinner=False)
def compute_global_model_stats_cached() -> Dict[str, Any]:
    events = load_event_jsons()
    correct_non_draw = 0
    denominator_non_draw = 0
    draw_fights = 0
    resolved_fights_total = 0

    for event_data in events:
        event_name = str(event_data.get("name", "") or "")
        pred_index = load_predictions_index_for_event(event_name)
        if pred_index is None:
            continue
        fights = event_data.get("fights", [])
        if not isinstance(fights, list):
            continue
        for fight in fights:
            if not isinstance(fight, dict):
                continue
            winner = fight.get("winner", None)
            if winner is None:
                continue
            fighter_a = (fight.get("fighter_a") or {}).get("name", "") if isinstance(fight.get("fighter_a"), dict) else ""
            fighter_b = (fight.get("fighter_b") or {}).get("name", "") if isinstance(fight.get("fighter_b"), dict) else ""
            if not fighter_a or not fighter_b:
                continue
            key = (normalize_name(str(fighter_a)), normalize_name(str(fighter_b)))
            prediction_row = None
            if key in pred_index:
                prediction_row = pred_index[key]
            else:
                swapped_key = (key[1], key[0])
                if swapped_key in pred_index:
                    prediction_row = pred_index[swapped_key]
            if prediction_row is None:
                continue
            resolved_fights_total += 1
            winner_str = str(winner).strip()
            if winner_str.lower() == "draw":
                draw_fights += 1
                continue
            denominator_non_draw += 1
            predicted_winner = str(prediction_row.get("predicted_winner", "") or "")
            if normalize_name(predicted_winner) == normalize_name(winner_str):
                correct_non_draw += 1

    accuracy_excl_draws: Optional[float] = None
    if denominator_non_draw > 0:
        accuracy_excl_draws = correct_non_draw / denominator_non_draw

    return {
        "accuracy_excl_draws": accuracy_excl_draws,
        "correct_non_draw": correct_non_draw,
        "denominator_non_draw": denominator_non_draw,
        "draw_fights": draw_fights,
        "resolved_fights_total": resolved_fights_total,
    }


@st.cache_data(show_spinner=False)
def training_fight_count_cached() -> int:
    if not TRAINING_CSV.exists():
        return 0
    try:
        return len(pd.read_csv(TRAINING_CSV, usecols=[0]))
    except Exception:
        try:
            return len(pd.read_csv(TRAINING_CSV))
        except Exception:
            return 0


def build_predictions_table(
    event_data: Dict[str, Any], pred_index: Optional[Dict[Tuple[str, str], Dict[str, Any]]]
) -> pd.DataFrame:
    fights = event_data.get("fights", [])
    if not isinstance(fights, list):
        return pd.DataFrame(
            columns=[
                "fighter_a",
                "fighter_b",
                "predicted_winner",
                "fighter_a_probability",
                "fighter_b_probability",
                "actual_winner",
            ]
        )
    rows: List[Dict[str, Any]] = []
    for fight in fights:
        if not isinstance(fight, dict):
            continue
        fighter_a = (fight.get("fighter_a") or {}).get("name", "") if isinstance(fight.get("fighter_a"), dict) else ""
        fighter_b = (fight.get("fighter_b") or {}).get("name", "") if isinstance(fight.get("fighter_b"), dict) else ""
        key = (normalize_name(str(fighter_a)), normalize_name(str(fighter_b)))
        predicted_winner = ""
        fighter_a_prob: Optional[float] = None
        fighter_b_prob: Optional[float] = None
        if pred_index is not None and key in pred_index:
            row = pred_index[key]
            predicted_winner = str(row.get("predicted_winner", "") or "")
            fighter_a_prob = float(row.get("fighter_1_probability", "nan"))
            fighter_b_prob = float(row.get("fighter_2_probability", "nan"))
        elif pred_index is not None:
            swapped_key = (key[1], key[0])
            if swapped_key in pred_index:
                row = pred_index[swapped_key]
                predicted_winner = str(row.get("predicted_winner", "") or "")
                fighter_a_prob = float(row.get("fighter_2_probability", "nan"))
                fighter_b_prob = float(row.get("fighter_1_probability", "nan"))
        winner = fight.get("winner", None)
        actual = "" if winner is None else str(winner).strip()
        rows.append(
            {
                "fighter_a": fighter_a,
                "fighter_b": fighter_b,
                "fighter_a_probability": fighter_a_prob,
                "fighter_b_probability": fighter_b_prob,
                "predicted_winner": predicted_winner,
                "actual_winner": actual,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "fighter_a",
            "fighter_b",
            "fighter_a_probability",
            "fighter_b_probability",
            "predicted_winner",
            "actual_winner",
        ],
    )


def prediction_correctness(actual: str, predicted: str) -> str:
    if not actual or not predicted:
        return "—"
    if actual.lower() == "draw":
        return "—"
    if normalize_name(actual) == normalize_name(predicted):
        return "✓"
    return "✗"


@st.cache_data(show_spinner=False)
def build_fighter_catalog(events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    catalog: Dict[str, Dict[str, Any]] = {}
    for event_data in events:
        fights = event_data.get("fights", [])
        if not isinstance(fights, list):
            continue
        for fight in fights:
            if not isinstance(fight, dict):
                continue
            for corner in ("fighter_a", "fighter_b"):
                fd = fight.get(corner)
                if not isinstance(fd, dict):
                    continue
                name = fd.get("name")
                if not name:
                    continue
                catalog[normalize_name(str(name))] = fd
    return catalog


def catalog_display_names(catalog: Dict[str, Dict[str, Any]]) -> List[str]:
    names = []
    seen = set()
    for fd in catalog.values():
        n = str(fd.get("name", "") or "").strip()
        if not n:
            continue
        low = n.lower()
        if low in seen:
            continue
        seen.add(low)
        names.append(n)
    return sorted(names, key=lambda x: x.lower())


def filter_name_matches(query: str, names: List[str], limit: int = 80) -> List[str]:
    q = query.strip().lower()
    if not q:
        return []
    out = [n for n in names if q in n.lower()]
    out.sort(key=lambda x: (len(x), x.lower()))
    return out[:limit]


def resolve_fighter_entry(query: str, catalog: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    qn = normalize_name(query.strip())
    if qn and qn in catalog:
        return catalog[qn]
    return None


def _coerce_float(v: Any) -> Optional[float]:
    try:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        if pd.isna(v):
            return None
    except Exception:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _coerce_int(v: Any) -> int:
    fv = _coerce_float(v)
    if fv is None:
        return 0
    try:
        return int(round(fv))
    except Exception:
        return 0


@st.cache_data(show_spinner=False)
def load_fighter_details_catalog() -> Dict[str, Dict[str, Any]]:
    if not FIGHTERS_CSV.exists():
        return {}
    try:
        df = pd.read_csv(FIGHTERS_CSV)
    except Exception:
        return {}
    catalog: Dict[str, Dict[str, Any]] = {}

    for _, row in df.iterrows():
        name = row.get("name")
        if name is None or pd.isna(name):
            continue
        dataset_entry: Dict[str, Any] = {
            "height": _coerce_float(row.get("height")),
            "weight": _coerce_float(row.get("weight")),
            "reach": _coerce_float(row.get("reach")),
            "stance": row.get("stance"),
            "dob": row.get("dob"),
            "wins": _coerce_int(row.get("wins")),
            "losses": _coerce_int(row.get("losses")),
            "draws": _coerce_int(row.get("draws")),
            "career_splm": _coerce_float(row.get("splm")),
            "career_str_acc": _coerce_float(row.get("str_acc")),
            "career_sapm": _coerce_float(row.get("sapm")),
            "career_str_def": _coerce_float(row.get("str_def")),
            "career_td_avg": _coerce_float(row.get("td_avg")),
            "career_td_acc": _coerce_float(row.get("td_avg_acc")),
            "career_td_def": _coerce_float(row.get("td_def")),
            "career_sub_avg": _coerce_float(row.get("sub_avg")),
            "result": "win",
        }
        catalog[normalize_name(str(name))] = {"name": str(name), "dataset": [dataset_entry]}
    return catalog


@st.cache_resource(show_spinner=False)
def load_stacking_model():
    path = MODEL_DIR / "stacking_model.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


def model_stack_available() -> bool:
    return (MODEL_DIR / "stacking_model.joblib").exists()


def predict_from_feature_frame(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    model = load_stacking_model()
    if model is None or df.empty:
        return None
    st.session_state["last_inference_error"] = None
    metadata_cols = ["r_name", "b_name", "event_name"]
    feature_cols = [c for c in df.columns if c not in metadata_cols]
    X = df[feature_cols].copy()
    try:
        predictions = model.predict(X)
        probabilities = model.predict_proba(X)
    except Exception as e:
        # Keep the error available to the UI so deployment issues are debuggable.
        st.session_state["last_inference_error"] = f"{type(e).__name__}: {e}"
        return None
    r_name = str(df.iloc[0].get("r_name", "") or "")
    b_name = str(df.iloc[0].get("b_name", "") or "")
    pred = predictions[0]
    if probabilities.shape[1] >= 2:
        p_r = float(probabilities[0, 1])
        p_b = float(probabilities[0, 0])
    else:
        p_r = p_b = 0.5
    winner_name = r_name if bool(pred) else b_name
    return {
        "predicted_winner": winner_name,
        "fighter_a_probability": p_r,
        "fighter_b_probability": p_b,
        "fighter_a_name": r_name,
        "fighter_b_name": b_name,
    }


def run_matchup_prediction(fighter_a: Dict[str, Any], fighter_b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    df = transform_matchup_to_features(fighter_a, fighter_b, date_str="", division="unknown", title_fight=0, event_name="Matchup")
    return predict_from_feature_frame(df)


def fighter_profile_strip(fd: Dict[str, Any]) -> Dict[str, str]:
    ds = fd.get("dataset")
    row = ds[0] if isinstance(ds, list) and ds and isinstance(ds[0], dict) else {}
    wins = row.get("wins", "—")
    losses = row.get("losses", "—")
    draws = row.get("draws", "—")
    rec = f"{wins}-{losses}-{draws}" if wins != "—" else "—"
    h = row.get("height", "—")
    reach = row.get("reach", "—")
    return {"record": str(rec), "height": str(h), "reach": str(reach)}


def pct_cell(v: Any) -> str:
    if v is None:
        return "—"
    try:
        if isinstance(v, float) and np.isnan(v):
            return "—"
    except Exception:
        pass
    try:
        if pd.isna(v):
            return "—"
    except Exception:
        pass
    try:
        return f"{float(v) * 100.0:.1f}%"
    except Exception:
        return "—"


def html_fight_table(headers: List[str], rows: List[List[str]], table_class: str = "w-full text-sm text-left") -> str:
    """
    Render a responsive fight table:
    - On small screens (xs): stacked "card rows" for readability.
    - On sm+ screens: classic HTML table for compactness.
    """

    def _cell_value_html(v: Any) -> str:
        s = str(v) if v is not None else "—"
        if s in ("✓", "✗", "—"):
            return s
        return escape(s)

    # Desktop table (sm+)
    ths_table = "".join(
        f'<th class="px-3 py-2 font-semibold text-slate-300 border-b border-slate-700">{escape(h)}</th>'
        for h in headers
    )
    body_table = ""
    for row in rows:
        tds = "".join(
            f'<td class="px-3 py-2 border-b border-slate-800 text-slate-200">{_cell_value_html(c)}</td>'
            for c in row
        )
        body_table += f"<tr>{tds}</tr>"

    table_html = (
        f'<table class="{table_class}">'
        f"<thead><tr>{ths_table}</tr></thead>"
        f"<tbody>{body_table}</tbody>"
        f"</table>"
    )

    # Mobile cards (xs)
    card_items: List[str] = []
    for row in rows:
        kvs: List[str] = []
        for h, c in zip(headers, row):
            kvs.append(
                '<div class="flex items-start justify-between gap-3">'
                f'<span class="text-xs text-slate-500">{escape(h)}</span>'
                f'<span class="text-xs text-slate-200 font-medium text-right break-words whitespace-normal">{_cell_value_html(c)}</span>'
                "</div>"
            )
        kvs_html = "".join(kvs)
        card_items.append(
            f'<div class="rounded-lg border border-slate-800 bg-slate-950/40 p-3 space-y-2">{kvs_html}</div>'
        )

    cards_html = f'<div class="sm:hidden space-y-2">{"".join(card_items)}</div>'

    return f'<div class="w-full">{cards_html}<div class="hidden sm:block">{table_html}</div></div>'


def upcoming_table_rows(df: pd.DataFrame) -> Tuple[List[str], List[List[str]]]:
    headers = ["Matchup", "Predicted winner", "Confidence %"]
    rows: List[List[str]] = []
    for _, r in df.iterrows():
        a, b = str(r["fighter_a"]), str(r["fighter_b"])
        matchup = f"{a} vs {b}"
        predicted = str(r.get("predicted_winner", "") or "")
        if normalize_name(predicted) == normalize_name(a):
            confidence = pct_cell(r.get("fighter_a_probability"))
        elif normalize_name(predicted) == normalize_name(b):
            confidence = pct_cell(r.get("fighter_b_probability"))
        else:
            confidence = "—"
        rows.append(
            [
                matchup,
                predicted or "—",
                confidence,
            ]
        )
    return headers, rows


def past_table_rows(df: pd.DataFrame) -> Tuple[List[str], List[List[str]]]:
    headers = ["Matchup", "Actual", "Predicted", "Confidence %", "Score"]
    rows: List[List[str]] = []
    for _, r in df.iterrows():
        a, b = str(r["fighter_a"]), str(r["fighter_b"])
        matchup = f"{a} vs {b}"
        actual = str(r.get("actual_winner", "") or "—")
        pred = str(r.get("predicted_winner", "") or "—")
        if normalize_name(pred) == normalize_name(a):
            confidence = pct_cell(r.get("fighter_a_probability"))
        elif normalize_name(pred) == normalize_name(b):
            confidence = pct_cell(r.get("fighter_b_probability"))
        else:
            confidence = "—"
        mark = prediction_correctness(actual, pred)
        rows.append(
            [
                matchup,
                actual,
                pred,
                confidence,
                mark,
            ]
        )
    return headers, rows
