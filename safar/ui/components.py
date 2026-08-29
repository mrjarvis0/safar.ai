"""Reusable Streamlit UI helpers. Owner: rishu."""
import streamlit as st


def candidate_card(name: str, plan: dict) -> None:
    # TODO(rishu): render a plan card: cost / comfort / walking / risk + the "why"
    st.subheader(name)
    st.caption("TODO: render plan details")
