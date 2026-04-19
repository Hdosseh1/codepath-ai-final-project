"""
test_ai_features.py  —  PawPal AI Feature Tests
=================================================
Tests for PawPalRAG and PawPalAgent in ai_features.py.

All external calls (Anthropic API + Google Places API) are mocked,
so these tests run without any API keys and without burning credits.

Run with:
    python -m pytest test_ai_features.py -v
"""

import json
import pytest
from datetime import datetime, time
from unittest.mock import MagicMock, patch, PropertyMock

from pawpal_system import Pet, Task, ScheduledTask, User
from ai_features import PawPalRAG, PawPalAgent, PLACE_TYPE_MAP, CATEGORY_LABEL


# ===========================================================================
# Shared fixtures
# ===========================================================================

@pytest.fixture
def mock_anthropic_client():
    """A mock Anthropic client that returns a canned text response."""
    client = MagicMock()
    response = MagicMock()
    response.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.text = "Here is my recommendation based on the retrieved data."
    text_block.type = "text"
    response.content = [text_block]
    client.messages.create.return_value = response
    return client


@pytest.fixture
def sample_places():
    """Realistic Google Places API results (already normalised)."""
    return [
        {
            "name": "City Animal Hospital",
            "address": "123 Main St",
            "rating": 4.7,
            "open_now": True,
            "place_id": "PLACE_001",
            "lat": 38.99,
            "lng": -77.03,
        },
        {
            "name": "Paws & Claws Vet",
            "address": "456 Oak Ave",
            "rating": 4.2,
            "open_now": False,
            "place_id": "PLACE_002",
            "lat": 38.98,
            "lng": -77.02,
        },
    ]


@pytest.fixture
def basic_user():
    """A User with one pet and one task, matching the PawPal data model."""
    pet = Pet(
        pet_id="pet-001",
        name="Max",
        species="dog",
        age=3,
        health_info="Healthy",
    )
    task = Task(
        task_id="task-001",
        pet_id="pet-001",
        name="Morning walk",
        duration=30,
        priority=3,
        category="walk",
        is_medication=False,
        preferred_time="morning",
        is_recurring=True,
        recurrence_pattern="daily",
    )
    pet.add_task(task)

    user = User(username="Jordan", password="")
    user.pets.append(pet)
    return user


# ===========================================================================
# PawPalRAG  —  Unit tests
# ===========================================================================

