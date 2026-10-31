"""Streamlit analytics dashboard.

Run from the repo root:   python -m analytics.dashboard            (live database)
                          python -m analytics.dashboard --sample   (synthetic preview)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # streamlit puts only the script folder on sys.path
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from analytics.dashboard import metrics, sample, source  # noqa: E402

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

TEXTS = tomllib.loads((Path(__file__).parent / "texts.toml").read_text(encoding="utf-8"))
OUTCOME_COLORS = {
    "resolved_auto": "#1DB954", "retained": "#4CC76E", "refunded": "#9BD34A",
    "canceled": "#F2C230", "escalated": "#F28C28", "abandoned": "#E5484D",
}
CSS = """
<style>
.block-container {padding-top: 5rem; padding-bottom: 0.5rem; zoom: 0.78;}
[data-testid="stHeader"] {height: 2rem;}
h1 {font-size: 1.7rem !important; padding: 0 !important;}
h3 {font-size: 1.05rem !important; padding: 0.2rem 0 !important;}
.tile {border-radius: 10px; padding: 8px 12px; background: #161A22; border-left: 6px solid var(--c);}
.tile .l {font-size: 0.72rem; color: #9AA3B2; text-transform: uppercase; letter-spacing: .04em;}
.tile .v {font-size: 1.7rem; font-weight: 700; color: var(--c); line-height: 1.2;}
.tile .s {font-size: 0.68rem; color: #7C8594;}
</style>
"""


def health(good):
    """Map goodness 0..1 to red -> yellow -> green (hue 0..120)."""
    if good is None:
        return "#9AA3B2"
    good = max(0.0, min(1.0, good))
    return f"hsl({int(good * 120)}, 75%, 52%)"


def tile(col, label, value, good=None, sub=""):
    col.markdown(
        f'<div class="tile" style="--c:{health(good)}"><div class="l">{label}</div>'
        f'<div class="v">{value}</div><div class="s">{sub or "&nbsp;"}</div></div>',
        unsafe_allow_html=True,
    )


def bar(data, x, y, color_field=None, scale=None, height=210, horizontal=False):
    import altair as alt

    enc = dict(x=alt.X(x, sort=None, title=None), y=alt.Y(y, title=None))
    if horizontal:
        enc = dict(y=alt.Y(x, sort="-x", title=None, axis=alt.Axis(labelLimit=260)), x=alt.X(y, title=None))
    if scale:
        enc["color"] = alt.Color(color_field, scale=alt.Scale(domain=list(scale), range=list(scale.values())), legend=None)
    else:
        enc["color"] = alt.Color(color_field, scale=alt.Scale(scheme="redyellowgreen", domain=[0, 1]), legend=None)
    st.altair_chart(alt.Chart(alt.Data(values=data)).mark_bar().encode(**enc).properties(height=height),
                    use_container_width=True)





def pct(v):
    return "n/a" if v is None else f"{v:.0%}"


def num(v, digits=2):
    return "n/a" if v is None else f"{v:.{digits}f}"


@st.cache_data(ttl=5, show_spinner=False)
def load_live(days: int):
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return source.load_postgres(since)


def load(days: int, use_sample: bool):
    if use_sample:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        conversations, calls = sample.generate()
        return ([c for c in conversations if c["started_at"] >= since],
                [t for t in calls if t["occurred_at"] >= since])
    return load_live(days)


def main():
    st.set_page_config(page_title=TEXTS["title"], page_icon="📊", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    use_sample = os.environ.get("DASHBOARD_SAMPLE") == "1"
    with st.sidebar:
        days = st.select_slider("Window (days)", options=[1, 7, 14, 30, 90], value=14)
        if st.button("Refresh now"):
            st.cache_data.clear()
    st.title(TEXTS["title"])
    if use_sample:
        st.warning(TEXTS["sample_banner"])
    try:
        conversations, calls = load(days, use_sample)
    except Exception:  # noqa: BLE001 - friendly message; details stay in the server log
        st.error(TEXTS["db_error"])
        st.stop()
    if not conversations:
        st.info(TEXTS["empty"])
        st.stop()

    o = metrics.outcomes(conversations)
    refunds = metrics.auto_refunds(calls)
    sent = metrics.sentiment(conversations)
    churn = metrics.churn_risk(conversations)
    gaps = metrics.knowledge_gaps(conversations)["count"]
    quality = metrics.quality(conversations)
    total = o["total"]
    clamp = lambda v: max(0.0, min(1.0, v))  # noqa: E731

    c = st.columns(8)
    tile(c[0], "Conversations", total)
    tile(c[1], "Resolved w/o escalation", pct(o["resolved_rate"]), clamp((o["resolved_rate"] - 0.4) / 0.5))
    tile(c[2], "Escalated", pct(o["escalated_rate"]), clamp(1 - o["escalated_rate"] / 0.4))
    tile(c[3], "Abandoned", pct(o["abandoned_rate"]), clamp(1 - o["abandoned_rate"] / 0.2))
    tile(c[4], "Retained", o["retained"], clamp(o["retained"] / max(total, 1) / 0.3))
    refund_text = ", ".join(f"{v:,.2f} {k}" for k, v in refunds["totals"].items()) or "0"
    tile(c[5], "Auto refunds", refund_text, None, f"{refunds['count']} verified")
    tile(c[6], "Avg churn risk", num(churn["average"]),
         None if churn["average"] is None else 1 - churn["average"], f"{churn['high_risk']} high-risk")
    end = sent["avg_end"]
    tile(c[7], "Sentiment end", num(end), None if end is None else clamp((end + 2) / 4),
         f"from {num(sent['avg_start'])}")
    if refunds["incomplete"]:
        st.caption(TEXTS["refund_note"].format(n=refunds["incomplete"]))

    c = st.columns(5)
    for col, q in zip(c, quality):
        tile(col, f"Quality: {q['metric']}", num(q["average"]),
             None if q["average"] is None else clamp((q["average"] - 1) / 4), f"n={q['assessed']}")
    tile(c[3], "Knowledge gaps", gaps, clamp(1 - gaps / max(total, 1) / 0.2))
    tile(c[4], "Escalations / abandoned", o["counts"].get("escalated", 0) + o["counts"].get("abandoned", 0),
         clamp(1 - (o["counts"].get("escalated", 0) + o["counts"].get("abandoned", 0)) / max(total, 1) / 0.4))

    a, b, d = st.columns(3)
    with a:
        st.subheader("Conversations per day")
        daily = [{"day": str(x["day"]), "n": x["conversations"]} for x in metrics.daily_volume(conversations)]
        import altair as alt
        st.altair_chart(alt.Chart(alt.Data(values=daily)).mark_bar(color="#1DB954")
                        .encode(x=alt.X("day:N", title=None, axis=alt.Axis(labelAngle=-45)), y=alt.Y("n:Q", title=None))
                        .properties(height=210), use_container_width=True)
    with b:
        st.subheader("Outcomes")
        bar([{"outcome": k, "n": v} for k, v in o["counts"].items()], "outcome:N", "n:Q", "outcome:N", OUTCOME_COLORS)
    with d:
        st.subheader("Reasons (intent + reason)")
        reasons = metrics.cancellation_reasons(conversations)
        top = reasons[0]["count"] if reasons else 1
        # More frequent reasons are worse for the business: red = most common.
        bar([{"reason": f"{r['intent']}: {r['reason']}", "n": r["count"], "g": 1 - r["count"] / top}
             for r in reasons[:8]], "reason:N", "n:Q", "g:Q", None, horizontal=True)

    a, b, d = st.columns(3)
    with a:
        st.subheader("Accepted retention offers")
        offers = metrics.retention_offers(calls)
        if offers:
            bar([{"offer": x["offer"], "n": x["accepted"], "g": 1.0} for x in offers], "offer:N", "n:Q", "g:Q", None,
                height=170, horizontal=True)
        else:
            st.caption("No accepted offers")
    with b:
        st.subheader("Tool usage")
        usage = metrics.tool_usage(calls)[:8]
        bar([{"tool": u["tool"], "n": u["calls"], "g": u.get("done", 0) / u["calls"]} for u in usage],
            "tool:N", "n:Q", "g:Q", None, height=170, horizontal=True)
    with d:
        st.subheader("Policy citations")
        cites = metrics.policy_citations(calls)
        if cites:
            bar([{"policy": x["policy"], "n": x["calls"], "g": 1.0} for x in cites[:6]], "policy:N", "n:Q", "g:Q", None,
                height=170, horizontal=True)
        else:
            st.caption("No policy citations")

    with st.expander("Conversation drill-down"):
        st.dataframe([{"session": x["session_id"], "started": x["started_at"], "intent": x["intent"],
                       "reason": x["reason"], "outcome": x["resolution"], "churn": x["churn_risk"]}
                      for x in conversations], hide_index=True, width="stretch", height=220)
        chosen = st.selectbox("Inspect session", [x["session_id"] for x in conversations])
        selected = next(x for x in conversations if x["session_id"] == chosen)
        st.write(selected["summary"])
        rows = metrics.session_tool_calls(calls, chosen)
        st.dataframe([{k: r[k] for k in ("occurred_at", "tool_name", "result_status", "autonomy_level", "actor",
                                         "offer_code", "refunded_amount", "currency", "error_code")} for r in rows],
                     hide_index=True, width="stretch")


main()
