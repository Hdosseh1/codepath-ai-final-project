# PawPal+ AI

**An intelligent pet care scheduling assistant** powered by Claude Sonnet 4, featuring a RAG pipeline for real-time location discovery and an agentic workflow that autonomously manages pet schedules.

---

## Original project

This project extends **PawPal+**, built in Modules 1–3 of AI 110. The original app allowed a pet owner to create profiles for their pets, add care tasks (walks, feedings, medications, grooming), and generate a prioritized daily schedule that respected the owner's availability window. It included conflict detection, recurring task support, and a JSON-based persistence layer — but it had no AI features; all scheduling was rule-based Python logic.

---

## Title and summary

**PawPal+ AI** adds two integrated AI capabilities to the original scheduler:

1. A **RAG pipeline** that retrieves real nearby vets, parks, and pet supply stores from Google Places and uses Claude to generate grounded, context-aware recommendations — so the app never invents locations.
2. An **agentic workflow** where Claude autonomously calls tools to search for places, read the pet's schedule, check business hours, and add new tasks — completing multi-step scheduling requests in a single natural-language prompt.

Together these turn PawPal+ from a manual task tracker into a proactive AI scheduling assistant. A pet owner can type "find a good vet near me and add an appointment for Max on Saturday morning" and the system handles the rest.

---

## Architecture overview

![Data flow diagram](assets/pipeline.png)

The system has two parallel pipelines that share the same Claude model:

**RAG pipeline (left side):** The user's query triggers a Google Places Nearby Search, which returns up to 5 real locations. These are formatted into a plain-text context block and passed directly to Claude. Claude's answer is grounded exclusively in the retrieved data — it cannot hallucinate place names or addresses because the system prompt explicitly forbids it.

**Agentic pipeline (right side):** Claude is given five tools — `search_nearby_places`, `get_pet_schedule`, `add_location_to_schedule`, `get_next_appointment`, and `check_place_hours`. Claude autonomously decides which tools to call and in what order (Plan → Act → Verify loop), executing up to 5 iterations before a guardrail fires. Every tool call mutates the live `User` object, so any task Claude adds is immediately visible to the existing `TaskScheduler`.

Both pipelines converge at Claude Sonnet 4 and deliver a response through the Streamlit UI.

![Oversight and testing layers](assets/tests.png)

Quality is enforced at three levels: automated pytest (33 mocked tests, no API keys required), human-in-the-loop review via the visible tool-call trace in the UI, and runtime guardrails including a 5-iteration cap, full logging to `pawpal_ai.log`, and per-tool error handling.

---

## Setup instructions

**Requirements:** Python 3.9+, a free Anthropic API key, and a Google Places API key.

### 1. Clone and enter the repo

```bash
git clone https://github.com/Hdosseh1/ai110-module2show-pawpal-starter.git
cd ai110-module2show-pawpal-starter
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your `.env` file

Create a file named `.env` in the project root (same folder as `app.py`):

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
GOOGLE_PLACES_KEY=AIzaSy-your-key-here
```

