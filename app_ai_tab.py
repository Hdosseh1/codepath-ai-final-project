"""
app_ai_tab.py  —  PawPal AI Assistant Tab
==========================================
This file contains the Streamlit UI for the two new AI features.

HOW TO INTEGRATE INTO app.py
-----------------------------
1.  At the top of app.py, add:

        from app_ai_tab import render_ai_tab

2.  In the tab list, add a third tab:

        tab1, tab2, tab3 = st.tabs(["📋 Tasks", "📅 Schedule", "🤖 AI Assistant"])

3.  At the bottom of app.py, add:

        with tab3:
            render_ai_tab(user)

4.  Add to your .env / Streamlit secrets:

        ANTHROPIC_API_KEY   = "sk-ant-..."
        GOOGLE_PLACES_KEY   = "AIza..."

That's it — no changes to existing tabs required.
"""
from __future__ import annotations
import os
import anthropic
import streamlit as st

from ai_features import PawPalRAG, PawPalAgent
from pawpal_system import UserDataManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_clients() -> tuple[anthropic.Anthropic | None, str | None, str | None]:
    """Return (anthropic_client, google_key, error_message)."""
    ant_key = os.getenv("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY", "")
    gpl_key = os.getenv("GOOGLE_PLACES_KEY") or st.secrets.get("GOOGLE_PLACES_KEY", "")
    if not ant_key:
        return None, None, "ANTHROPIC_API_KEY is not set."
    if not gpl_key:
        return None, None, "GOOGLE_PLACES_KEY is not set."
    return anthropic.Anthropic(api_key=ant_key), gpl_key, None


