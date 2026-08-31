"""Reusable Streamlit UI helpers. Owner: rishu.

candidate_card: renders a Pareto candidate (cost / comfort / scores / why / itinerary).
team_details: renders Discovery / Risk / Support team outputs in expandable form.
"""
import streamlit as st

LABELS = {"saver": "💸 Saver", "comfort": "🛋 Comfort", "balanced": "⚖️ Balanced"}


def candidate_card(name: str, plan: dict) -> None:
    """Render a full plan card: cost, flight, hotel, activities, scores, why, itinerary."""
    if not plan:
        st.caption(f"{name}: no plan generated")
        return

    label = LABELS.get(name, name.title())
    st.markdown(f"### {label}")

    # Cost + confidence
    st.metric("Total", f"₹{plan['cost_inr']:,.0f}", f"≈ ¥{plan.get('cost_jpy', 0):,.0f}")
    conf = plan.get("confidence", 0)
    st.progress(min(1.0, conf), text=f"confidence {int(conf * 100)}%")

    if not plan.get("feasible", True):
        st.error("⚠ Over budget")

    # Flight / hotel / activities
    st.write(f"✈ {plan.get('flight', '—')}")
    st.write(f"🏨 {plan.get('hotel', '—')}")
    acts = plan.get("activities", [])
    if acts:
        st.write(f"🎫 {', '.join(acts)}")

    # Scores
    scores = plan.get("scores", {})
    if scores:
        cols = st.columns(len(scores))
        for col, (k, v) in zip(cols, scores.items()):
            col.metric(k.title(), round(v, 2))

    # Why
    why = plan.get("why")
    if why:
        st.caption(why)

    # LLM note (if available)
    llm_note = plan.get("llm_note")
    if llm_note:
        st.info(f"🤖 {llm_note}")

    # Day-by-day itinerary
    itin = plan.get("itinerary", [])
    if itin:
        with st.expander(f"Day-by-day ({len(itin)} days)"):
            for day in itin:
                st.markdown(f"**Day {day['day']}** · {day['total_km']} km")
                for i in day["items"]:
                    tag = "🌤" if i.get("outdoor") else "🏠"
                    warn = " ⚠️ closes before you finish" if not i.get("within_hours", True) else ""
                    st.caption(f"{i['arrive']}–{i['depart']} · {tag} {i['name']} "
                               f"({i.get('area', '—')}, +{i['travel_km']}km){warn}")


def team_details(state) -> None:
    """Render Discovery / Risk / Support team outputs in a three-column layout."""
    d = getattr(state, "discovery", {}) or {}
    r = getattr(state, "risk", {}) or {}
    sup = getattr(state, "support", {}) or {}

    t1, t2, t3 = st.columns(3)
    with t1:
        st.markdown("**Discovery**")
        picks = d.get("local_expert", {}).get("neighbourhood_picks", [])
        if picks:
            st.caption("Local: " + ", ".join(picks[:4]))
        food_spots = d.get("food", {}).get("food_spots", [])
        if food_spots:
            st.caption("Food: " + ", ".join(food_spots[:4]))
        dest_info = d.get("destination", {})
        if dest_info.get("description"):
            st.caption(f"About: {dest_info['description']}")

    with t2:
        st.markdown("**Risk**")
        wx = r.get("weather", {})
        if wx.get("forecast_7d"):
            st.caption(f"Weather: {wx['forecast_7d']}")
        safety = r.get("safety", {})
        if safety.get("advisory"):
            st.caption(f"Safety: {safety['advisory']}")
        health = r.get("health", {})
        if health.get("guidance"):
            st.caption(f"Health: {health['guidance']}")
        ins = r.get("insurance", {})
        if ins.get("recommended_cover"):
            st.caption(f"Insurance: {', '.join(ins['recommended_cover'][:3])}")

    with t3:
        st.markdown("**Support**")
        packing = sup.get("packing", {})
        if packing.get("items"):
            st.caption("Packing: " + ", ".join(packing["items"][:5]))
        culture = sup.get("culture", {})
        if culture.get("etiquette"):
            st.caption("Culture: " + "; ".join(culture["etiquette"][:3]))
        transport = sup.get("transport", {})
        if transport.get("intra_city"):
            st.caption(f"Transport: {transport['intra_city']}")