class TestPawPalRAGRetrieve:
    """Tests for the retrieve_nearby_places step."""

    def test_returns_normalised_place_list(self, mock_anthropic_client):
        """retrieve_nearby_places should return a list of dicts with expected keys."""
        raw_api_response = {
            "results": [
                {
                    "name": "City Animal Hospital",
                    "vicinity": "123 Main St",
                    "rating": 4.7,
                    "place_id": "PLACE_001",
                    "opening_hours": {"open_now": True},
                    "geometry": {"location": {"lat": 38.99, "lng": -77.03}},
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = raw_api_response
        mock_resp.raise_for_status = MagicMock()

        with patch("ai_features.requests.get", return_value=mock_resp):
            rag = PawPalRAG(mock_anthropic_client, "fake-google-key")
            places = rag.retrieve_nearby_places("vet", 38.99, -77.03)

        assert len(places) == 1
        place = places[0]
        assert place["name"] == "City Animal Hospital"
        assert place["address"] == "123 Main St"
        assert place["rating"] == 4.7
        assert place["open_now"] is True
        assert place["place_id"] == "PLACE_001"

    def test_returns_empty_list_on_api_failure(self, mock_anthropic_client):
        """retrieve_nearby_places should return [] and not raise if the API errors."""
        import requests as req
        with patch("ai_features.requests.get", side_effect=req.RequestException("timeout")):
            rag = PawPalRAG(mock_anthropic_client, "fake-google-key")
            places = rag.retrieve_nearby_places("vet", 38.99, -77.03)

        assert places == []

    def test_caps_results_at_five(self, mock_anthropic_client):
        """retrieve_nearby_places should return at most 5 results."""
        single_result = {
            "name": "Vet",
            "vicinity": "1 St",
            "rating": 4.0,
            "place_id": "P",
            "opening_hours": {"open_now": True},
            "geometry": {"location": {"lat": 38.0, "lng": -77.0}},
        }
        raw_api_response = {"results": [single_result] * 10}  # 10 results from API
        mock_resp = MagicMock()
        mock_resp.json.return_value = raw_api_response
        mock_resp.raise_for_status = MagicMock()

        with patch("ai_features.requests.get", return_value=mock_resp):
            rag = PawPalRAG(mock_anthropic_client, "fake-google-key")
            places = rag.retrieve_nearby_places("vet", 38.99, -77.03)

        assert len(places) == 5

    def test_uses_correct_place_type_for_category(self, mock_anthropic_client):
        """The correct Google place type string should be passed for each category."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": []}
        mock_resp.raise_for_status = MagicMock()

        for category, expected_type in PLACE_TYPE_MAP.items():
            with patch("ai_features.requests.get", return_value=mock_resp) as mock_get:
                rag = PawPalRAG(mock_anthropic_client, "fake-google-key")
                rag.retrieve_nearby_places(category, 38.99, -77.03)
                call_params = mock_get.call_args[1]["params"]
                assert call_params["type"] == expected_type, (
                    f"Category '{category}' should map to place type '{expected_type}'"
                )


class TestPawPalRAGContext:
    """Tests for the build_context step."""

    def test_context_contains_place_names(self, mock_anthropic_client, sample_places):
        rag = PawPalRAG(mock_anthropic_client, "fake-google-key")
        context = rag.build_context(sample_places, "vet")
        assert "City Animal Hospital" in context
        assert "Paws & Claws Vet" in context

    def test_context_shows_open_status(self, mock_anthropic_client, sample_places):
        rag = PawPalRAG(mock_anthropic_client, "fake-google-key")
        context = rag.build_context(sample_places, "vet")
        assert "Open now" in context
        assert "Currently closed" in context

    def test_context_handles_empty_places(self, mock_anthropic_client):
        rag = PawPalRAG(mock_anthropic_client, "fake-google-key")
        context = rag.build_context([], "vet")
        assert "No nearby" in context

    def test_context_includes_ratings(self, mock_anthropic_client, sample_places):
        rag = PawPalRAG(mock_anthropic_client, "fake-google-key")
        context = rag.build_context(sample_places, "vet")
        assert "4.7" in context
        assert "4.2" in context

    def test_context_unknown_hours(self, mock_anthropic_client):
        """A place with open_now=None should show 'Hours unknown'."""
        places = [
            {
                "name": "Mystery Vet",
                "address": "9 Unknown St",
                "rating": 3.9,
                "open_now": None,
                "place_id": "P_UNK",
                "lat": 38.0,
                "lng": -77.0,
            }
        ]
        rag = PawPalRAG(mock_anthropic_client, "fake-google-key")
        context = rag.build_context(places, "vet")
        assert "Hours unknown" in context


class TestPawPalRAGQuery:
    """End-to-end tests for the full RAG query pipeline."""

    def test_query_returns_answer_places_and_context(
        self, mock_anthropic_client, sample_places
    ):
        """query() should return a dict with all three keys populated."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {
                    "name": p["name"],
                    "vicinity": p["address"],
                    "rating": p["rating"],
                    "place_id": p["place_id"],
                    "opening_hours": {"open_now": p["open_now"]},
                    "geometry": {"location": {"lat": p["lat"], "lng": p["lng"]}},
                }
                for p in sample_places
            ]
        }
        with patch("ai_features.requests.get", return_value=mock_resp):
            rag = PawPalRAG(mock_anthropic_client, "fake-google-key")
            result = rag.query(
                user_question="Which vet is best?",
                category="vet",
                lat=38.99,
                lng=-77.03,
            )

        assert "answer" in result
        assert "places" in result
        assert "context" in result
        assert len(result["places"]) == 2
        assert isinstance(result["answer"], str)
        assert len(result["answer"]) > 0

    def test_query_passes_context_to_claude(self, mock_anthropic_client, sample_places):
        """Claude should receive the retrieved location context in its prompt."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {
                    "name": p["name"],
                    "vicinity": p["address"],
                    "rating": p["rating"],
                    "place_id": p["place_id"],
                    "opening_hours": {"open_now": p["open_now"]},
                    "geometry": {"location": {"lat": p["lat"], "lng": p["lng"]}},
                }
                for p in sample_places
            ]
        }
        with patch("ai_features.requests.get", return_value=mock_resp):
            rag = PawPalRAG(mock_anthropic_client, "fake-google-key")
            rag.query("Which vet?", "vet", 38.99, -77.03)

        call_kwargs = mock_anthropic_client.messages.create.call_args[1]
        user_content = call_kwargs["messages"][0]["content"]
        assert "City Animal Hospital" in user_content

    def test_query_with_pet_name_in_context(self, mock_anthropic_client):
        """pet_name should appear in the prompt when provided."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"results": []}

        with patch("ai_features.requests.get", return_value=mock_resp):
            rag = PawPalRAG(mock_anthropic_client, "fake-google-key")
            rag.query("Find a park", "park", 38.99, -77.03, pet_name="Max")

        call_kwargs = mock_anthropic_client.messages.create.call_args[1]
        user_content = call_kwargs["messages"][0]["content"]
        assert "Max" in user_content


