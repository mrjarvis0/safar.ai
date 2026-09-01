"""Altair chart builders for the Safar UI — dark-themed, self-contained.

Altair ships with Streamlit (no extra dependency), so these are safe to rely
on. Every builder returns a configured `alt.Chart`; render with
`st.altair_chart(chart, use_container_width=True)`. Each is defensive: given
missing/empty data it returns None, and the caller simply skips it.
"""
from __future__ import annotations

import altair as alt
import pandas as pd

# palette — kept in sync with theme.py
ACCENT, ACCENT2, ACCENT3, AMBER, ROSE = "#7c5cff", "#22d3ee", "#34d399", "#f59e0b", "#f43f5e"
ARCH = {"saver": "#38bdf8", "comfort": "#c084fc", "balanced": "#f59e0b"}
_ARCH_ORDER = ["Saver", "Comfort", "Balanced"]

_AXIS = dict(labelColor="#94a0bd", titleColor="#c7cee0",
             gridColor="rgba(255,255,255,.06)", domainColor="rgba(255,255,255,.12)",
             tickColor="rgba(255,255,255,.12)", labelFont="Inter", titleFont="Sora",
             titleFontWeight=600, labelFontSize=11)


def _cfg(chart):
    """Apply the shared dark styling to a top-level chart."""
    return (chart
            .configure(background="rgba(0,0,0,0)")
            .configure_view(strokeWidth=0, fill="rgba(0,0,0,0)")
            .configure_axis(**_AXIS)
            .configure_legend(labelColor="#c7cee0", titleColor="#c7cee0",
                              labelFont="Inter", titleFont="Sora", orient="top")
            .configure_title(color="#e6e9f2", font="Sora", fontSize=14,
                             anchor="start", fontWeight=600))


def _arch_scale():
    return alt.Scale(domain=list(ARCH), range=list(ARCH.values()))


# ------------------------------------------------- candidate cost vs budget --
def candidate_cost(candidates: dict, budget: float | None = None):
    rows = []
    for k in ("saver", "comfort", "balanced"):
        p = candidates.get(k)
        if not p:
            continue
        rows.append({"Plan": k.title(), "arch": k, "Cost": float(p.get("cost_inr", 0)),
                     "Fits": "in budget" if p.get("feasible") else "over budget"})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    base = alt.Chart(df)
    bars = base.mark_bar(cornerRadiusEnd=7, height=30).encode(
        x=alt.X("Cost:Q", title="Total cost (₹)", axis=alt.Axis(format="~s")),
        y=alt.Y("Plan:N", sort=_ARCH_ORDER, title=None),
        color=alt.Color("arch:N", scale=_arch_scale(), legend=None),
        opacity=alt.condition("datum.Fits == 'over budget'", alt.value(.45), alt.value(1)),
        tooltip=[alt.Tooltip("Plan:N"), alt.Tooltip("Cost:Q", format=",.0f", title="₹"),
                 alt.Tooltip("Fits:N", title="budget")])
    labels = base.mark_text(align="left", dx=7, color="#e6e9f2", font="Sora",
                            fontSize=12, fontWeight=600).encode(
        x="Cost:Q", y=alt.Y("Plan:N", sort=_ARCH_ORDER),
        text=alt.Text("Cost:Q", format=",.0f"))
    layers = [bars, labels]
    if budget:
        rule = alt.Chart(pd.DataFrame({"b": [budget]})).mark_rule(
            color=ROSE, strokeWidth=2, strokeDash=[6, 4]).encode(
            x="b:Q", tooltip=alt.Tooltip("b:Q", format=",.0f", title="budget ₹"))
        layers.append(rule)
    return _cfg(alt.layer(*layers).properties(height=150))


# ------------------------------------------------------ score breakdown ------
def score_breakdown(candidates: dict):
    label = {"comfort": "Comfort", "experience": "Experience",
             "safety": "Safety", "cost_norm": "Cost (norm)"}
    rows = []
    for k in ("saver", "comfort", "balanced"):
        p = candidates.get(k)
        if not p:
            continue
        sc = p.get("scores", {})
        for key, nice in label.items():
            if key in sc:
                rows.append({"Plan": k.title(), "arch": k, "Metric": nice,
                             "Score": round(float(sc[key]), 3)})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    ch = alt.Chart(df).mark_bar(cornerRadiusEnd=4).encode(
        x=alt.X("Plan:N", title=None, axis=alt.Axis(labelAngle=0),
                sort=_ARCH_ORDER),
        y=alt.Y("Score:Q", title=None, scale=alt.Scale(domain=[0, 1])),
        color=alt.Color("arch:N", scale=_arch_scale(), legend=None),
        tooltip=["Plan", "Metric", "Score"]
    ).properties(height=150, width=96)
    return _cfg(ch.facet(column=alt.Column(
        "Metric:N", title=None,
        header=alt.Header(labelColor="#c7cee0", labelFont="Sora",
                          labelFontWeight=600, labelFontSize=12))))


