"""
ai_features.py  —  Anicare+ AI Features
=======================================
Provides two AI capabilities that slot cleanly into the existing Anicare+ system:

  1. AnicareRAG   — Retrieval-Augmented Generation
                   Retrieves nearby vets / parks / pet stores via Google Places,
                   then uses Claude to generate a grounded, context-aware answer.

  2. AnicareAgent — Agentic Workflow
                   Claude operates as an autonomous agent with tools to search
                   nearby places, read/write the pet schedule, and check
                   appointment availability.  A MAX_ITERATIONS guardrail prevents
                   runaway loops.

Dependencies (add to requirements.txt):
  anthropic>=0.25.0
  requests>=2.31.0

Environment variables required:
  ANTHROPIC_API_KEY   — your Anthropic key
  GOOGLE_PLACES_KEY   — your Google Places API key
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

import anthropic
import requests

from anicare_system import Pet, Task, User

# ---------------------------------------------------------------------------
# Logging setup — writes to anicare_ai.log AND console
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("anicare_ai.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("anicare_ai")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL = "claude-sonnet-4-6"

PLACE_TYPE_MAP = {
    "vet": "veterinary_care",
    "park": "park",
    "pet_store": "pet_store",
}

CATEGORY_LABEL = {
    "vet": "veterinary clinic",
    "park": "park",
    "pet_store": "pet supply store",
}

# ---------------------------------------------------------------------------
# Tool definitions for the agentic workflow
# ---------------------------------------------------------------------------
AGENT_TOOLS = [
    {
        "name": "search_nearby_places",
        "description": (
            "Search for vets, parks, or pet supply stores near the user's location. "
            "Returns up to 5 results with name, address, rating, and open status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["vet", "park", "pet_store"],
                    "description": "Type of place to search for.",
                },
                "lat": {"type": "number", "description": "User latitude."},
                "lng": {"type": "number", "description": "User longitude."},
                "radius_meters": {
                    "type": "integer",
                    "description": "Search radius in metres (default 5000).",
                    "default": 5000,
                },
            },
            "required": ["category", "lat", "lng"],
        },
    },
    {
        "name": "get_pet_schedule",
        "description": (
            "Get the current tasks/schedule for all pets or a specific pet. "
            "Returns task name, category, duration, priority, and recurrence info."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pet_name": {
                    "type": "string",
                    "description": "Name of the pet.  Omit to get all pets.",
                }
            },
        },
    },
    {
        "name": "add_location_to_schedule",
        "description": (
            "Add a vet visit, park outing, or pet store trip to a pet's task list. "
            "The task will appear in the next generated schedule."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pet_name": {"type": "string", "description": "Name of the pet."},
                "task_name": {
                    "type": "string",
                    "description": "Descriptive name for the new task (e.g. 'Vet visit – City Animal Clinic').",
                },
                "category": {
                    "type": "string",
                    "enum": ["walk", "general", "medication"],
                    "description": "Task category.",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Estimated duration in minutes.",
                },
                "preferred_time": {
                    "type": "string",
                    "enum": ["morning", "evening", "flexible"],
                    "default": "flexible",
                },
                "is_recurring": {
                    "type": "boolean",
                    "description": "Whether the task repeats.",
                    "default": False,
                },
                "recurrence_pattern": {
                    "type": "string",
                    "enum": ["daily", "weekly", "every_other_day"],
                    "default": "daily",
                },
            },
            "required": ["pet_name", "task_name", "category", "duration_minutes"],
        },
    },
    {
        "name": "get_next_appointment",
        "description": (
            "Get the next scheduled vet appointment or medication task for a pet, "
            "including the next due date if set."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pet_name": {
                    "type": "string",
                    "description": "Name of the pet.",
                }
            },
            "required": ["pet_name"],
        },
    },
    {
        "name": "check_place_hours",
        "description": (
            "Check whether a specific vet/park/store is currently open and retrieve "
            "its weekly opening hours and phone number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "place_id": {
                    "type": "string",
                    "description": "Google Place ID returned by search_nearby_places.",
                },
                "place_name": {
                    "type": "string",
                    "description": "Human-readable name (used as fallback in response).",
                },
            },
            "required": ["place_id"],
        },
    },
]


# ===========================================================================
# 1.  RAG PIPELINE
# ===========================================================================

class AnicareRAG:
    """
    Retrieval-Augmented Generation pipeline.

    Flow:
      retrieve_nearby_places()  →  build_context()  →  Claude generates answer

    The generated answer is grounded exclusively in the retrieved location data,
    satisfying the RAG requirement that retrieved data actively shapes the response.
    """

    def __init__(self, client: anthropic.Anthropic, google_places_key: str) -> None:
        self.client = client
        self.places_key = google_places_key
        self._log = logging.getLogger("anicare_ai.rag")

    # ------------------------------------------------------------------
    # Step 1: Retrieve
    # ------------------------------------------------------------------

    def retrieve_nearby_places(
        self,
        category: str,
        lat: float,
        lng: float,
        radius_meters: int = 5000,
    ) -> list[dict]:
        """Call Google Places Nearby Search and return up to 5 normalised results."""
        place_type = PLACE_TYPE_MAP.get(category, "veterinary_care")
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        # Add keyword alongside type for better coverage
        keyword_map = {"vet": "veterinarian", "park": "dog park", "pet_store": "pet store"}
        params = {
            "location": f"{lat},{lng}",
            "radius": radius_meters,
            "type": place_type,
            "keyword": keyword_map.get(category, ""),
            "key": self.places_key,
        }

        self._log.info("Retrieving %s near (%.4f, %.4f) radius=%dm", category, lat, lng, radius_meters)

        try:
            resp = requests.get(url, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            self._log.error("Places API network error: %s", exc)
            return [{"_api_error": f"Network error: {exc}"}]

        status = data.get("status", "UNKNOWN")
        self._log.info("Places API status: %s", status)

        if status == "REQUEST_DENIED":
            msg = data.get("error_message", "API key rejected.")
            self._log.error("Places API REQUEST_DENIED: %s", msg)
            return [{"_api_error": f"REQUEST_DENIED — {msg}"}]
        if status == "OVER_QUERY_LIMIT":
            return [{"_api_error": "OVER_QUERY_LIMIT — quota exceeded for today."}]
        if status == "INVALID_REQUEST":
            return [{"_api_error": "INVALID_REQUEST — bad parameters sent to Places API."}]
        if status not in ("OK", "ZERO_RESULTS"):
            return [{"_api_error": f"Unexpected status: {status}"}]

        raw = data.get("results", [])
        self._log.info("Places returned %d results (status=%s)", len(raw), status)

        places = []
        for r in raw[:5]:
            oh = r.get("opening_hours", {})
            open_now = oh.get("open_now")
            places.append(
                {
                    "name": r.get("name", "Unknown"),
                    "address": r.get("vicinity", "Address unavailable"),
                    "rating": r.get("rating", "N/A"),
                    "open_now": open_now,
                    "place_id": r.get("place_id", ""),
                    "lat": r["geometry"]["location"]["lat"],
                    "lng": r["geometry"]["location"]["lng"],
                }
            )

        return places

    # ------------------------------------------------------------------
    # Step 2: Augment
    # ------------------------------------------------------------------

    def build_context(self, places: list[dict], category: str) -> str:
        """Format retrieved places into a plain-text context block for Claude."""
        label = CATEGORY_LABEL.get(category, category)
        if not places:
            return f"No nearby {label}s were found within the search radius."

        lines = [f"Nearby {label}s (retrieved from Google Places):"]
        for i, p in enumerate(places, 1):
            if p["open_now"] is True:
                status = "Open now"
            elif p["open_now"] is False:
                status = "Currently closed"
            else:
                status = "Hours unknown"
            lines.append(
                f"  {i}. {p['name']}"
                f"\n     Address : {p['address']}"
                f"\n     Rating  : {p['rating']}/5"
                f"\n     Status  : {status}"
                f"\n     Place ID: {p['place_id']}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Step 3: Generate
    # ------------------------------------------------------------------

    def query(
        self,
        user_question: str,
        category: str,
        lat: float,
        lng: float,
        pet_name: Optional[str] = None,
    ) -> dict:
        """
        Run the full RAG pipeline and return a dict:
          {
            "answer": str,       # Claude's response
            "places": list[dict],# raw retrieved data
            "context": str,      # formatted context passed to Claude
          }
        """
        # --- Retrieve ---
        places = self.retrieve_nearby_places(category, lat, lng)

        # --- Augment ---
        context = self.build_context(places, category)
        pet_ctx = f" for {pet_name}" if pet_name else ""

        system_prompt = (
            "You are Anicare+'s AI assistant helping pet owners find local care services. "
            "Answer using ONLY the location data provided in the context below. "
            "Never invent place names, addresses, or ratings. "
            "If none of the listed locations suit the owner's needs, say so clearly. "
            "Be concise, friendly, and specific."
        )

        user_message = (
            f"Retrieved location data{pet_ctx}:\n\n{context}\n\n"
            f"Owner's question: {user_question}"
        )

        self._log.info("Generating RAG response for: %r", user_question)

        # --- Generate ---
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        answer = response.content[0].text
        self._log.info("RAG response generated successfully")

        return {"answer": answer, "places": places, "context": context}


# ===========================================================================
# 2.  AGENTIC WORKFLOW
# ===========================================================================

class AnicareAgent:
    """
    Autonomous agent that plans and acts across multiple tool calls.

    Claude is given five tools and runs in a loop until it produces a
    final text answer or the MAX_ITERATIONS guardrail fires.

    Plan → Act → Verify loop:
      • Plan  : Claude inspects the request and decides which tool(s) to call.
      • Act   : Tools execute (Places API, schedule read/write, etc.).
      • Verify: Claude reviews results and either calls more tools or answers.
    """

    MAX_ITERATIONS = 5

    def __init__(
        self,
        client: anthropic.Anthropic,
        google_places_key: str,
        user: User,
    ) -> None:
        self.client = client
        self.places_key = google_places_key
        self.user = user
        self._rag = AnicareRAG(client, google_places_key)
        self._log = logging.getLogger("anicare_ai.agent")

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _tool_search_nearby_places(
        self,
        category: str,
        lat: float,
        lng: float,
        radius_meters: int = 5000,
    ) -> str:
        places = self._rag.retrieve_nearby_places(category, lat, lng, radius_meters)
        if not places:
            return json.dumps({"error": "No places found in the search area."})
        return json.dumps(places)

    def _tool_get_pet_schedule(self, pet_name: Optional[str] = None) -> str:
        tasks = []
        for pet in self.user.pets:
            if pet_name and pet.name.lower() != pet_name.lower():
                continue
            for task in pet.tasks:
                tasks.append(
                    {
                        "pet": pet.name,
                        "task": task.name,
                        "category": task.category,
                        "duration_min": task.duration,
                        "priority": task.priority,
                        "is_medication": task.is_medication,
                        "is_recurring": task.is_recurring,
                        "recurrence_pattern": task.recurrence_pattern if task.is_recurring else None,
                        "next_due": (
                            task.next_due_date.isoformat() if task.next_due_date else None
                        ),
                    }
                )
        if not tasks:
            msg = f"No tasks found for {pet_name}." if pet_name else "No tasks found."
            return json.dumps({"message": msg})
        return json.dumps(tasks)

    def _tool_add_location_to_schedule(
        self,
        pet_name: str,
        task_name: str,
        category: str,
        duration_minutes: int,
        preferred_time: str = "flexible",
        is_recurring: bool = False,
        recurrence_pattern: str = "daily",
    ) -> str:
        pet = next(
            (p for p in self.user.pets if p.name.lower() == pet_name.lower()), None
        )
        if not pet:
            return json.dumps({"error": f"Pet '{pet_name}' not found."})

        task = Task(
            task_id=uuid.uuid4().hex,
            pet_id=pet.pet_id,
            name=task_name,
            duration=duration_minutes,
            priority=5 if category == "medication" else 3,
            category=category,
            is_medication=(category == "medication"),
            preferred_time=preferred_time,
            is_recurring=is_recurring,
            recurrence_pattern=recurrence_pattern if is_recurring else "daily",
        )
        pet.add_task(task)
        self._log.info("Added task '%s' to %s's schedule", task_name, pet_name)
        return json.dumps(
            {
                "success": True,
                "message": f"Added '{task_name}' ({duration_minutes} min, {preferred_time}) to {pet_name}'s schedule.",
                "task_id": task.task_id,
            }
        )

    def _tool_get_next_appointment(self, pet_name: str) -> str:
        pet = next(
            (p for p in self.user.pets if p.name.lower() == pet_name.lower()), None
        )
        if not pet:
            return json.dumps({"error": f"Pet '{pet_name}' not found."})

        upcoming = []
        for task in pet.tasks:
            is_vet_related = (
                task.category == "medication"
                or "vet" in task.name.lower()
                or "appointment" in task.name.lower()
            )
            if is_vet_related:
                upcoming.append(
                    {
                        "task": task.name,
                        "category": task.category,
                        "is_recurring": task.is_recurring,
                        "next_due": (
                            task.next_due_date.isoformat()
                            if task.next_due_date
                            else "No specific date set"
                        ),
                    }
                )

        if not upcoming:
            return json.dumps(
                {"message": f"No upcoming vet or medication appointments found for {pet_name}."}
            )
        return json.dumps(upcoming)

    def _tool_check_place_hours(
        self, place_id: str, place_name: str = ""
    ) -> str:
        """Fetch detailed hours from the Google Places Details API."""
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "name,opening_hours,formatted_phone_number",
            "key": self.places_key,
        }
        try:
            resp = requests.get(url, params=params, timeout=8)
            resp.raise_for_status()
            result = resp.json().get("result", {})
            hours = result.get("opening_hours", {})
            return json.dumps(
                {
                    "name": result.get("name", place_name),
                    "open_now": hours.get("open_now", "Unknown"),
                    "weekday_hours": hours.get("weekday_text", []),
                    "phone": result.get("formatted_phone_number", "N/A"),
                }
            )
        except requests.RequestException as exc:
            self._log.error("Place details API error: %s", exc)
            return json.dumps({"error": str(exc)})

    # ------------------------------------------------------------------
    # Tool dispatcher
    # ------------------------------------------------------------------

    def _dispatch_tool(self, tool_name: str, tool_input: dict) -> str:
        self._log.info("Tool call: %s  input=%s", tool_name, json.dumps(tool_input))
        try:
            if tool_name == "search_nearby_places":
                return self._tool_search_nearby_places(**tool_input)
            elif tool_name == "get_pet_schedule":
                return self._tool_get_pet_schedule(**tool_input)
            elif tool_name == "add_location_to_schedule":
                return self._tool_add_location_to_schedule(**tool_input)
            elif tool_name == "get_next_appointment":
                return self._tool_get_next_appointment(**tool_input)
            elif tool_name == "check_place_hours":
                return self._tool_check_place_hours(**tool_input)
            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
        except Exception as exc:  # pragma: no cover
            self._log.error("Tool '%s' raised: %s", tool_name, exc)
            return json.dumps({"error": str(exc)})

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(
        self,
        user_message: str,
        lat: float,
        lng: float,
        conversation_history: list = None,
    ) -> dict:
        """
        Execute the agentic loop. Pass conversation_history to continue
        an existing chat — Claude will have full context of previous exchanges.

        Returns dict with keys: answer, tool_log, iterations, messages.
        Pass result["messages"] back as conversation_history next turn.
        """
        system_prompt = (
            f"You are Anicare+'s AI scheduling assistant. "
            f"The user's approximate location is latitude={lat}, longitude={lng}. "
            "You have tools to find nearby pet services, read and update the pet schedule, "
            "and check business hours. "
            "Always use real data from your tools — never invent place names or details. "
            "When you add a task to the schedule, confirm the action clearly. "
            "You remember the full conversation — use it to give contextual replies. "
            "Be concise and action-oriented."
        )

        # Start from existing history then append new user turn
        messages: list[dict] = list(conversation_history) if conversation_history else []
        messages.append({"role": "user", "content": user_message})
        tool_log: list[dict] = []
        iterations = 0

        self._log.info("Agent run started: %r (history=%d msgs)", user_message, len(messages))

        while iterations < self.MAX_ITERATIONS:
            iterations += 1
            self._log.info("Iteration %d/%d", iterations, self.MAX_ITERATIONS)

            response = self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=system_prompt,
                tools=AGENT_TOOLS,
                messages=messages,
            )

            # ---- Claude is done (no more tool calls) ----
            if response.stop_reason == "end_turn":
                final_text = next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                )
                self._log.info("Agent finished in %d iteration(s)", iterations)
                # Append final assistant reply to history
                messages.append({"role": "assistant", "content": final_text})
                self._log.info("Agent finished in %d iteration(s)", iterations)
                return {
                    "answer": final_text,
                    "tool_log": tool_log,
                    "iterations": iterations,
                    "messages": messages,
                }

            # ---- Claude wants to call tools ----
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                # stop_reason wasn't "end_turn" but there are no tool calls either
                final_text = next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                )
                messages.append({"role": "assistant", "content": final_text})
                return {
                    "answer": final_text,
                    "tool_log": tool_log,
                    "iterations": iterations,
                    "messages": messages,
                }

            # Append assistant turn (with tool_use blocks)
            messages.append({"role": "assistant", "content": response.content})

            # Execute tools and collect results
            tool_results = []
            for tc in tool_uses:
                result_str = self._dispatch_tool(tc.name, tc.input)
                tool_log.append(
                    {"tool": tc.name, "input": tc.input, "result": result_str}
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": result_str,
                    }
                )

            # Feed results back into the conversation
            messages.append({"role": "user", "content": tool_results})

        # Guardrail: too many iterations
        self._log.warning("MAX_ITERATIONS (%d) reached", self.MAX_ITERATIONS)
        return {
            "answer": (
                "I wasn't able to complete the request within my step limit. "
                "Please try a more specific question."
            ),
            "tool_log": tool_log,
            "iterations": iterations,
            "messages": messages,
        }