# ===========================================================================
# PawPalAgent  —  Tool unit tests
# ===========================================================================

class TestAgentToolGetPetSchedule:
    """Tests for the get_pet_schedule tool implementation."""

    def test_returns_tasks_for_specific_pet(self, mock_anthropic_client, basic_user):
        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        result = json.loads(agent._tool_get_pet_schedule(pet_name="Max"))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["task"] == "Morning walk"
        assert result[0]["pet"] == "Max"

    def test_returns_all_tasks_when_no_pet_specified(
        self, mock_anthropic_client, basic_user
    ):
        # Add a second pet
        pet2 = Pet(pet_id="pet-002", name="Luna", species="cat", age=2, health_info="")
        task2 = Task(
            task_id="task-002",
            pet_id="pet-002",
            name="Feeding",
            duration=10,
            priority=4,
            category="feeding",
        )
        pet2.add_task(task2)
        basic_user.pets.append(pet2)

        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        result = json.loads(agent._tool_get_pet_schedule())
        assert len(result) == 2

    def test_returns_message_when_pet_not_found(
        self, mock_anthropic_client, basic_user
    ):
        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        result = json.loads(agent._tool_get_pet_schedule(pet_name="NonExistent"))
        assert "message" in result or "No tasks" in str(result)

    def test_case_insensitive_pet_name(self, mock_anthropic_client, basic_user):
        """Pet name lookup should be case-insensitive."""
        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        result = json.loads(agent._tool_get_pet_schedule(pet_name="max"))
        assert isinstance(result, list)
        assert len(result) == 1


class TestAgentToolAddLocationToSchedule:
    """Tests for the add_location_to_schedule tool implementation."""

    def test_adds_task_to_pet(self, mock_anthropic_client, basic_user):
        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        initial_count = len(basic_user.pets[0].tasks)

        result = json.loads(
            agent._tool_add_location_to_schedule(
                pet_name="Max",
                task_name="Vet visit – City Animal Hospital",
                category="general",
                duration_minutes=60,
                preferred_time="morning",
            )
        )

        assert result["success"] is True
        assert len(basic_user.pets[0].tasks) == initial_count + 1

    def test_new_task_has_correct_name(self, mock_anthropic_client, basic_user):
        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        agent._tool_add_location_to_schedule(
            pet_name="Max",
            task_name="Park visit – Sligo Creek",
            category="walk",
            duration_minutes=45,
        )
        task_names = [t.name for t in basic_user.pets[0].tasks]
        assert "Park visit – Sligo Creek" in task_names

    def test_medication_task_gets_high_priority(self, mock_anthropic_client, basic_user):
        """Medication tasks should automatically get priority 5."""
        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        agent._tool_add_location_to_schedule(
            pet_name="Max",
            task_name="Give flea meds",
            category="medication",
            duration_minutes=5,
        )
        med_task = next(
            t for t in basic_user.pets[0].tasks if t.name == "Give flea meds"
        )
        assert med_task.priority == 5
        assert med_task.is_medication is True

    def test_returns_error_for_unknown_pet(self, mock_anthropic_client, basic_user):
        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        result = json.loads(
            agent._tool_add_location_to_schedule(
                pet_name="Ghost",
                task_name="Vet visit",
                category="general",
                duration_minutes=30,
            )
        )
        assert "error" in result

    def test_recurring_task_flag_is_preserved(self, mock_anthropic_client, basic_user):
        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        agent._tool_add_location_to_schedule(
            pet_name="Max",
            task_name="Weekly park run",
            category="walk",
            duration_minutes=60,
            is_recurring=True,
            recurrence_pattern="weekly",
        )
        task = next(
            t for t in basic_user.pets[0].tasks if t.name == "Weekly park run"
        )
        assert task.is_recurring is True
        assert task.recurrence_pattern == "weekly"


