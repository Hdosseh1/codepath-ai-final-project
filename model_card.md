# Anicare+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?
My initial UML included classes for `User`, `UserManager`, `TaskScheduler`, `Pet`, and `Task`, along with supporting classes for schedule persistence and AI tooling. The `TaskScheduler` handles task ordering and conflict detection, the `User` owns pets and availability, and `UserManager` manages user data and JSON persistence.
**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.
Yes. I refactored `anicare_system.py` so the `User` class directly contains pets and tasks instead of passing task IDs separately. This made the scheduler simpler: it now extracts tasks from the `User` object rather than looking up task IDs through pets.
---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?
The scheduler considers user availability, task priority, and user preferences. I decided priority matters most because high-priority work like pet medication should be scheduled even when time is tight, while lower-priority tasks can shift around.
**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?
The scheduler prioritizes tasks sequentially without performing complex backtracking or global optimization. That keeps the system simple, fast, and easy to reason about, which is reasonable for a pet care app where reliability is more important than marginal schedule improvement.
---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?
I used AI for design brainstorming, refining the UML, suggesting logic improvements, and polishing the UI text. More descriptive prompts with context were most helpful because they let the model give better-targeted suggestions.
**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?
I rejected an AI-suggested UI implementation because it looked plausible but contained syntax and indentation errors. I verified it by reviewing the generated code and comparing it to the existing app structure before accepting or adapting it.
---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?
I focused on sorting correctness, recurrence logic, and conflict detection. These tests are important because they ensure the scheduler produces a reliable and usable daily plan for pet care.
**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?
I ran a set of pytest checks and confirmed the app worked through the UI path as well. Next I would test more edge cases around multi-user or joint account scheduling and more complex task overlaps.
---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?
The integration of AI features with the existing scheduler worked cleanly, and the core scheduling logic ran reliably.
**b. What you would improve**

- If you had another iteration, what would you improve or redesign?
I would improve the UI and make the agent workflow more transparent to the user.
**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
The biggest lesson was that the challenge is often controlling the information the model sees, not getting good text. The RAG pipeline and the agent tool loop taught me that AI systems need strong discipline around context and verification.