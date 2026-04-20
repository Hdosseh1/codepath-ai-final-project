from __future__ import annotations

import streamlit as st
from datetime import datetime, time
import uuid
import base64
import os
from typing import Optional

from anicare_system import User, Pet, Task, TaskScheduler, UserDataManager
from app_ai_tab import render_ai_tab
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Anicare+",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------
# Theme CSS
# -----------------------

ORANGE = "#E87722"
ORANGE_DARK = "#C45E00"
ORANGE_LIGHT = "#FFF3E0"

def _img_to_b64(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

# Load login background if it exists
login_bg_b64 = _img_to_b64("assets/login_bg.png") or _img_to_b64("assets/login_bg.jpg")
login_bg_css = (
    f"background-image: url('data:image/png;base64,{login_bg_b64}'); "
    "background-size: cover; background-position: center;"
    if login_bg_b64
    else f"background: {ORANGE};"
)

st.markdown(f"""
<style>
/* ── Full app background (covers entire viewport) ── */
.stApp {{
    background-color: #FFFFFF !important;
}}

/* ── Main content area: white ── */
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main .block-container {{
    background-color: #FFFFFF !important;
    color: #1a1a1a !important;
}}

/* ── Sidebar: orange ── */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div {{
    background-color: {ORANGE} !important;
}}
[data-testid="stSidebar"] * {{
    color: #FFFFFF !important;
}}
[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] .stSelectbox select,
[data-testid="stSidebar"] .stNumberInput input {{
    background-color: rgba(0,0,0,0.2) !important;
    color: #fff !important;
    border: 1px solid rgba(255,255,255,0.4) !important;
    border-radius: 6px !important;
}}
[data-testid="stSidebar"] .stButton > button {{
    background-color: #FFFFFF !important;
    color: {ORANGE_DARK} !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 8px !important;
}}
[data-testid="stSidebar"] .stButton > button * {{
    color: {ORANGE_DARK} !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background-color: {ORANGE_LIGHT} !important;
}}
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton > button[kind="primary"] * {{
    background-color: #1a1a1a !important;
    color: #FFFFFF !important;
}}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {{
    background-color: #333333 !important;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    background-color: #FFFFFF !important;
    border-bottom: 2px solid {ORANGE} !important;
}}
.stTabs [data-baseweb="tab"] {{
    color: #555 !important;
}}
.stTabs [aria-selected="true"] {{
    color: {ORANGE} !important;
    border-bottom: 2px solid {ORANGE} !important;
}}

/* ── Primary buttons ── */
.stButton > button[kind="primary"],
.stFormSubmitButton > button {{
    background-color: {ORANGE} !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
}}
.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button:hover {{
    background-color: {ORANGE_DARK} !important;
}}

/* ── Expanders ── */
[data-testid="stExpander"] {{
    border: 1px solid {ORANGE}33 !important;
    border-radius: 8px !important;
}}

/* ── Text in main area ── */
h1, h2, h3, p, label, .stMarkdown {{
    color: #1a1a1a !important;
}}

/* ── LOGIN PAGE STYLES ── */

/* Full-page background when on login screen */
.login-bg .stApp,
.login-bg [data-testid="stAppViewContainer"],
.login-bg [data-testid="stMain"],
.login-bg .main .block-container {{
    {login_bg_css}
    background-color: transparent !important;
}}

/* Style the Streamlit form as a white card */
[data-testid="stForm"] {{
    background: rgba(255, 255, 255, 0.97) !important;
    border-radius: 16px !important;
    padding: 40px 36px !important;
    box-shadow: 0 8px 40px rgba(0, 0, 0, 0.22) !important;
    border: none !important;
    max-width: 420px !important;
    margin: 0 auto !important;
}}

/* Light input field on login */
[data-testid="stForm"] [data-testid="stTextInput"] input {{
    background-color: #f7f7f7 !important;
    color: #1a1a1a !important;
    border: 1.5px solid #ddd !important;
    border-radius: 8px !important;
}}
[data-testid="stForm"] label {{
    color: #444 !important;
    font-weight: 500 !important;
}}
</style>
""", unsafe_allow_html=True)

# -----------------------
# Session state init
# -----------------------

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "login_username" not in st.session_state:
    st.session_state["login_username"] = ""
if "archived_tasks" not in st.session_state:
    st.session_state["archived_tasks"] = []
if "last_schedule" not in st.session_state:
    st.session_state["last_schedule"] = None

# -----------------------
# Login page
# -----------------------

if not st.session_state["logged_in"]:
    # Inject background image + hide sidebar + hide header on login
    bg_style = (
        f"background-image: url('data:image/png;base64,{login_bg_b64}') !important;"
        "background-size: cover !important; background-position: center !important;"
        if login_bg_b64
        else f"background-color: {ORANGE} !important;"
    )
    st.markdown(f"""
    <style>
    [data-testid="stSidebar"] {{ display: none !important; }}
    [data-testid="stHeader"]  {{ display: none !important; }}
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    .main .block-container {{
        {bg_style}
        background-color: transparent !important;
    }}
    .main .block-container {{
        padding-top: 8vh !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 1.1, 1])
    with col_c:
        with st.form("login_form"):
            st.markdown(f"""
            <div style="text-align:center; padding-bottom: 8px;">
                <span style="font-size:40px;">🐾</span>
                <h1 style="color:{ORANGE}; font-size:30px; margin:8px 0 4px;">Anicare+</h1>
                <p style="color:#666; font-size:14px; margin-bottom:20px;">
                    Enter your username to log in or create a new account.
                </p>
            </div>
            """, unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="e.g. hayden")
            submitted = st.form_submit_button("Login", use_container_width=True, type="primary")

        if submitted:
            if not username.strip():
                st.warning("Please enter a username.")
            else:
                uname = username.strip()
                udm = UserDataManager()
                loaded = None
                try:
                    loaded = udm.load_user(uname)
                except Exception:
                    loaded = None
                st.session_state["pawpal_user"] = loaded if loaded else User(username=uname, password="")
                st.session_state["logged_in"] = True
                st.session_state["login_username"] = uname
                st.rerun()

    st.stop()

# -----------------------
# Load user after login
# -----------------------

if "pawpal_user" not in st.session_state:
    udm_init = UserDataManager()
    loaded = None
    try:
        loaded = udm_init.load_user(st.session_state["login_username"])
    except Exception:
        loaded = None
    st.session_state["pawpal_user"] = loaded if loaded else User(
        username=st.session_state["login_username"], password=""
    )

user: User = st.session_state["pawpal_user"]

# -----------------------
# Helpers
# -----------------------

def _pet_by_name(pet_name: str) -> Optional[Pet]:
    return next((p for p in user.pets if p.name == pet_name), None)

def _pet_name_by_id(pet_id: str) -> str:
    return next((p.name for p in user.pets if p.pet_id == pet_id), pet_id)

def _priority_label(priority: int) -> str:
    return "🔴 High" if priority >= 4 else "🟡 Medium" if priority >= 3 else "🟢 Low"

def _persist_user_and_schedule(schedule=None) -> None:
    udm = UserDataManager()
    try:
        udm.save_user(user)
    except Exception:
        pass
    if schedule is not None:
        try:
            udm.save_schedule(schedule)
        except Exception:
            pass

# -----------------------
# Sidebar
# -----------------------

st.sidebar.title("🐾 Anicare+")
st.sidebar.caption("Manage pets, tasks, and build a schedule.")

with st.sidebar.expander("👤 User", expanded=True):
    st.sidebar.text_input("Username", value=user.username, disabled=True)
    if st.sidebar.button("Logout", key="sb_logout"):
        for key in ["logged_in", "login_username", "pawpal_user",
                    "archived_tasks", "last_schedule"]:
            st.session_state.pop(key, None)
        st.rerun()
    st.sidebar.caption("Tip: Add pets/tasks below, then generate a schedule.")

with st.sidebar.expander("➕ Add Pet", expanded=False):
    new_pet_name = st.text_input("Pet name", key="sb_pet_name")
    new_species = st.selectbox("Species", ["dog", "cat", "other"], key="sb_pet_species")
    new_age = st.number_input("Age", min_value=0, max_value=50, value=2, key="sb_pet_age")
    new_health = st.text_input("Health info", value="Healthy", key="sb_pet_health")
    if st.button("Add Pet", key="sb_add_pet"):
        if not new_pet_name.strip():
            st.warning("Please enter a pet name.")
        else:
            pet_id = f"{user.username}-{new_pet_name}-{uuid.uuid4().hex[:6]}"
            pet = Pet(
                pet_id=pet_id,
                name=new_pet_name.strip(),
                species=new_species,
                age=int(new_age),
                health_info=new_health.strip(),
            )
            user.pets.append(pet)
            _persist_user_and_schedule()
            st.success(f"Added pet: {pet.name}")

with st.sidebar.expander("📝 Add Task", expanded=False):
    if not user.pets:
        st.info("Add a pet first.")
    else:
        pet_names = [p.name for p in user.pets]
        add_selected_pet = st.selectbox("Select pet", options=pet_names, key="sb_task_pet")
        add_title = st.text_input("Task title", value="Morning walk", key="sb_task_title")
        add_duration = st.number_input(
            "Duration (minutes)", min_value=1, max_value=240, value=20, key="sb_task_duration"
        )
        add_priority_str = st.selectbox("Priority", ["low", "medium", "high"], index=2, key="sb_task_priority")
        add_category = st.selectbox(
            "Category",
            ["general", "walk", "feeding", "grooming", "play", "medication"],
            index=0,
            key="sb_task_category",
        )
        add_is_med = st.checkbox("Is medication", value=(add_category == "medication"), key="sb_task_med")
        add_pref_time = st.selectbox("Preferred time", ["flexible", "morning", "evening"], index=0, key="sb_task_pref")
        add_recurring = st.checkbox("Recurring", value=False, key="sb_task_recurring")
        add_recur_pattern = st.selectbox(
            "Recurrence pattern",
            ["daily", "every_other_day", "weekly"],
            index=0,
            key="sb_task_recur_pattern",
            disabled=not add_recurring,
        )
        priority_map = {"low": 2, "medium": 3, "high": 5}
        if st.button("Add Task", key="sb_add_task"):
            pet_obj = _pet_by_name(add_selected_pet)
            if not pet_obj:
                st.error("Pet not found. Try again.")
            elif not add_title.strip():
                st.warning("Please enter a task title.")
            else:
                task = Task(
                    task_id=uuid.uuid4().hex,
                    pet_id=pet_obj.pet_id,
                    name=add_title.strip(),
                    duration=int(add_duration),
                    priority=priority_map.get(add_priority_str, 3),
                    category=add_category,
                    is_medication=bool(add_is_med),
                    preferred_time=add_pref_time,
                    is_recurring=bool(add_recurring),
                    recurrence_pattern=(add_recur_pattern if add_recurring else "daily"),
                )
                pet_obj.add_task(task)
                _persist_user_and_schedule()
                st.success(f"Added task '{task.name}' to {pet_obj.name}")

with st.sidebar.expander("🗓️ Availability & Scheduling", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        avail_start = st.time_input("Available from", value=time(9, 0), key="sb_avail_from")
    with col2:
        avail_end = st.time_input("Available until", value=time(17, 0), key="sb_avail_to")

    generate = st.button("Generate schedule", type="primary", key="sb_generate")
    if generate:
        if not user.pets:
            st.error("No pets yet. Add a pet first.")
        elif not any(p.tasks for p in user.pets):
            st.error("No tasks yet. Add at least one task.")
        else:
            user.availability = [f"{avail_start.strftime('%H:%M')}-{avail_end.strftime('%H:%M')}"]
            scheduler = TaskScheduler(user)
            schedule = scheduler.schedule_tasks(datetime.now())
            st.session_state["last_schedule"] = schedule
            _persist_user_and_schedule(schedule)
            st.success("Schedule generated!")

    if st.session_state.get("last_schedule"):
        if st.button("Clear schedule", key="sb_clear_schedule"):
            st.session_state["last_schedule"] = None
            st.toast("Cleared.", icon="🧹")

# -----------------------
# Main UI
# -----------------------

st.title("🐾 Anicare+")
st.caption("A task planner + scheduler for pet care.")

tab1, tab2, tab3 = st.tabs(["📋 Tasks", "📅 Schedule", "🤖 AI Assistant"])

# ── Tab 1: Tasks ──────────────────────────────────────────
with tab1:
    st.subheader("Current Task Overview")
    if not user.pets:
        st.info("No pets added yet. Use the sidebar to add your first pet.")
    else:
        for p in user.pets:
            with st.expander(f"{p.name} — {p.species} • {len(p.tasks)} task(s)", expanded=False):
                if not p.tasks:
                    st.info("No tasks yet.")
                else:
                    task_rows = []
                    for t in p.tasks:
                        task_rows.append({
                            "Task": t.name,
                            "Duration (min)": t.duration,
                            "Priority": _priority_label(t.priority),
                            "Category": getattr(t, "category", "general"),
                            "Medication": "✓" if getattr(t, "is_medication", False) else "✗",
                            "Recurring": "✓" if getattr(t, "is_recurring", False) else "✗",
                            "Preferred": getattr(t, "preferred_time", "flexible"),
                        })
                    st.dataframe(task_rows, use_container_width=True, hide_index=True)

# ── Tab 2: Schedule ───────────────────────────────────────
with tab2:
    st.subheader("Generated Schedule")
    schedule = st.session_state.get("last_schedule")
    if not schedule:
        st.info("No schedule generated yet. Use the sidebar → **Generate schedule**.")
    else:
        with st.expander("Filters", expanded=True):
            pet_filter_options = ["All"] + [p.name for p in user.pets]
            pet_filter = st.selectbox("Filter by pet", options=pet_filter_options, index=0, key="flt_pet")
            status_filter = st.selectbox(
                "Filter by status",
                options=["All", "pending", "in_progress", "completed"],
                index=0,
                key="flt_status",
            )
            c1, c2 = st.columns(2)
            with c1:
                time_from = st.time_input("From", value=time(0, 0), key="flt_from")
            with c2:
                time_to = st.time_input("To", value=time(23, 59), key="flt_to")

        if schedule.scheduled_tasks:
            st.markdown("### Tasks (sorted by time)")
            rows = []
            for st_task in schedule.get_tasks_by_time():
                task_obj = getattr(st_task, "task", None)
                task_name = task_obj.name if task_obj else st_task.task_id
                pet_name = _pet_name_by_id(st_task.pet_id)
                priority = getattr(task_obj, "priority", 0)
                status = getattr(st_task, "status", "pending")

                try:
                    time_str = f"{st_task.start_time.strftime('%H:%M')} - {st_task.end_time.strftime('%H:%M')}"
                except Exception:
                    time_str = ""

                if pet_filter != "All" and pet_name != pet_filter:
                    continue
                if status_filter != "All" and status != status_filter:
                    continue
                try:
                    if st_task.start_time and (
                        st_task.start_time < time_from or st_task.start_time > time_to
                    ):
                        continue
                except Exception:
                    pass

                checked = st.checkbox(
                    f"{time_str} — {task_name} ({pet_name})",
                    value=(status == "completed"),
                    key=f"chk-{st_task.task_id}",
                )

                if checked and status != "completed":
                    try:
                        pet_obj = next((p for p in user.pets if p.pet_id == st_task.pet_id), None)
                        task_obj = getattr(st_task, "task", None)
                        if task_obj and not getattr(task_obj, "is_recurring", False) and pet_obj:
                            pet_obj.tasks = [t for t in pet_obj.tasks if t.task_id != task_obj.task_id]
                            st.session_state["archived_tasks"].append({
                                "task_id": task_obj.task_id,
                                "task_name": task_obj.name,
                                "pet_id": pet_obj.pet_id,
                                "pet_name": pet_obj.name,
                                "duration": task_obj.duration,
                                "priority": task_obj.priority,
                                "category": getattr(task_obj, "category", "general"),
                                "is_medication": getattr(task_obj, "is_medication", False),
                                "preferred_time": getattr(task_obj, "preferred_time", "flexible"),
                                "completed_at": datetime.now().isoformat(),
                            })
                            st_task.status = "completed"
                        else:
                            try:
                                st_task.mark_complete(datetime.now())
                            except Exception:
                                st_task.status = "completed"
                        st.session_state["last_schedule"] = schedule
                        _persist_user_and_schedule(schedule)
                        st.success(f"Marked '{task_name}' completed.")
                    except Exception as e:
                        st.error(f"An error occurred: {e}")
                elif (not checked) and status == "completed":
                    st_task.status = "pending"
                    st.session_state["last_schedule"] = schedule
                    _persist_user_and_schedule(schedule)

                rows.append({
                    "Time": time_str,
                    "Task": task_name,
                    "Pet": pet_name,
                    "Priority": _priority_label(priority),
                    "Duration": f"{getattr(task_obj, 'duration', '')} min",
                    "Status": getattr(st_task, "status", "pending"),
                })

            st.table(rows)

            if schedule.has_conflicts():
                st.warning("⚠️ Schedule Conflicts Detected")
                st.text(schedule.get_conflict_summary())
            else:
                st.success("✓ No time conflicts detected.")
        else:
            st.warning("⚠️ No tasks could be scheduled in the available time.")

        try:
            scheduled_ids = {t.task_id for t in schedule.scheduled_tasks}
            all_tasks = [t for p in user.pets for t in p.tasks]
            unscheduled = [t for t in all_tasks if t.task_id not in scheduled_ids]
        except Exception:
            unscheduled = []

        if unscheduled:
            st.info(f"ℹ️ {len(unscheduled)} task(s) could not fit in your available time")
            st.dataframe(
                [{"Task": t.name, "Pet": _pet_name_by_id(t.pet_id),
                  "Duration (min)": t.duration, "Priority": _priority_label(t.priority)}
                 for t in unscheduled],
                use_container_width=True, hide_index=True,
            )

        with st.expander("📝 Detailed Explanation", expanded=False):
            try:
                st.text(schedule.get_explanation())
            except Exception:
                st.text(getattr(schedule, "explanation", ""))

        with st.expander("📦 Archived Tasks", expanded=False):
            archived = st.session_state.get("archived_tasks", [])
            if not archived:
                st.info("No archived tasks.")
            else:
                for a in list(archived):
                    cols = st.columns([4, 1, 1])
                    cols[0].write(
                        f"{a.get('task_name')} — {a.get('pet_name')} "
                        f"(completed {a.get('completed_at')[:19]})"
                    )
                    if cols[1].button("Restore", key=f"restore-{a.get('task_id')}"):
                        pet_obj = next(
                            (p for p in user.pets if p.pet_id == a.get("pet_id")), None
                        )
                        if pet_obj:
                            restored = Task(
                                task_id=a.get("task_id"),
                                pet_id=pet_obj.pet_id,
                                name=a.get("task_name"),
                                duration=a.get("duration", 0),
                                priority=a.get("priority", 3),
                                category=a.get("category", "general"),
                                is_medication=a.get("is_medication", False),
                                preferred_time=a.get("preferred_time", "flexible"),
                                is_recurring=False,
                            )
                            pet_obj.tasks.append(restored)
                            st.session_state["archived_tasks"] = [
                                x for x in st.session_state["archived_tasks"]
                                if x.get("task_id") != a.get("task_id")
                            ]
                            _persist_user_and_schedule()
                            st.success(f"Restored '{a.get('task_name')}' to {pet_obj.name}")
                    if cols[2].button("Delete", key=f"delete-arch-{a.get('task_id')}"):
                        st.session_state["archived_tasks"] = [
                            x for x in st.session_state["archived_tasks"]
                            if x.get("task_id") != a.get("task_id")
                        ]
                        st.success("Deleted archived task")

# ── Tab 3: AI Assistant ───────────────────────────────────
with tab3:
    render_ai_tab(user)