class TestAgentToolGetNextAppointment:
    """Tests for the get_next_appointment tool implementation."""

    def test_finds_medication_task(self, mock_anthropic_client, basic_user):
        """A medication task should appear in upcoming appointments."""
        med_task = Task(
            task_id="task-med",
            pet_id="pet-001",
            name="Heartworm pill",
            duration=5,
            priority=5,
            category="medication",
            is_medication=True,
            next_due_date=datetime(2026, 5, 1),
        )
        basic_user.pets[0].add_task(med_task)

        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        result = json.loads(agent._tool_get_next_appointment(pet_name="Max"))

        assert isinstance(result, list)
        assert any("Heartworm pill" in item["task"] for item in result)

    def test_finds_task_with_vet_in_name(self, mock_anthropic_client, basic_user):
        """A task whose name contains 'vet' should appear in upcoming appointments."""
        vet_task = Task(
            task_id="task-vet",
            pet_id="pet-001",
            name="Vet checkup",
            duration=60,
            priority=4,
            category="general",
        )
        basic_user.pets[0].add_task(vet_task)

        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        result = json.loads(agent._tool_get_next_appointment(pet_name="Max"))

        assert any("Vet checkup" in item["task"] for item in result)

    def test_returns_message_when_no_appointments(
        self, mock_anthropic_client, basic_user
    ):
        """Should return a message dict (not error) when no vet/med tasks exist."""
        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        result = json.loads(agent._tool_get_next_appointment(pet_name="Max"))
        # basic_user only has a "walk" task, so no appointments
        assert "message" in result

    def test_returns_error_for_unknown_pet(self, mock_anthropic_client, basic_user):
        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        result = json.loads(agent._tool_get_next_appointment(pet_name="Ghost"))
        assert "error" in result


# ===========================================================================
# PawPalAgent  —  Agentic loop tests
# ===========================================================================

class TestAgentLoop:
    """Tests for the full agentic run() loop behaviour."""

    def test_single_turn_no_tools(self, mock_anthropic_client, basic_user):
        """If Claude returns end_turn immediately, run() should return its answer."""
        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        result = agent.run("Hello, how are you?", lat=38.99, lng=-77.03)

        assert "answer" in result
        assert result["answer"] == "Here is my recommendation based on the retrieved data."
        assert result["iterations"] == 1
        assert result["tool_log"] == []

    def test_tool_call_then_final_answer(self, mock_anthropic_client, basic_user):
        """
        Simulate Claude making one tool call then returning a final answer.
        Iteration 1: Claude returns tool_use for search_nearby_places
        Iteration 2: Claude returns end_turn with final text
        """
        # Build a tool_use block for iteration 1
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.id = "tu_001"
        tool_use_block.name = "search_nearby_places"
        tool_use_block.input = {"category": "vet", "lat": 38.99, "lng": -77.03}

        response_iter1 = MagicMock()
        response_iter1.stop_reason = "tool_use"
        response_iter1.content = [tool_use_block]

        # Final answer for iteration 2
        final_text_block = MagicMock()
        final_text_block.type = "text"
        final_text_block.text = "I found 2 vets near you."

        response_iter2 = MagicMock()
        response_iter2.stop_reason = "end_turn"
        response_iter2.content = [final_text_block]

        mock_anthropic_client.messages.create.side_effect = [
            response_iter1,
            response_iter2,
        ]

        mock_places_resp = MagicMock()
        mock_places_resp.raise_for_status = MagicMock()
        mock_places_resp.json.return_value = {"results": []}

        with patch("ai_features.requests.get", return_value=mock_places_resp):
            agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
            result = agent.run("Find a vet near me", lat=38.99, lng=-77.03)

        assert result["answer"] == "I found 2 vets near you."
        assert result["iterations"] == 2
        assert len(result["tool_log"]) == 1
        assert result["tool_log"][0]["tool"] == "search_nearby_places"

    def test_guardrail_stops_at_max_iterations(
        self, mock_anthropic_client, basic_user
    ):
        """
        Agent should stop and return a fallback message if MAX_ITERATIONS is reached
        without an end_turn response.
        """
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.id = "tu_loop"
        tool_use_block.name = "get_pet_schedule"
        tool_use_block.input = {}

        looping_response = MagicMock()
        looping_response.stop_reason = "tool_use"
        looping_response.content = [tool_use_block]

        # Every iteration returns another tool_use (infinite loop scenario)
        mock_anthropic_client.messages.create.return_value = looping_response

        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        result = agent.run("Keep going forever", lat=38.99, lng=-77.03)

        assert result["iterations"] == PawPalAgent.MAX_ITERATIONS
        assert "step limit" in result["answer"].lower() or "wasn't able" in result["answer"].lower()

    def test_tool_log_records_all_calls(self, mock_anthropic_client, basic_user):
        """Every tool call should be recorded in tool_log with tool name, input, result."""
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.id = "tu_001"
        tool_use_block.name = "get_pet_schedule"
        tool_use_block.input = {"pet_name": "Max"}

        response_iter1 = MagicMock()
        response_iter1.stop_reason = "tool_use"
        response_iter1.content = [tool_use_block]

        final_block = MagicMock()
        final_block.type = "text"
        final_block.text = "Done."

        response_iter2 = MagicMock()
        response_iter2.stop_reason = "end_turn"
        response_iter2.content = [final_block]

        mock_anthropic_client.messages.create.side_effect = [
            response_iter1,
            response_iter2,
        ]

        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        result = agent.run("What is on Max's schedule?", lat=38.99, lng=-77.03)

        assert len(result["tool_log"]) == 1
        entry = result["tool_log"][0]
        assert entry["tool"] == "get_pet_schedule"
        assert "pet_name" in entry["input"]
        assert entry["result"] is not None

    def test_add_task_tool_actually_mutates_user(
        self, mock_anthropic_client, basic_user
    ):
        """
        When Claude calls add_location_to_schedule, the user's pet tasks
        should be mutated in-place so the schedule can be regenerated.
        """
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.id = "tu_add"
        tool_use_block.name = "add_location_to_schedule"
        tool_use_block.input = {
            "pet_name": "Max",
            "task_name": "Vet visit – City Animal Hospital",
            "category": "general",
            "duration_minutes": 60,
            "preferred_time": "morning",
        }

        response_iter1 = MagicMock()
        response_iter1.stop_reason = "tool_use"
        response_iter1.content = [tool_use_block]

        final_block = MagicMock()
        final_block.type = "text"
        final_block.text = "Added vet visit to Max's schedule."

        response_iter2 = MagicMock()
        response_iter2.stop_reason = "end_turn"
        response_iter2.content = [final_block]

        mock_anthropic_client.messages.create.side_effect = [
            response_iter1,
            response_iter2,
        ]

        initial_count = len(basic_user.pets[0].tasks)
        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        agent.run("Book a vet for Max", lat=38.99, lng=-77.03)

        assert len(basic_user.pets[0].tasks) == initial_count + 1
        new_task = basic_user.pets[0].tasks[-1]
        assert new_task.name == "Vet visit – City Animal Hospital"