# ---------------------------------------------------------- group fairness ---
def group_fairness(group: dict):
    pp = group.get("per_person") or {}
    if not pp:
        return None
    df = pd.DataFrame([{"Traveller": k, "Satisfaction": round(float(v), 3)}
                       for k, v in pp.items()])
    bars = alt.Chart(df).mark_bar(cornerRadiusEnd=6, width=42).encode(
        x=alt.X("Traveller:N", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Satisfaction:Q", title="Utility"),
        color=alt.Color("Satisfaction:Q", legend=None,
                        scale=alt.Scale(range=["#22d3ee", "#7c5cff", "#34d399"])),
        tooltip=["Traveller", "Satisfaction"])
    layers = [bars]
    floor = group.get("fairness_min")
    if floor is not None:
        layers.append(alt.Chart(pd.DataFrame({"f": [floor]})).mark_rule(
            color=AMBER, strokeWidth=2, strokeDash=[5, 4]).encode(
            y="f:Q", tooltip=alt.Tooltip("f:Q", title="fairness floor")))
    return _cfg(alt.layer(*layers).properties(height=190))


# --------------------------------------------------- itinerary distances -----
def itinerary_distance(candidate: dict):
    days = candidate.get("itinerary") or []
    rows = [{"Day": f"Day {d.get('day', i + 1)}",
             "km": round(float(d.get("total_km", 0)), 1),
             "stops": len(d.get("items", []))}
            for i, d in enumerate(days)]
    if not rows:
        return None
    df = pd.DataFrame(rows)
    area = alt.Chart(df).mark_area(
        line={"color": ACCENT2, "strokeWidth": 2}, interpolate="monotone",
        opacity=.5,
        color=alt.Gradient(gradient="linear",
                           stops=[alt.GradientStop(color="rgba(34,211,238,.05)", offset=0),
                                  alt.GradientStop(color="rgba(124,92,255,.5)", offset=1)],
                           x1=1, x2=1, y1=1, y2=0)).encode(
        x=alt.X("Day:N", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("km:Q", title="Transit km"),
        tooltip=["Day", alt.Tooltip("km:Q", title="km"),
                 alt.Tooltip("stops:Q", title="stops")])
    pts = alt.Chart(df).mark_point(size=70, filled=True, color=ACCENT2).encode(
        x="Day:N", y="km:Q")
    return _cfg(alt.layer(area, pts).properties(height=170))


# ------------------------------------------------------- agent cost/conf -----
def agent_cost(runs: list):
    if not runs:
        return None
    df = pd.DataFrame(runs)
    if "cost_usd" not in df or "agent" not in df:
        return None
    g = (df.groupby("agent", as_index=False)["cost_usd"].sum()
           .sort_values("cost_usd", ascending=False).head(14))
    if g["cost_usd"].sum() == 0:
        return None
    ch = alt.Chart(g).mark_bar(cornerRadiusEnd=5).encode(
        x=alt.X("cost_usd:Q", title="LLM cost (USD)", axis=alt.Axis(format="$.4f")),
        y=alt.Y("agent:N", sort="-x", title=None),
        color=alt.Color("cost_usd:Q", legend=None,
                        scale=alt.Scale(range=["#22d3ee", "#7c5cff"])),
        tooltip=["agent", alt.Tooltip("cost_usd:Q", format="$.5f")]
    ).properties(height=max(150, 24 * len(g)))
    return _cfg(ch)


def agent_confidence(runs: list):
    if not runs:
        return None
    df = pd.DataFrame(runs)
    if "confidence" not in df or "agent" not in df:
        return None
    g = df.groupby("agent", as_index=False)["confidence"].mean()
    ch = alt.Chart(g).mark_bar(cornerRadiusEnd=5).encode(
        x=alt.X("confidence:Q", title="Avg confidence", scale=alt.Scale(domain=[0, 1])),
        y=alt.Y("agent:N", sort="-x", title=None),
        color=alt.Color("confidence:Q", legend=None,
                        scale=alt.Scale(scheme="viridis", domain=[0, 1])),
        tooltip=["agent", alt.Tooltip("confidence:Q", format=".2f")]
    ).properties(height=max(150, 24 * len(g)))
    return _cfg(ch)


# ------------------------------------------------------------- seasonality ---
def seasonality(se: dict):
    """Min/max temperature band for the travel month."""
    if not se or "avg_high_c" not in se:
        return None
    df = pd.DataFrame([{"lo": se.get("avg_low_c", 0), "hi": se.get("avg_high_c", 0),
                        "m": f"Month {se.get('month', '')}"}])
    band = alt.Chart(df).mark_bar(cornerRadius=8, height=26).encode(
        x=alt.X("lo:Q", title="°C"), x2="hi:Q",
        y=alt.Y("m:N", title=None),
        color=alt.value(ACCENT),
        tooltip=[alt.Tooltip("lo:Q", title="avg low °C"),
                 alt.Tooltip("hi:Q", title="avg high °C")])
    return _cfg(band.properties(height=80))
