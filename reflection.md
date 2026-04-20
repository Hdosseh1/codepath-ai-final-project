# Anicare+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?
My initial UML has about 7 classes each handling different but linked tasks. There is a class for the task scheduler that schedules for the user listed in the user class. The task scheduler does references the pet class which has a task. The user data is managed by the user manager class.
**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.
The code in anicare_system.py was refactored to allow the user class have pets and tasks instead of passing them separately. The task scheduler also just extracts tasks from the user instead of looking up task ids from the pet.
---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?
Currrently the scheduler considers the user's availability or time constraints, their preferences and the priority they put on certain tasks for instance medication. After review with some pet owners and Copilot, I determined that priority should matter most over the others since a task like medication for the pet should be considered as important despite the user's availability.
**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?
The scheduler prioritizes tasks and schedules them sequentially without rearrangin the overall layout. This makes it simple, fast and easy to understand but then it misses the chance improve the overall schedule by backtracking. For this scenario, it is a good tradeoff since we do not want to do anything too complex that might break the app for a minimal improvement.
---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?
I used Ai to help me dign the UML, suggest better logi methods and polish the UI. I realized that giving the AI tools more descriptive promts and adding context helps them work better.
**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?
I asked the AI for suggestions regarding the UI design and although the suggested code was correct, it had syntax errors. I had to reject it and ask it to redo it since i read through it and realised its suggestions were wrongly indented.
---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?
The sorting correctness, recurrence logic and conflict detedtion were the main things i tested.
These allowed me ensure that the system had a strong reliability and that the core actions were implemented.
**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?
I run a couple of pytests and deployed the app online too and it still works well. i would like to test if multiple users could be added to a joint account.
---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?
The logic and algorithims were implemented well and run withour a single error message.
**b. What you would improve**

- If you had another iteration, what would you improve or redesign?
The UI
**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
You always have to read through the code AI gives you - it may seem right at first glance but requires your supervision and judgement to make it better.