# ===========================================================================
# Integration with existing PawPal system
# ===========================================================================

class TestIntegrationWithPawPalSystem:
    """
    Verify that AI-added tasks integrate cleanly with the existing
    TaskScheduler and ScheduledTask classes.
    """

    def test_ai_added_task_appears_in_scheduler(
        self, mock_anthropic_client, basic_user
    ):
        """A task added by the agent should be schedulable by TaskScheduler."""
        from pawpal_system import TaskScheduler

        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        agent._tool_add_location_to_schedule(
            pet_name="Max",
            task_name="Vet visit",
            category="general",
            duration_minutes=60,
            preferred_time="morning",
        )

        basic_user.availability = ["09:00-17:00"]
        scheduler = TaskScheduler(basic_user)
        schedule = scheduler.schedule_tasks(datetime.now())

        scheduled_names = [st.task.name for st in schedule.scheduled_tasks]
        assert "Vet visit" in scheduled_names

    def test_ai_added_medication_is_prioritised_first(
        self, mock_anthropic_client, basic_user
    ):
        """Medication tasks added by AI should be scheduled before regular tasks."""
        from pawpal_system import TaskScheduler

        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        agent._tool_add_location_to_schedule(
            pet_name="Max",
            task_name="Give flea medication",
            category="medication",
            duration_minutes=5,
        )

        basic_user.availability = ["09:00-17:00"]
        scheduler = TaskScheduler(basic_user)
        schedule = scheduler.schedule_tasks(datetime.now())

        # Medication should be the first scheduled task
        first_task = schedule.get_tasks_by_time()[0]
        assert first_task.task.is_medication is True

    def test_scheduled_task_can_be_marked_complete(
        self, mock_anthropic_client, basic_user
    ):
        """An AI-added task should support mark_complete() from ScheduledTask."""
        from pawpal_system import TaskScheduler

        agent = PawPalAgent(mock_anthropic_client, "fake-google-key", basic_user)
        agent._tool_add_location_to_schedule(
            pet_name="Max",
            task_name="Park visit",
            category="walk",
            duration_minutes=45,
        )

        basic_user.availability = ["09:00-17:00"]
        scheduler = TaskScheduler(basic_user)
        schedule = scheduler.schedule_tasks(datetime.now())

        park_st = next(
            st for st in schedule.scheduled_tasks if "Park" in st.task.name
        )
        assert park_st.status == "pending"
        park_st.mark_complete(datetime.now())
        assert park_st.status == "completed"