import html
from typing import Any, Dict, List, Optional

import streamlit as st
from streamlit_tailwind import st_tw

from fight_app_data import (
    build_fighter_catalog,
    build_predictions_table,
    catalog_display_names,
    compute_global_model_stats_cached,
    filter_name_matches,
    fighter_profile_strip,
    html_fight_table,
    list_past_events,
    list_upcoming_events,
    load_event_jsons,
    load_fighter_details_catalog,
    load_predictions_index_for_event,
    model_stack_available,
    normalize_name,
    past_table_rows,
    resolve_fighter_entry,
    run_matchup_prediction,
    training_fight_count_cached,
    upcoming_table_rows,
)

st.set_page_config(
    page_title="UFC Fight Predictor",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 72rem; }
    [data-testid="stAppViewContainer"] { background: #020617; }
    div[data-testid="stVerticalBlock"] > div:has(> div > [data-testid="stMarkdown"]) {
        font-family: ui-sans-serif, system-ui, sans-serif;
    }
    .stTextInput input {
        background: #0f172a !important;
        color: #f1f5f9 !important;
        border-color: #334155 !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #0f172a !important;
        color: #f1f5f9 !important;
        border-color: #334155 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def pick_fighter(
    label: str,
    catalog: Dict[str, Dict[str, Any]],
    all_names: List[str],
    key_prefix: str,
) -> Optional[Dict[str, Any]]:
    q_key = f"{key_prefix}_q"
    search_key = f"{key_prefix}_search_query"
    selected_key = f"{key_prefix}_selected_name"
    sync_key = f"{key_prefix}_sync_text"

    if search_key not in st.session_state:
        st.session_state[search_key] = ""
    if selected_key not in st.session_state:
        st.session_state[selected_key] = ""
    if sync_key not in st.session_state:
        st.session_state[sync_key] = False

    if st.session_state.get(sync_key):
        st.session_state[q_key] = str(st.session_state.get(selected_key, "") or "")
        st.session_state[sync_key] = False

    def submit_search() -> None:
        query = str(st.session_state.get(q_key, "")).strip()
        st.session_state[search_key] = query
        st.session_state[selected_key] = ""
        if len(query) >= 3:
            matches = filter_name_matches(query, all_names, limit=200)
            if len(matches) == 1:
                st.session_state[selected_key] = matches[0]
                st.session_state[sync_key] = True
                st.session_state[search_key] = ""

    st.text_input(
        label,
        key=q_key,
        placeholder="Search fighter and press Enter…",
        on_change=submit_search,
    )

    selected_name = str(st.session_state.get(selected_key, "") or "").strip()
    if selected_name:
        selected = resolve_fighter_entry(selected_name, catalog)
        if selected is not None:
            return selected

    search_query = str(st.session_state.get(search_key, "") or "").strip()
    if len(search_query) < 3:
        return None

    matches = filter_name_matches(search_query, all_names, limit=200)
    if not matches:
        st.caption("No matches.")
        return None

    st.caption(f"{len(matches)} matches")
    options_key = f"{key_prefix}_options"
    st.markdown(
        f"""
        <style>
        /* Cap the options list height so it doesn't dominate the page on mobile. */
        .st-key-{options_key} {{
          max-height: 40vh;
          overflow-y: auto;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    options_container = st.container(border=True, key=options_key)
    with options_container:
        for idx, name in enumerate(matches):
            if st.button(name, key=f"{key_prefix}_option_{idx}", use_container_width=True):
                st.session_state[selected_key] = name
                st.session_state[sync_key] = True
                st.session_state[search_key] = ""
                st.rerun()

    return None


events = load_event_jsons()
stats = compute_global_model_stats_cached()
train_rows = training_fight_count_cached()

catalog = load_fighter_details_catalog()
if not catalog:
    catalog = build_fighter_catalog(events)
all_names = catalog_display_names(catalog)

acc = stats.get("accuracy_excl_draws")
acc_str = "N/A" if acc is None else f"{acc * 100:.1f}%"
resolved = int(stats.get("resolved_fights_total", 0))
non_draw_scored = int(stats.get("denominator_non_draw", 0))
draws = int(stats.get("draw_fights", 0))

hero_html = f"""
<div class="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 p-8 shadow-xl">
  <p class="text-xs font-semibold uppercase tracking-widest text-amber-500/90 mb-2">UFC analytics</p>
  <h1 class="text-3xl md:text-4xl font-bold text-white tracking-tight mb-2">Fight Predictor</h1>
  <p class="text-slate-400 text-sm max-w-2xl mb-8">Stacking classifier using MLP, LightGBM, SVM, and Random Forest models. This model is not perfect, but it learns non-trivial patterns from historical UFC bouts. View model prediction on past UFC events or run inference with custom match-ups.</p>
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
    <div class="rounded-xl bg-slate-950/80 border border-slate-800 p-4">
      <p class="text-xs text-slate-500 uppercase tracking-wide mb-1">Accuracy</p>
      <p class="text-2xl font-bold text-white">{html.escape(acc_str)}</p>
      <p class="text-xs text-slate-500 mt-1">Excludes draws · {non_draw_scored} fights</p>
    </div>
    <div class="rounded-xl bg-slate-950/80 border border-slate-800 p-4">
      <p class="text-xs text-slate-500 uppercase tracking-wide mb-1">Predicted fights</p>
      <p class="text-2xl font-bold text-white">{resolved}</p>
      <p class="text-xs text-slate-500 mt-1">{draws} draws included</p>
    </div>
    <div class="rounded-xl bg-slate-950/80 border border-slate-800 p-4">
      <p class="text-xs text-slate-500 uppercase tracking-wide mb-1">Training fights</p>
      <p class="text-2xl font-bold text-white">{train_rows:,}</p>
      <p class="text-xs text-slate-500 mt-1">Rows in UFC.csv archive</p>
    </div>
  </div>
</div>
"""
st_tw(text=hero_html)

with st.container(border=True):
    panel2_title = """
<div class="rounded-xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 px-6 py-4 shadow-lg">
  <h2 class="text-lg font-semibold text-white">Predicted UFC Events</h2>
  <p class="text-sm text-slate-400 mt-1">View model predictions for upcoming UFC events or past events with actual results vs. model.</p>
</div>
"""
    st_tw(text=panel2_title)

    mode = st.radio("View", ("Upcoming", "Past"), horizontal=True, label_visibility="collapsed")

    if mode == "Upcoming":
        upcoming = list_upcoming_events(events)
        if not upcoming:
            st_tw(
                text='<div class="rounded-xl border border-slate-800 bg-slate-950/50 px-6 py-8 text-slate-400 text-center">No upcoming events (all fights have winners filled in).</div>',
            )
        else:
            labels = [f'{e.get("name", "")} — {e.get("date", "")}' for e in upcoming]
            idx = st.selectbox("Event", range(len(upcoming)), format_func=lambda i: labels[i], key="up_ev")
            ev = upcoming[idx]
            en = str(ev.get("name", "") or "")
            pred_index = load_predictions_index_for_event(en)
            df = build_predictions_table(ev, pred_index)

            meta = f"""
<div class="flex flex-wrap gap-6 text-sm text-slate-400 px-6 py-3 border border-slate-800 rounded-xl bg-slate-950/50">
  <span><span class="text-slate-600">Date</span> <span class="text-slate-200 ml-1">{html.escape(str(ev.get("date", "") or "—"))}</span></span>
  <span><span class="text-slate-600">Location</span> <span class="text-slate-200 ml-1">{html.escape(str(ev.get("location", "") or "—"))}</span></span>
</div>
"""
            st_tw(text=meta)

            if pred_index is None:
                st_tw(
                    text=f'<div class="px-6 py-4 text-amber-200/90 text-sm border border-slate-800 rounded-xl bg-slate-950/50">No predictions CSV for <span class="font-medium">{html.escape(en)}</span>.</div>',
                )
            else:
                headers, rows = upcoming_table_rows(df)
                tbl = html_fight_table(headers, rows)
                # Let the table height be driven by the number of rows.
                # Keep horizontal overflow scrollable for narrow screens.
                wrap = f'<div class="rounded-xl border border-slate-800 bg-slate-950/50 p-4 overflow-x-auto">{tbl}</div>'
                st_tw(text=wrap)

    else:
        past = list_past_events(events)
        if not past:
            st_tw(
                text='<div class="rounded-xl border border-slate-800 bg-slate-950/50 px-6 py-8 text-slate-400 text-center">No past events found.</div>',
            )
        else:
            labels = [f'{e.get("name", "")} — {e.get("date", "")}' for e in past]
            idx = st.selectbox("Event", range(len(past)), format_func=lambda i: labels[i], key="past_ev")
            ev = past[idx]
            en = str(ev.get("name", "") or "")
            pred_index = load_predictions_index_for_event(en)
            df = build_predictions_table(ev, pred_index)

            correct = 0
            denominator = 0
            for _, row in df.iterrows():
                actual = str(row.get("actual_winner", "") or "").strip()
                predicted = str(row.get("predicted_winner", "") or "").strip()
                if not actual or not predicted:
                    continue
                if actual.lower() == "draw":
                    continue
                denominator += 1
                if normalize_name(actual) == normalize_name(predicted):
                    correct += 1

            if denominator > 0:
                accuracy_pct = correct / denominator * 100.0
                accuracy_text = f"{correct}/{denominator} ({accuracy_pct:.0f}%)"
            else:
                accuracy_text = " —"

            meta = f"""
<div class="flex flex-wrap gap-6 text-sm text-slate-400 px-6 py-3 border border-slate-800 rounded-xl bg-slate-950/50">
  <span><span class="text-slate-600">Date</span> <span class="text-slate-200 ml-1">{html.escape(str(ev.get("date", "") or "—"))}</span></span>
  <span><span class="text-slate-600">Location</span> <span class="text-slate-200 ml-1">{html.escape(str(ev.get("location", "") or "—"))}</span></span>
  <span><span class="text-slate-600">Accuracy</span> <span class="text-slate-200 ml-1">{html.escape(accuracy_text)}</span></span>
</div>
"""
            st_tw(text=meta)

            if pred_index is None:
                st_tw(
                    text=f'<div class="px-6 py-4 text-amber-200/90 text-sm border border-slate-800 rounded-xl bg-slate-950/50">No predictions CSV for <span class="font-medium">{html.escape(en)}</span>.</div>',
                )
            else:
                headers, rows = past_table_rows(df)
                tbl = html_fight_table(headers, rows)
                # Let the table height be driven by the number of rows.
                # Keep horizontal overflow scrollable for narrow screens.
                wrap = f'<div class="rounded-xl border border-slate-800 bg-slate-950/50 p-4 overflow-x-auto">{tbl}</div>'
                st_tw(text=wrap)

with st.container(border=True):
    panel1_header = """
<div class="rounded-xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-950 px-6 py-4 shadow-lg">
  <h2 class="text-lg font-semibold text-white">Custom matchup</h2>
  <p class="text-sm text-slate-400 mt-1">Search fighters from the fighters dataset and view model predictions. Note: This model is not perfect and has limitations.</p>
</div>
"""
    st_tw(text=panel1_header)

    c1, c2 = st.columns(2)
    with c1:
        fa = pick_fighter("Fighter A", catalog, all_names, "fa")
    with c2:
        fb = pick_fighter("Fighter B", catalog, all_names, "fb")

    if fa and fb:
        if fa is fb or normalize_name(str(fa.get("name"))) == normalize_name(str(fb.get("name"))):
            st_tw(
                text='<div class="rounded-xl border border-amber-900/50 bg-amber-950/30 text-amber-200 text-sm px-4 py-3">Choose two different fighters.</div>',
            )
        elif not model_stack_available():
            st_tw(
                text='<div class="rounded-xl border border-red-900/40 bg-red-950/20 text-red-200 text-sm px-4 py-3">Add <code class="bg-black/30 px-1 rounded">models/stacking_model.joblib</code> to run live predictions.</div>',
            )
        else:
            pred = run_matchup_prediction(fa, fb)
            pa = fighter_profile_strip(fa)
            pb = fighter_profile_strip(fb)
            name_a = html.escape(str(fa.get("name", "")))
            name_b = html.escape(str(fb.get("name", "")))

            if pred:
                pw = html.escape(str(pred["predicted_winner"]))
                pcta = f"{pred['fighter_a_probability'] * 100:.1f}%"
                pctb = f"{pred['fighter_b_probability'] * 100:.1f}%"
                result_html = f"""
<div class="rounded-2xl border border-slate-800 bg-slate-900/80 p-4 sm:p-6 mb-2 shadow-lg">
  <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <p class="text-xs uppercase text-slate-500 tracking-wide">Predicted winner</p>
      <p class="text-2xl sm:text-3xl font-bold text-emerald-400 mt-1 leading-tight">{pw}</p>
    </div>

    <div class="flex flex-col sm:flex-row gap-2 sm:gap-8 text-sm">
      <div class="flex items-baseline gap-2"><span class="text-slate-500">A win</span><span class="text-white font-semibold">{pcta}</span></div>
      <div class="flex items-baseline gap-2"><span class="text-slate-500">B win</span><span class="text-white font-semibold">{pctb}</span></div>
    </div>
  </div>

  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm border-t border-slate-800 pt-4 mt-4 sm:mt-0">
    <div class="rounded-lg bg-slate-950/60 p-3 border border-slate-800">
      <p class="font-medium text-slate-200">{name_a}</p>
      <p class="text-slate-500 mt-1 break-words">Record {html.escape(pa["record"])} · Ht {html.escape(pa["height"])} · Reach {html.escape(pa["reach"])}</p>
    </div>
    <div class="rounded-lg bg-slate-950/60 p-3 border border-slate-800">
      <p class="font-medium text-slate-200">{name_b}</p>
      <p class="text-slate-500 mt-1 break-words">Record {html.escape(pb["record"])} · Ht {html.escape(pb["height"])} · Reach {html.escape(pb["reach"])}</p>
    </div>
  </div>
</div>
"""
            else:
                result_html = """
<div class="rounded-xl border border-red-900/40 bg-red-950/20 text-red-200 text-sm px-4 py-3 mb-2">Model inference failed. Check feature columns vs. saved model.</div>
"""
            st_tw(text=result_html)

st.caption("Karandeep Shoker · MMA Fight Predictor")
