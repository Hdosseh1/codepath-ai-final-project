"""
app_ai_tab.py  —  Anicare AI Assistant Tab
==========================================
"""
from __future__ import annotations

import os
import anthropic
import streamlit as st

from ai_features import AnicareRAG, AnicareAgent


def _get_clients():
    ant_key = os.getenv("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY", "")
    gpl_key = os.getenv("GOOGLE_PLACES_KEY") or st.secrets.get("GOOGLE_PLACES_KEY", "")
    if not ant_key:
        return None, None, "ANTHROPIC_API_KEY is not set."
    if not gpl_key:
        return None, None, "GOOGLE_PLACES_KEY is not set."
    return anthropic.Anthropic(api_key=ant_key), gpl_key, None


def _pet_names(user):
    return [p.name for p in user.pets]


def _init_state():
    if "rag_result" not in st.session_state:
        st.session_state["rag_result"] = None
    if "agent_history" not in st.session_state:
        st.session_state["agent_history"] = []
    if "agent_messages" not in st.session_state:
        st.session_state["agent_messages"] = []  # raw Anthropic messages for context


def render_ai_tab(user) -> None:
    _init_state()

    st.subheader("🤖 AI Assistant")
    st.caption(
        "Powered by Claude · Uses your real location to find nearby services "
        "and can update your pet's schedule automatically."
    )

    client, gpl_key, err = _get_clients()
    if err:
        st.error(f"⚠️ {err}  Add it to your `.env` or Streamlit secrets to enable AI features.")
        return

    if not user.pets:
        st.info("Add at least one pet in the sidebar before using the AI assistant.")
        return

    with st.expander("📍 Your location", expanded=True):
        col_lat, col_lng = st.columns(2)
        with col_lat:
            lat = st.number_input("Latitude",  value=38.9897, format="%.4f", key="ai_lat")
        with col_lng:
            lng = st.number_input("Longitude", value=-77.0281, format="%.4f", key="ai_lng")
        st.caption("Tip: paste coordinates from Google Maps (right-click → 'What's here?').")

    st.divider()

    feature = st.radio(
        "What would you like to do?",
        options=["🔍 Find nearby places  (RAG)", "🤝 Ask the AI assistant  (Agent)"],
        horizontal=True,
        key="ai_feature",
    )

    st.divider()

    # =========================================================================
    # Feature 1 — RAG
    # =========================================================================
    if feature.startswith("🔍"):
        st.markdown("### Find nearby pet services")
        st.caption(
            "Retrieves real locations from Google Places, then Claude summarises "
            "them in the context of your pet's needs."
        )

        col1, col2 = st.columns(2)
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

        st.slider("Search radius (km)", min_value=1, max_value=20, value=5, key="rag_radius")
        question = st.text_input(
            "Your question",
            value="Which of these is best for my pet?",
            key="rag_question",
        )

        if st.button("🔍 Search & Ask Claude", type="primary", key="rag_run"):
            pet_name = None if pet_filter == "All pets" else pet_filter
            with st.spinner("Retrieving locations and generating answer…"):
                rag = AnicareRAG(client, gpl_key)
                result = rag.query(
                    user_question=question,
                    category=category,
                    lat=lat,
                    lng=lng,
                    pet_name=pet_name,
                )
            api_error = next(
                (p.get("_api_error") for p in result["places"] if "_api_error" in p), None
            )
            st.session_state["rag_result"] = {"error": api_error} if api_error else result

        # Always render stored result (persists across reruns)
        stored = st.session_state.get("rag_result")
        if stored:
            if "error" in stored:
                st.error(f"**Google Places API error:** {stored['error']}")
                if "REQUEST_DENIED" in stored["error"]:
                    st.warning("Enable **Places API** in Google Cloud Console and ensure billing is active.")
            else:
                conf = stored.get("confidence", {})
                level = conf.get("level", "Unknown")
                reason = conf.get("reason", "")
                color_map = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}
                icon = color_map.get(level, "⚪")
                st.markdown(f"**Confidence:** {icon} **{level}** &nbsp;·&nbsp; *{reason}*")
                st.markdown("#### Claude's recommendation")
                st.info(stored["answer"])

                with st.expander("📋 Raw locations retrieved (RAG context)", expanded=False):
                    st.text(stored["context"])

                clean = [p for p in stored["places"] if "_api_error" not in p]
                if clean:
                    st.markdown("#### Nearby locations")
                    for p in clean:
                        badge = (
                            "🟢 Open" if p["open_now"] is True
                            else "🔴 Closed" if p["open_now"] is False
                            else "⚪ Hours unknown"
                        )
                        st.markdown(
                            f"**{p['name']}** — {p['address']}  \n"
                            f"⭐ {p['rating']}/5 &nbsp; {badge}"
                        )

                if st.button("🗑️ Clear results", key="rag_clear"):
                    st.session_state["rag_result"] = None
                    st.rerun()

    # =========================================================================
    # Feature 2 — Agent with conversation history
    # =========================================================================
    else:
        st.markdown("### AI scheduling assistant")
        st.caption(
            "Claude autonomously decides which tools to call — searching nearby places, "
            "reading your schedule, adding tasks, and checking availability."
        )

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

        col_run, col_clear = st.columns([2, 1])
        with col_run:
            run_clicked = st.button("🤝 Run AI Agent", type="primary", key="agent_run")
        with col_clear:
            if st.button("🗑️ Clear history", key="agent_clear"):
                st.session_state["agent_history"] = []
                st.session_state["agent_messages"] = []
                st.rerun()

        if run_clicked:
            if not user_prompt.strip():
                st.warning("Please enter a request before running the agent.")
            else:
                with st.spinner("Agent is working… (may make multiple tool calls)"):
                    agent = AnicareAgent(client, gpl_key, user)
                    result = agent.run(
                        user_prompt,
                        lat=lat,
                        lng=lng,
                        conversation_history=st.session_state["agent_messages"],
                    )
                # Persist the updated conversation for next turn
                st.session_state["agent_messages"] = result.get("messages", [])
                st.session_state["agent_history"].insert(0, {
                    "prompt": user_prompt,
                    "result": result,
                })

        # Always render full conversation history (newest first)
        for entry in st.session_state.get("agent_history", []):
            prompt = entry["prompt"]
            result = entry["result"]

            st.markdown(f"---\n**You:** {prompt}")
            st.success(result["answer"])
            st.caption(
                f"Completed in {result['iterations']} "
                f"iteration{'s' if result['iterations'] != 1 else ''}."
            )

            if result["tool_log"]:
                with st.expander(
                    f"🔧 Tool calls ({len(result['tool_log'])} total) — agentic trace",
                    expanded=False,
                ):
                    for j, t in enumerate(result["tool_log"], 1):
                        st.markdown(f"**Step {j} — `{t['tool']}`**")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.caption("Input")
                            st.json(t["input"])
                        with c2:
                            st.caption("Result")
                            try:
                                st.json(t["result"])
                            except Exception:
                                st.text(t["result"])
                        st.divider()

            if any("add_location_to_schedule" in e["tool"] for e in result["tool_log"]):
                st.info(
                    "✅ A task was added to your pet's list. "
                    "Go to the sidebar and click **Generate schedule** to see it in your plan."
                )