"""Safar — Streamlit UI + observability dashboard (entry point). Owner: rishu.

Run:  streamlit run app.py   (pip install -r requirements.txt first)

Three tabs:
  🗺  Plan       — intake -> 3 candidates -> itinerary -> teams -> approval -> booking
  📡  On-Trip    — fire live events, watch minimal-disruption replanning (§12)
  📊  Dashboard  — observability (§19): agent runs, cost/confidence, events, bookings
"""
import streamlit as st

from safar.orchestrator import plan_trip, approve
from safar.engine import copilot, booking
from safar import store, events

st.set_page_config(page_title="Safar", page_icon="🧭", layout="wide")

LABELS = {"saver": "💸 Saver", "comfort": "🛋 Comfort", "balanced": "⚖️ Balanced"}
PRIORITY_W = {"budget": {"cost": 1.4, "comfort": 0.4}, "comfort": {"comfort": 1.4, "cost": 0.4},
              "experience": {"experience": 1.4}, "balanced": {}}


# ---------------------------------------------------------------- intake -----
with st.sidebar:
    st.title("🧭 Safar")
    st.caption("Multi-agent travel operating system")
    destination = st.text_input("Destination", "Tokyo")
    days = st.slider("Days", 2, 21, 5)
    budget = st.number_input("Budget (₹)", 30000, 1000000, 200000, step=10000)
    interests = st.multiselect("Interests",
                               ["food", "culture", "art", "city", "nature", "shopping"],
                               default=["food", "culture"])
    pace = st.select_slider("Pace", ["relaxed", "moderate", "packed"], "relaxed")
    col_a, col_b = st.columns(2)
    stars_min = col_a.slider("Min ★", 1, 5, 3)
    month = col_b.slider("Month", 1, 12, 11)
    home = st.text_input("Home country", "India")

    party = []
    if st.checkbox("Group trip (Nash bargaining)"):
        n = st.number_input("Travellers", 2, 4, 3)
        for i in range(int(n)):
            pr = st.selectbox(f"Traveller {i + 1} priority",
                              list(PRIORITY_W), key=f"pr{i}")
            party.append({"name": f"T{i + 1}", "weights": PRIORITY_W[pr]})

    if st.button("Plan my trip", type="primary", width="stretch"):
        with st.spinner("Agents → negotiate → ground → validate…"):
            st.session_state.state = plan_trip({
                "destination": destination, "days": days, "budget_inr": budget,
                "interests": interests, "pace": pace, "hotel_stars_min": stars_min,
                "travel_month": month, "home_country": home, "party": party,
            })
        for k in ("decision", "booking", "copilot"):
            st.session_state.pop(k, None)


state = st.session_state.get("state")
tab_plan, tab_ontrip, tab_dash = st.tabs(["🗺 Plan", "📡 On-Trip", "📊 Dashboard"])


# ============================================================= itinerary =====
def render_itinerary(cand):
    for day in cand.get("itinerary", []):
        st.markdown(f"**Day {day['day']}** · {day['total_km']} km")
        for i in day["items"]:
            tag = "🌤" if i["outdoor"] else "🏠"
            warn = " ⚠️ closes before you finish" if not i["within_hours"] else ""
            st.caption(f"{i['arrive']}–{i['depart']} · {tag} {i['name']} "
                       f"({i['area']}, +{i['travel_km']}km){warn}")


