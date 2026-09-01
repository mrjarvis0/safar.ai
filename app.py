"""Safar — Streamlit UI + observability dashboard (entry point). Owner: rishu.

Run:  streamlit run app.py   (pip install -r requirements.txt first)

Three tabs:
  🗺  Plan       — intake -> 3 candidates -> itinerary -> teams -> approval -> booking
  📡  On-Trip    — fire live events, watch minimal-disruption replanning (§12)
  📊  Dashboard  — observability (§19): agent runs, cost/confidence, events, bookings

Presentation (theme + charts) lives in safar/ui/*; this file wires the agent
pipeline to those helpers. The pipeline calls are unchanged — UI is a skin.
"""
import streamlit as st

from safar.orchestrator import plan_trip, approve
from safar.engine import copilot, booking
from safar import store, events, config, monitor
from safar.gateway import payment
from safar.agents import ground_transport as gta
from safar.ui import theme as ui, charts as viz

st.set_page_config(page_title="Safar · Travel OS", page_icon="🧭", layout="wide")
ui.inject_theme()

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
        for k in ("decision", "booking", "copilot", "flight_poll"):
            st.session_state.pop(k, None)


state = st.session_state.get("state")

ui.hero()
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
        ui.section("Candidate plans", "three Pareto archetypes off the negotiation front")
        cols = st.columns(3)
        for col, key in zip(cols, ("saver", "comfort", "balanced")):
            p = state.candidates.get(key)
            if not p:
                continue
            with col:
                st.markdown(f"### {LABELS[key]}")
                st.metric("Total", f"₹{p['cost_inr']:,.0f}", f"≈ ¥{p['cost_jpy']:,.0f}")
                ui.gauge(p["confidence"], "confidence",
                         color=ui.ARCH_COLOR[key], size=118)
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

        # visual comparison — cost vs budget + score breakdown + daily distance
        ui.section("How the plans compare", "the numbers behind the trade-off")
        budget_inr = (state.constraints.get("hard", {}) or {}).get("budget_inr")
        cc = viz.candidate_cost(state.candidates, budget_inr)
        if cc is not None:
            st.markdown("**Total cost vs. your hard budget** "
                        "(dashed line = budget; faded bar = over budget)")
            st.altair_chart(cc, use_container_width=True)
        sb = viz.score_breakdown(state.candidates)
        if sb is not None:
            st.markdown("**Objective scores** — higher comfort/experience/safety is better; "
                        "cost is shown normalised (lower = cheaper)")
            st.altair_chart(sb, use_container_width=True)
        bal = state.candidates.get("balanced")
        idc = viz.itinerary_distance(bal) if bal else None
        if idc is not None:
            st.markdown("**Daily transit load** (Balanced plan) — flatter is a gentler pace")
            st.altair_chart(idc, use_container_width=True)

        # group fairness
        grp = state.candidates.get("group")
        if grp:
            ui.section("Group fairness", grp["method"])
            gf = viz.group_fairness(grp)
            if gf is not None:
                c_left, c_right = st.columns([3, 2])
                with c_left:
                    st.altair_chart(gf, use_container_width=True)
                with c_right:
                    st.caption(f"Nash product maximised across the party; the amber line "
                               f"is the fairness floor ({grp['fairness_min']}) — the least "
                               "satisfied traveller. No one gets crushed for the group.")
                    ui.chips([(who, str(sat)) for who, sat in grp["per_person"].items()])
            else:
                gc = st.columns(len(grp["per_person"]))
                for c, (who, sat) in zip(gc, grp["per_person"].items()):
                    c.metric(who, sat)

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

        # phase-2 intelligence — 10 specialised agents (§7), each guarded
        with st.expander("🧠 Phase-2 intelligence · 10 specialised agents"):
            sea, cr, fr = state.seasonality or {}, state.connection_risk or {}, state.fare_rules or {}
            ro, doc, con = state.route_opt or {}, state.document or {}, state.connectivity or {}
            sus, emg, prof = state.sustainability or {}, state.emergency or {}, state.traveler_profile or {}
            trn = state.transport or {}
            p1, p2, p3 = st.columns(3)
            with p1:
                st.markdown("**📅 Seasonality**")
                st.caption(f"{sea.get('crowd_level', '?')} crowds · {sea.get('crowd_note', '')}")
                st.markdown("**⏱ Connection risk**")
                _r = ((cr.get("risks") or [{}])[0] or {}).get("note", "no issues flagged")
                st.caption(f"{cr.get('flagged', 0)} flagged · {_r}")
                st.markdown("**🎫 Fare rules**")
                st.caption(str(fr.get("recommendation", "—")))
            with p2:
                st.markdown("**🗺 Route optimiser**")
                st.caption(f"{ro.get('optimisation', '—')} · {ro.get('total_transit_km', 0)} km")
                st.markdown("**📄 Documents**")
                st.caption(f"{doc.get('action_required', 0)} of {doc.get('total', 0)} need action")
                st.markdown("**📶 Connectivity**")
                st.caption(str(con.get("recommendation") or (con.get("esim") or {}).get("note", "—")))
            with p3:
                st.markdown("**🌱 Sustainability**")
                _cf = sus.get("carbon_footprint") or {}
                st.caption(f"{_cf.get('total_kg_co2', '?')} kg CO₂ · {_cf.get('equivalent', '')}")
                st.markdown("**🆘 Emergency**")
                _n = emg.get("emergency_numbers") or {}
                st.caption(f"Police {_n.get('police', '—')} · Amb {_n.get('ambulance', '—')}")
                st.markdown("**👤 Traveler profile**")
                st.caption("Cold start — sensible defaults" if prof.get("cold_start")
                           else f"Learned from {prof.get('history_length', 0)} past trip(s)")

            # sustainability / seasonality quick viz
            _cf = sus.get("carbon_footprint") or {}
            vcol1, vcol2 = st.columns(2)
            with vcol1:
                if _cf.get("total_kg_co2") is not None:
                    st.markdown("**Carbon footprint**")
                    ui.chips([("kg CO₂", str(_cf.get("total_kg_co2", "?"))),
                              ("≈", str(_cf.get("equivalent", "—")))])
            with vcol2:
                sc = viz.seasonality(se)
                if sc is not None:
                    st.markdown("**Typical temperature band**")
                    st.altair_chart(sc, use_container_width=True)

            # transport routing (§2c) — real OSRM road routes, primary + backup
            if trn.get("legs"):
                st.markdown("**🚕 Transport routing** · " + ("🟢 live OSRM"
                            if trn.get("live") else "⚪ estimate") + f" · {trn.get('total_km', 0)} km")
                for leg in trn["legs"]:
                    p = leg.get("primary") or {}
                    alts = leg.get("alternatives") or []
                    tail = (f" · {len(alts)} backup route(s)" if alts
                            else (" · fallback estimate" if leg.get("fallback") else ""))
                    st.caption(f"{leg['from']} → {leg['to']}: "
                               f"{p.get('distance_km', '?')} km / {p.get('duration_min', '?')} min"
                               f" [{leg.get('source', '?')}]" + tail)

        # validation + advisories
        if state.errors:
            st.error("Hard-constraint failures:\n" + "\n".join(f"- {e}" for e in state.errors))
        else:
            st.success("✓ all candidates pass hard constraints")
        if state.warnings:
            st.warning("Advisories (temporal / geo / weather / visa):\n"
                       + "\n".join(f"- {w}" for w in state.warnings))

        # intercity bus/train inventory (Phase 3b)
        with st.expander("🚌 Intercity bus / train (Phase 3b)"):
            grd = state.ground or {}
            if grd.get("leg"):
                st.caption(f"Auto-detected leg **{grd['leg'][0]} → {grd['leg'][1]}** · "
                           f"{grd.get('recommendation', '')}")
            src = (grd.get("status") or {})
            live = src.get("bus_api") == "live" or src.get("rail_api") == "live"
            st.caption(f"Inventory source: **{'live aggregator' if live else 'mock'}** "
                       "(set REDBUS_/RAIL_ keys for live RedBus-class + rail data).")
            gc1, gc2, gc3 = st.columns([2, 2, 1])
            frm = gc1.text_input("From", grd.get("leg", ["Delhi"])[0] if grd.get("leg") else "Delhi")
            to = gc2.text_input("To", grd.get("leg", ["", "Agra"])[1] if grd.get("leg") else "Agra")
            if gc3.button("Search"):
                st.session_state.ground_search = gta.search(frm, to)
            gs = st.session_state.get("ground_search")
            if gs:
                bt1, bt2 = st.columns(2)
                with bt1:
                    st.markdown("**🚆 Trains**")
                    for t in gs["trains"][:4]:
                        flag = "" if t["bookable"] else " · ⚠ waitlist"
                        st.caption(t["summary"] + flag)
                with bt2:
                    st.markdown("**🚌 Buses**")
                    for bopt in gs["buses"][:4]:
                        flag = "" if bopt["bookable"] else " · ⚠ sold out"
                        st.caption(bopt["summary"] + flag)

        # approval gate (§10)
        ui.section("Human approval", "nothing irreversible happens without your yes")
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
            mode = config.booking_mode()
            st.success(f"Approved **{dec[1]}** → status **{state.status}**. "
                       f"Preferences learned; nothing charged.")
            st.caption(f"Booking mode **{mode}** · payment **{payment.active_provider()}** — "
                       "capture is human-confirmed only; Safar never captures money "
                       "autonomously and never touches card data (§13).")
            label = ("💳 Run booking saga (simulated — no real payment)" if mode == "simulate"
                     else "💳 Book (live) — reserves seat + creates payment order, you complete checkout")
            if st.button(label):
                st.session_state.booking = booking.execute(state, dec[1])
                st.session_state.pop("capture", None)
            bk = st.session_state.get("booking")
            if bk:
                st.code("\n".join(bk["log"]), language="text")
                if bk.get("status") == "AWAITING_PAYMENT":
                    st.warning(f"⏸ **Awaiting payment** — order `{bk['order_id']}`, "
                               f"₹{bk['amount_inr']:,.0f}. Complete checkout in your PSP's "
                               "hosted page (Safar never sees card data), then confirm below.")
                    with st.form("confirm_pay"):
                        demo = payment.active_provider() == "mock"
                        pay_id = st.text_input("Payment ID from checkout",
                                               value="pay_mock_demo" if demo else "")
                        sig = st.text_input("Razorpay signature (optional)", value="")
                        human_ok = st.checkbox("I completed the payment — capture it now")
                        if st.form_submit_button("✅ Confirm payment & capture"):
                            st.session_state.capture = booking.confirm_payment(
                                state, bk.get("idem", ""), pay_id,
                                order_id=bk.get("order_id", ""), signature=sig,
                                human_confirmed=human_ok)
                    cap = st.session_state.get("capture")
                    if cap:
                        msg = "\n".join(cap.get("log") or [cap.get("reason", "")])
                        (st.success if cap["status"] == "BOOKED" else st.error)(msg)
                elif bk.get("status") == "NEEDS_INPUT":
                    st.info("Live flight order needs **traveler details** (name / DOB / "
                            "passport) supplied by a human — Safar never fabricates "
                            "passenger identities. Add them where you drive the booking API.")
        elif dec:
            st.info(f"Decision **{dec[0]}** recorded (status {state.status}).")