def _pet_names(user) -> list[str]:
    return [p.name for p in user.pets]


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_ai_tab(user) -> None:
    """Render the full AI Assistant tab inside a Streamlit app."""

    st.subheader("🤖 AI Assistant")
    st.caption(
        "Powered by Claude · Uses your real location to find nearby services "
        "and can update your pet's schedule automatically."
    )

    # --- API key check ---
    client, gpl_key, err = _get_clients()
    if err:
        st.error(f"⚠️ {err}  Add it to your `.env` or Streamlit secrets to enable AI features.")
        return

    if not user.pets:
        st.info("Add at least one pet in the sidebar before using the AI assistant.")
        return

    # -----------------------------------------------------------------------
    # Location input  (sidebar-style inline form)
    # -----------------------------------------------------------------------
    with st.expander("📍 Your location", expanded=True):
        col_lat, col_lng = st.columns(2)
        with col_lat:
            lat = st.number_input(
                "Latitude",
                value=38.9897,
                format="%.4f",
                help="Your approximate latitude",
                key="ai_lat",
            )
        with col_lng:
            lng = st.number_input(
                "Longitude",
                value=-77.0281,
                format="%.4f",
                help="Your approximate longitude",
                key="ai_lng",
            )
        st.caption(
            "Tip: paste coordinates from Google Maps (right-click → 'What's here?')."
        )

    st.divider()

    # -----------------------------------------------------------------------
    # Feature selector
    # -----------------------------------------------------------------------
    feature = st.radio(
        "What would you like to do?",
        options=[
            "🔍 Find nearby places  (RAG)",
            "🤝 Ask the AI assistant  (Agent)",
        ],
        horizontal=True,
        key="ai_feature",
    )

    st.divider()

    # =======================================================================
    # Feature 1 — RAG: Find nearby places
    # =======================================================================
    if feature.startswith("🔍"):
        st.markdown("### Find nearby pet services")
        st.caption(
            "Retrieves real locations from Google Places, then Claude summarises "
            "them in the context of your pet's needs."
        )

        col1, col2 = st.columns([1, 1])
        with col1:
            category = st.selectbox(
                "Service type",
                options=["vet", "park", "pet_store"],
                format_func=lambda c: {
                    "vet": "🏥 Veterinary clinic",
                    "park": "🌳 Dog / pet park",
                    "pet_store": "🛒 Pet supply store",
                }[c],
                key="rag_category",
            )
        with col2:
            pet_filter = st.selectbox(
                "For which pet? (optional)",
                options=["All pets"] + _pet_names(user),
                key="rag_pet",
            )

        radius = st.slider(
            "Search radius (km)",
            min_value=1,
            max_value=20,
            value=5,
            key="rag_radius",
        )

        question = st.text_input(
            "Your question",
            value=f"Which of these is best for my pet?",
            key="rag_question",
        )

        if st.button("🔍 Search & Ask Claude", type="primary", key="rag_run"):
            pet_name = None if pet_filter == "All pets" else pet_filter
            with st.spinner("Retrieving locations and generating answer…"):
                rag = PawPalRAG(client, gpl_key)
                result = rag.query(
                    user_question=question,
                    category=category,
                    lat=lat,
                    lng=lng,
                    pet_name=pet_name,
                )

            # --- Answer ---
            st.markdown("#### Claude's recommendation")
            st.info(result["answer"])

            # --- Retrieved data (collapsed) ---
            with st.expander("📋 Raw locations retrieved (RAG context)", expanded=False):
                st.text(result["context"])

            # --- Place cards ---
            if result["places"]:
                st.markdown("#### Nearby locations")
                for p in result["places"]:
                    open_badge = (
                        "🟢 Open"
                        if p["open_now"] is True
                        else ("🔴 Closed" if p["open_now"] is False else "⚪ Hours unknown")
                    )
                    st.markdown(
                        f"**{p['name']}** — {p['address']}  \n"
                        f"⭐ {p['rating']}/5 &nbsp; {open_badge}"
                    )

    # =======================================================================
    # Feature 2 — Agent: AI assistant with tool use
    # =======================================================================
    else:
        st.markdown("### AI scheduling assistant")
        st.caption(
            "Claude autonomously decides which tools to call — searching nearby places, "
            "reading your schedule, adding tasks, and checking availability."
        )

        # --- Example prompts ---
        examples = [
            "Find the best-rated vet near me and add a 60-minute appointment to Max's schedule for tomorrow morning.",
            "What is Max's next vet appointment, and are there any open vets near me right now?",
            "Find a dog park nearby and add a 45-minute park visit to Bella's schedule this evening.",
            "Check whether City Animal Hospital is open and, if so, add a vet visit for Luna.",
        ]
        selected_example = st.selectbox(
            "Try an example prompt (or type your own below)",
            options=["— custom —"] + examples,
            key="agent_example",
        )

        default_prompt = "" if selected_example == "— custom —" else selected_example
        user_prompt = st.text_area(
            "Your request",
            value=default_prompt,
            height=100,
            key="agent_prompt",
            placeholder="e.g. Find a good vet near me and add an appointment for Max on Saturday morning.",
        )

        if st.button("🤝 Run AI Agent", type="primary", key="agent_run"):
            if not user_prompt.strip():
                st.warning("Please enter a request before running the agent.")
            else:
                with st.spinner("Agent is working… (may make multiple tool calls)"):
                    agent = PawPalAgent(client, gpl_key, user)
                    result = agent.run(user_prompt, lat=lat, lng=lng)

                # Persist user data if the agent added a task
                any_added = any(
                    entry["tool"] == "add_location_to_schedule"
                    for entry in result["tool_log"]
                )
                if any_added:
                    try:
                        UserDataManager().save_user(user)
                    except Exception:
                        pass

                # --- Final answer ---
                st.markdown("#### Agent response")
                st.success(result["answer"])

                st.caption(
                    f"Completed in {result['iterations']} "
                    f"iteration{'s' if result['iterations'] != 1 else ''}."
                )

                # --- Tool call log (for transparency / rubric) ---
                if result["tool_log"]:
                    with st.expander(
                        f"🔧 Tool calls ({len(result['tool_log'])} total) — agentic trace",
                        expanded=False,
                    ):
                        for i, entry in enumerate(result["tool_log"], 1):
                            st.markdown(f"**Step {i} — `{entry['tool']}`**")
                            col_in, col_out = st.columns(2)
                            with col_in:
                                st.caption("Input")
                                st.json(entry["input"])
                            with col_out:
                                st.caption("Result")
                                try:
                                    st.json(entry["result"])
                                except Exception:
                                    st.text(entry["result"])
                            st.divider()

                # Remind user to regenerate schedule if a task was added
                any_added = any(
                    "add_location_to_schedule" in e["tool"] for e in result["tool_log"]
                )
                if any_added:
                    st.info(
                        "✅ A task was added to your pet's list. "
                        "Go to the sidebar and click **Generate schedule** to see it in your plan."
                    )