# ================================================================= PLAN =======
with tab_plan:
    if not state:
        st.info("Set your trip in the sidebar and press **Plan my trip**.")
    else:
        g = state.grounding or {}
        se = g.get("seasonality") or {}
        m1, m2, m3, m4 = st.columns(4)
        if (g.get("geo") or {}).get("display_name"):
            m1.metric("Destination", g["geo"]["display_name"].split(",")[0])
        if se:
            m2.metric(f"Typical wx (mo {se['month']})",
                      f"{se['avg_high_c']}°/{se['avg_low_c']}°", f"{se['rainy_days']} rainy d")
        m3.metric("Bundles", state.candidates.get("considered", 0),
                  f"{state.candidates.get('feasible_count', 0)} in budget")
        visa = g.get("visa") or {}
        m4.metric("Visa (" + str(g.get("country")) + ")",
                  "required" if visa.get("required") else
                  ("unknown" if visa.get("required") is None else "not required"))
        if g.get("wikivoyage"):
            st.caption(f"📖 {g['wikivoyage'].strip()[:220]}…")
        if state.candidates.get("note"):
            st.warning(state.candidates["note"])

        # candidates
        st.subheader("Candidates")
        cols = st.columns(3)
        for col, key in zip(cols, ("saver", "comfort", "balanced")):
            p = state.candidates.get(key)
            if not p:
                continue
            with col:
                st.markdown(f"### {LABELS[key]}")
                st.metric("Total", f"₹{p['cost_inr']:,.0f}", f"≈ ¥{p['cost_jpy']:,.0f}")
                st.progress(min(1.0, p["confidence"]),
                            text=f"confidence {int(p['confidence'] * 100)}%")
                if not p["feasible"]:
                    st.error("Over budget")
                st.write(f"✈ {p['flight']}")
                st.write(f"🏨 {p['hotel']}")
                st.write(f"🎫 {', '.join(p['activities'])}")
                st.caption(p["why"])
                if p.get("llm_note"):
                    st.info(f"🤖 {p['llm_note']}")
                with st.expander(f"Day-by-day ({len(p.get('itinerary', []))} days)"):
                    render_itinerary(p)

        # group fairness
        grp = state.candidates.get("group")
        if grp:
            st.subheader("Group fairness · " + grp["method"])
            gc = st.columns(len(grp["per_person"]))
            for c, (who, sat) in zip(gc, grp["per_person"].items()):
                c.metric(who, sat)
            st.caption(f"Nash product maximised; fairness floor {grp['fairness_min']}.")

        # teams
        with st.expander("🔎 Discovery / Risk / Support teams"):
            d, r, sup = state.discovery, state.risk, state.support
            t1, t2, t3 = st.columns(3)
            with t1:
                st.markdown("**Discovery**")
                st.caption("Local: " + ", ".join(
                    d.get("local_expert", {}).get("neighbourhood_picks", [])[:4]))
                st.caption("Food: " + ", ".join(
                    d.get("food", {}).get("food_spots", [])[:4]))
            with t2:
                st.markdown("**Risk**")
                st.caption("Weather: " + str(r.get("weather", {}).get("forecast_7d")))
                _ai = (r.get("weather", {}) or {}).get("ai_model") or {}
                if _ai:
                    st.caption(f"AI forecast: NVIDIA {_ai.get('model')} · {_ai.get('status')}")
                st.caption("Safety: " + str(r.get("safety", {}).get("advisory")))
                st.caption("Health: " + str(r.get("health", {}).get("guidance")))
            with t3:
                st.markdown("**Support**")
                st.caption("Packing: " + ", ".join(sup.get("packing", {}).get("items", [])[:5]))
                st.caption("Culture: " + "; ".join(sup.get("culture", {}).get("etiquette", [])[:3]))

        # validation + advisories
        if state.errors:
            st.error("Hard-constraint failures:\n" + "\n".join(f"- {e}" for e in state.errors))
        else:
            st.success("✓ all candidates pass hard constraints")
        if state.warnings:
            st.warning("Advisories (temporal / geo / weather / visa):\n"
                       + "\n".join(f"- {w}" for w in state.warnings))

        # approval gate (§10)
        st.subheader("Human approval")
        pick = st.radio("Pick a candidate", ["balanced", "saver", "comfort"], horizontal=True)
        a, b, c, d = st.columns(4)
        if a.button("✅ APPROVE", width="stretch"):
            approve(state, "APPROVE", pick=pick)
            st.session_state.decision = ("APPROVE", pick)
        if b.button("✏️ MODIFY", width="stretch"):
            st.session_state.decision = ("MODIFY", pick)
        if c.button("🔁 REPLAN", width="stretch"):
            st.session_state.decision = ("REPLAN", pick)
        if d.button("❌ REJECT", width="stretch"):
            st.session_state.decision = ("REJECT", pick)

        dec = st.session_state.get("decision")
        if dec and dec[0] == "APPROVE":
            st.success(f"Approved **{dec[1]}** → status **{state.status}**. "
                       f"Preferences learned; nothing charged.")
            if st.button("💳 Run booking saga (simulated — no real payment)"):
                st.session_state.booking = booking.execute(state, dec[1])
            if st.session_state.get("booking"):
                st.code("\n".join(st.session_state.booking["log"]), language="text")
        elif dec:
            st.info(f"Decision **{dec[0]}** recorded (status {state.status}).")


