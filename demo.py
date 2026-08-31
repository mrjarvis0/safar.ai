"""Safar — headless end-to-end demo (no Streamlit needed).

    python demo.py

Runs the full loop: intake -> agents -> negotiate -> validate -> ground ->
3 candidates -> human approval gate. Prints everything to the console.
"""
import sys

from safar.orchestrator import plan_trip, approve

# Windows consoles default to cp1252 and choke on ₹/¥/★ — force UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

LINE = "─" * 72


def rupees(x: float) -> str:
    return f"₹{x:,.0f}"


def show(state) -> None:
    t = state.trip
    print(LINE)
    print(f"🧭  SAFAR — trip {state.trip_id}   status: {state.status}")
    print(f"    {t['destination']} · {t['days']} days · interests {t['interests']} · "
          f"pace {t['pace']}")
    print(f"    Hard budget: {rupees(state.constraints['hard']['budget_inr'])}   "
          f"weights {state.weights}")

    g = state.grounding
    if g:
        print(LINE)
        print("GROUNDING (live, free sources)")
        geo = g.get("geo") or {}
        if geo.get("display_name"):
            print(f"  • OSM: {geo['display_name']}  ({geo.get('lat')}, {geo.get('lon')})")
        se = g.get("seasonality") or {}
        if se:
            print(f"  • Seasonality (month {se['month']}, {se['year']}): "
                  f"avg high {se['avg_high_c']}°C / low {se['avg_low_c']}°C, "
                  f"{se['rainy_days']} rainy days")
        if g.get("wikivoyage"):
            print(f"  • Wikivoyage: {g['wikivoyage'].strip()[:200]}…")
        if g.get("optd"):
            o = g["optd"]
            print(f"  • OPTD (offline): IATA {o.get('iata')} · {o.get('timezone')} · "
                  f"{o.get('country')}")

    d, r, sup = state.discovery, state.risk, state.support
    if d or r or sup:
        print(LINE)
        print("TEAMS (Phase 2 breadth — grounded on free sources)")
        if d.get("local_expert", {}).get("neighbourhood_picks"):
            print(f"  • Local Expert : {', '.join(d['local_expert']['neighbourhood_picks'][:4])}")
        if d.get("food", {}).get("food_spots"):
            print(f"  • Food         : {', '.join(d['food']['food_spots'][:4])}")
        if r.get("weather"):
            print(f"  • Weather      : {r['weather'].get('forecast_7d')}")
        if r.get("safety"):
            print(f"  • Safety       : {r['safety'].get('advisory')}")
        if r.get("health"):
            print(f"  • Health       : {r['health'].get('guidance')}")
        if sup.get("packing", {}).get("items"):
            print(f"  • Packing      : {', '.join(sup['packing']['items'][:5])}")
        if sup.get("culture", {}).get("etiquette"):
            print(f"  • Culture      : {'; '.join(sup['culture']['etiquette'][:3])}")

    c = state.candidates
    print(LINE)
    print(f"CANDIDATES  (considered {c.get('considered', 0)} bundles, "
          f"{c.get('feasible_count', 0)} within budget)")
    for key, label in (("saver", "SAVER"), ("comfort", "COMFORT"),
                       ("balanced", "BALANCED ★")):
        p = c.get(key)
        if not p:
            continue
        flag = "" if p["feasible"] else "  ⚠ OVER BUDGET"
        print(f"\n  [{label}]  {rupees(p['cost_inr'])}  ≈ ¥{p['cost_jpy']:,.0f}"
              f"   confidence {int(p['confidence'] * 100)}%{flag}")
        print(f"    ✈  {p['flight']}")
        print(f"    🏨 {p['hotel']}")
        print(f"    🎫 {', '.join(p['activities'])}")
        print(f"    utility {p['scores']['utility']}  "
              f"(comfort {p['scores']['comfort']}, experience {p['scores']['experience']})")
        print(f"    why: {p['why']}")
        if p.get("llm_note"):
            print(f"    🤖 {p['llm_note']}")

    if c.get("note"):
        print(f"\n  NOTE: {c['note']}")

    # Day-by-day itinerary for the recommended (Balanced) plan
    bal = c.get("balanced")
    if bal and bal.get("itinerary"):
        print(LINE)
        print("ITINERARY — Balanced (nearest-neighbour route, opening-hours aware)")
        for day in bal["itinerary"]:
            print(f"  Day {day['day']}  ({day['total_km']} km)")
            for i in day["items"]:
                warn = "" if i["within_hours"] else "  ⚠ closes before you finish"
                out_in = "outdoor" if i["outdoor"] else "indoor"
                print(f"    {i['arrive']}–{i['depart']}  {i['name']} "
                      f"({i['area']}, {out_in}, +{i['travel_km']}km){warn}")

    # Group fairness (Nash bargaining), if a party was given
    grp = c.get("group")
    if grp:
        print(LINE)
        print(f"GROUP ({grp['method']}) — per-person satisfaction, "
              f"fairness floor {grp['fairness_min']}")
        for who, sat in grp["per_person"].items():
            print(f"    {who:12} {sat}")

    print(LINE)
    if state.errors:
        print("VALIDATION — ✗ HARD failures:")
        for e in state.errors:
            print(f"    ✗ {e}")
    else:
        print("VALIDATION — ✓ all candidates pass hard constraints")
    if state.warnings:
        print("ADVISORIES (soft — temporal / geo / weather / visa):")
        for w in state.warnings:
            print(f"    • {w}")
    print(LINE)


def main() -> None:
    intake = {
        "destination": "Tokyo",
        "days": 5,
        "budget_inr": 200000,
        "interests": ["food", "culture"],
        "pace": "relaxed",
        "travel_month": 11,
    }
    state = plan_trip(intake)
    show(state)

    # Human-in-the-loop gate. Prompt if interactive; auto-approve Balanced if
    # stdin is closed/piped (EOF) so the demo always finishes cleanly.
    choice = "APPROVE"
    try:
        raw = input("APPROVE / MODIFY / REPLAN / REJECT (default APPROVE): ").strip().upper()
        choice = raw or "APPROVE"
    except (EOFError, KeyboardInterrupt):
        print("APPROVE  (non-interactive)")
    approve(state, choice, pick="balanced")
    print(f"\nHITL decision: {choice}  ->  trip status: {state.status}")
    if state.status == "APPROVED":
        from safar import store
        from safar.engine import booking
        b = state.candidates["balanced"]
        obs = store.agent_run_summary(state.trip_id)
        print(f"Approved plan: BALANCED  {rupees(b['cost_inr'])}")
        print(f"Observability: {obs['runs']} agent runs logged, "
              f"avg confidence {obs['avg_confidence']}  (SQLite: data/safar.db)")
        print(f"Personalization: profile updated -> {state.weights}")

        # Booking saga (SIMULATED — no real payment, no card data)
        print("\nBOOKING SAGA (simulated):")
        for line in booking.execute(state, "balanced")["log"]:
            print(f"    {line}")


if __name__ == "__main__":
    main()
