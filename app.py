"""Safar — Streamlit UI (entry point).  Owner: rishu.

Run:  streamlit run app.py

Screens to build (team-work.md section 3, rishu):
  1. Intake     -> destination, days, budget, interests, pace
  2. Candidates -> 3 plans (Saver / Comfort / Balanced) side by side
  3. Approval   -> APPROVE / MODIFY / REPLAN, show the "why" + confidence + cost
"""
import streamlit as st

st.set_page_config(page_title="Safar", page_icon="🧭", layout="wide")
st.title("🧭 Safar — Multi-Agent Trip Planner")

st.info("Skeleton — build the intake form, candidate cards, and the approval gate here.")

# TODO(rishu): from safar.orchestrator import plan_trip
# TODO(rishu): render intake form -> call plan_trip(...) -> show 3 candidates -> approval buttons