# ============================================================== ON-TRIP ======
with tab_ontrip:
    if not state or not (st.session_state.get("decision") or {}):
        st.info("Plan and approve a trip first, then simulate live events here.")
    else:
        st.subheader("On-Trip Copilot — live event → replan (§12)")
        st.caption("High-impact events need a human 'yes' before applying — never autonomous.")
        etype = st.selectbox("Event", ["flight_delay", "attraction_closed", "weather_alert"])
        event = {"type": etype}
        if etype == "flight_delay":
            event["minutes"] = st.slider("Delay (min)", 30, 360, 180, step=30)
        elif etype == "attraction_closed":
            names = state.candidates["balanced"]["activities"]
            event["name"] = st.selectbox("Which attraction closed?", names)
        else:
            days_n = [d["day"] for d in state.candidates["balanced"]["itinerary"]]
            event["day"] = st.selectbox("Which day?", days_n or [1])

        if st.button("Fire event", type="primary"):
            st.session_state.copilot = copilot.react(state, event)

        res = st.session_state.get("copilot")
        if res:
            for ch in res["impact"]["changes"]:
                st.write(f"→ {ch}")
            if res["needs_approval"]:
                st.warning("⚠ HIGH IMPACT — needs your approval before it changes the plan.")
            st.markdown("**Proposed itinerary:**")
            for day in res["new_itinerary"]:
                names = ", ".join(f"{i['arrive']} {i['name']}" for i in day["items"])
                st.caption(f"Day {day['day']}: {names or '(empty)'}")


# ============================================================= DASHBOARD ======
with tab_dash:
    st.subheader("Observability & audit (§19) — from SQLite (data/safar.db)")
    trips = store.list_trips(20)
    if not trips:
        st.info("No trips yet — plan one on the 🗺 Plan tab.")
    else:
        st.markdown("**Recent trips**")
        st.dataframe(trips, width="stretch", hide_index=True)
        if state:
            tid = state.trip_id
            s = store.agent_run_summary(tid)
            k1, k2, k3 = st.columns(3)
            k1.metric("Agent runs (this trip)", s["runs"])
            k2.metric("LLM cost (USD)", s["cost_usd"])
            k3.metric("Avg confidence", s["avg_confidence"])

            runs = store.agent_runs(tid)
            if runs:
                st.markdown("**Agent runs**")
                st.dataframe(runs, width="stretch", hide_index=True)
            bks = store.bookings(tid)
            if bks:
                st.markdown("**Bookings (saga)**")
                st.dataframe(bks, width="stretch", hide_index=True)
            evs = store.events(tid)
            if evs:
                st.markdown("**Event log (event-sourced)**")
                st.dataframe([{"seq": e["seq"], "type": e["type"]} for e in evs],
                             width="stretch", hide_index=True)

    st.divider()
    if st.button("Run eval harness (golden trips, §18)"):
        from safar import eval as ev
        with st.spinner("Running golden trips…"):
            rows, agg = ev.run(verbose=False)
        st.dataframe([{"trip": n, **m} for n, m in rows],
                     width="stretch", hide_index=True)
        st.json(agg)