# ============================================================== ON-TRIP ======
with tab_ontrip:
    if not state or not (st.session_state.get("decision") or {}):
        st.info("Plan and approve a trip first, then simulate live events here.")
    else:
        ui.section("On-Trip Copilot", "live event → minimal-disruption re-plan (§12)")
        st.caption("High-impact events need a human 'yes' before applying — never autonomous.")

        # --- Live flight status → auto re-plan (§2b) --------------------------
        copilot.attach(state)          # subscribe this trip's copilot to the bus (idempotent)
        _live_src = bool(config.AVIATIONSTACK_API_KEY or config.AERODATABOX_API_KEY)
        with st.container(border=True):
            st.markdown("**✈️ Live flight status → auto re-plan**")
            _default_fn = monitor.resolve_flight_no(state) or "AI840"
            fc1, fc2 = st.columns([2, 3])
            fn = fc1.text_input("Flight number", _default_fn,
                                help="Amadeus fills this automatically; edit to track your real flight.")
            st.caption(("🟢 Live source configured (AviationStack/AeroDataBox)."
                        if _live_src else
                        "⚪ No status API key set — using a simulated delay so the flow still runs. "
                        "Add AVIATIONSTACK_API_KEY to .env for live data."))
            sim = None
            if not _live_src:
                sim = fc2.slider("Simulate delay (min)", 0, 300, 90, step=15)
            if st.button("Check live status", type="primary"):
                st.session_state.flight_poll = monitor.poll(state, flight_no=fn, demo_delay=sim)

            poll = st.session_state.get("flight_poll")
            if poll:
                s = poll["status"]
                st.write(f"**{poll['flight_no']}** — status: `{s.get('status', '?')}` · "
                         f"delay **{poll['delay_minutes']} min** · source `{s.get('source', '?')}`"
                         + ("  ·  🟢 live" if poll["live"] else "  ·  ⚪ demo"))
                if poll["replanned"]:
                    st.warning(f"⚠ Delay ≥ {poll['threshold_min']} min — Copilot proposed a re-plan "
                               "(needs your approval; not applied automatically).")
                    for r in poll["reactions"]:
                        for ch in r["impact"]["changes"]:
                            st.write(f"→ {ch}")
                elif poll["delay_minutes"] > 0:
                    st.info(f"Delay under the {poll['threshold_min']}-min threshold — no re-plan needed.")
                else:
                    st.success("On time — nothing to change.")

        st.divider()
        st.markdown("**🧪 Simulate any event** (manual)")
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
    ui.section("Observability & audit", "§19 — every agent run traced")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Data store", store.backend())
    d2.metric("Booking mode", config.booking_mode())
    d3.metric("Payment PSP", payment.active_provider())
    _gs = gta.gt.status()
    d4.metric("Ground inventory",
              "live" if (_gs.get("bus_api") == "live" or _gs.get("rail_api") == "live") else "mock")
    st.caption("Capture is human-confirmed only; Safar never captures money "
               "autonomously and never stores card data (§13). Set DATABASE_URL for "
               "Postgres, PAYMENT_PROVIDER + keys to go live.")
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
                ac, af = viz.agent_cost(runs), viz.agent_confidence(runs)
                if ac is not None or af is not None:
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if ac is not None:
                            st.markdown("**LLM cost by agent**")
                            st.altair_chart(ac, use_container_width=True)
                        else:
                            st.caption("Cost is $0 (no LLM key set — deterministic tools only).")
                    with cc2:
                        if af is not None:
                            st.markdown("**Confidence by agent**")
                            st.altair_chart(af, use_container_width=True)
                with st.expander("Raw agent runs"):
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