**Getting keys:**
- Anthropic key: [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) — free $5 credit on signup
- Google Places key: [console.cloud.google.com](https://console.cloud.google.com) → Enable Places API → Credentials → Create API Key — free $200/month credit

### 5. Run the app

```bash
streamlit run app.py
```

### 6. Run the tests (no API keys needed)

```bash
python -m pytest test_ai_features.py -v
```

---

## Sample interactions

### Sample 1 — RAG: finding a nearby vet

**Input:** User selects "Veterinary clinic", enters their coordinates, and asks *"Which of these is best for my dog who needs a routine checkup?"*

**AI output:**
> Based on the nearby locations retrieved, City Animal Hospital (4.7 stars, currently open) would be the best choice for a routine checkup. It has the highest rating of the options nearby and is open right now. Paws & Claws Vet (4.2 stars) is also a solid option if City Animal Hospital doesn't have availability — though it appears to be closed at this time.

The answer references only the two real locations returned by Google Places. No locations are invented.

---

### Sample 2 — Agent: adding a vet appointment

**Input:** *"Find the best-rated vet near me and add a 60-minute appointment to Max's schedule for tomorrow morning."*

**Agent tool call trace:**
1. `search_nearby_places` — category: vet, returns 5 nearby clinics
2. `add_location_to_schedule` — adds "Vet visit – City Animal Hospital", 60 min, morning, to Max

**AI output:**
> I found City Animal Hospital nearby with a 4.7-star rating. I've added a 60-minute vet appointment for Max tomorrow morning. Head to the sidebar and click Generate schedule to see it in your daily plan.

---

### Sample 3 — Agent: checking an existing appointment

**Input:** *"When is Max's next vet appointment, and is the vet open right now?"*

**Agent tool call trace:**
1. `get_next_appointment` — returns Max's "Vet visit – City Animal Hospital" task with next due date
2. `check_place_hours` — retrieves live hours for the place ID

**AI output:**
> Max's next vet appointment is scheduled for May 1st. City Animal Hospital is currently open — their hours today are 8:00 AM to 6:00 PM, and their phone number is (301) 555-0182.

---

## Design decisions

**Why separate `ai_features.py` from `app.py`?**
Keeping all AI logic in its own module means the original scheduling code in `pawpal_system.py` is completely untouched. If the AI features break or need to be disabled, a single import line is all that changes. It also makes the AI code independently testable without spinning up Streamlit.

**Why Google Places for RAG retrieval instead of a vector database?**
A vector database (Chroma, Pinecone) is the right tool when you need to search static documents — pet care articles, vet notes. For finding real nearby businesses that change daily (hours, ratings, new locations), a live API is strictly better. The retrieved data is always current and already structured, so there is no embedding step needed.

**Why Claude Sonnet 4 and not Opus?**
Sonnet 4 handles multi-step tool use and grounded synthesis well, runs significantly faster, and costs roughly 5× less per token than Opus. For a scheduling assistant where the user expects near-instant responses, Sonnet is the right trade-off. Opus would be justified only for complex reasoning tasks where accuracy is worth the latency and cost.

**Why cap the agent at 5 iterations?**
Without a hard ceiling, a misbehaving prompt or an unexpected tool result could cause the agent to loop indefinitely, burning API credits. Five iterations is enough to handle any realistic scheduling request (search → check hours → add task is 3 iterations). The guardrail fires rarely in practice but is essential for a production-like system.

---

## Reliability and evaluation

**33 out of 33 automated tests passed.** The test suite (`test_ai_features.py`) covers the RAG pipeline, all five agent tools, the agentic loop, and integration with the existing scheduler — all using `unittest.mock` so no API keys are required and results are fully deterministic.

**Automated tests:** 8 test classes, 33 cases. Key checks include: Places API results are capped at 5 and normalised correctly; context blocks always contain place names, ratings, and open/closed status; Claude receives the retrieved data in its prompt; the agent loop terminates under the 5-iteration guardrail; tasks added by the agent appear in `TaskScheduler` output; and medication tasks are always prioritised first.

**Logging and error handling:** Every tool call and every Places API request is logged to `pawpal_ai.log` with timestamp, tool name, and input parameters. All tool implementations are wrapped in `try/except` and return a structured `{"error": "..."}` JSON on failure instead of crashing. The agent loop catches exceptions at the dispatch level so one bad tool call does not abort the whole session.

**Human evaluation:** The visible tool-call trace in the Streamlit UI (collapsed expander under each agent response) lets the user inspect every step the agent took — what it searched for, what it found, and what it added. The user must click "Generate schedule" to apply any agent-added task, which acts as an explicit human approval step before the schedule changes.

**Confidence summary:** The RAG pipeline is highly reliable when Google Places returns results — Claude's answer is grounded in real data and the system prompt prevents hallucination. Reliability drops when the user's coordinates are imprecise or outside a dense urban area, since Places may return zero results. The agent is reliable for 1–2 tool requests; complex multi-tool chains occasionally require a follow-up prompt to complete fully.

---

## Reflection and ethics

**Limitations and biases in the system:**
The RAG pipeline is only as good as Google Places data. Rural areas, newly opened clinics, or businesses with outdated listings will produce poor or empty results. The agent has no memory between sessions — it cannot remember that the user already found a vet last week. The system also assumes the user's location is accurate; a wrong latitude/longitude will return entirely irrelevant results with no warning. Claude's responses are in English only and assume a US-style address format from the Places API.

**Could this AI be misused, and how is that prevented?**
The most realistic misuse is prompt injection — a user crafting a message that tricks the agent into adding unwanted tasks or calling tools in unintended ways. This is mitigated by three things: the tool schemas are strictly typed (the agent cannot call a tool with an invalid category), the 5-iteration cap limits the blast radius of any runaway instruction, and every task the agent adds still requires the human to click "Generate schedule" before it affects the actual plan. A more serious concern would be location privacy — the app sends the user's coordinates to Google. For a production deployment this should be disclosed in a privacy notice; for a class project the coordinates are entered manually by the user so they are aware.

**What surprised you while testing reliability?**
The most surprising result was how robustly the agent handled an empty Places API response. When `search_nearby_places` returned `[]`, Claude did not hallucinate locations — it correctly reported that no results were found and suggested the user try a wider radius. This was not explicitly enforced in the system prompt beyond "never invent place names", which suggests the model's grounding behaviour is stronger than expected when the retrieved context is clearly empty rather than absent.

**Collaboration with AI during this project:**

*Helpful instance:* When designing the tool schemas for the agentic workflow, Claude was asked to suggest what parameters `add_location_to_schedule` should accept. It proposed including `preferred_time` and `is_recurring` as optional fields — inputs that had not been considered initially. This was a genuinely useful suggestion because it meant the agent could schedule a recurring weekly park visit in a single tool call rather than requiring a follow-up. The suggestion was adopted directly.

*Flawed instance:* Early in development, Claude generated type hints using the `X | None` union syntax (e.g., `str | None`) which is only valid in Python 3.10+. The project runs on Python 3.9, so the app crashed on startup with a `TypeError` when Streamlit tried to import the file. Claude had not checked the Python version before writing the code. The fix was simple (`from __future__ import annotations` at the top of each file), but it was a reminder that AI-generated code needs to be checked against the actual runtime environment, not assumed to be universally compatible.
