from dataclasses import dataclass, field, asdict
from datetime import datetime, time, timedelta
from typing import List, Dict, Optional, Tuple
import json
import os
from pathlib import Path

# ==================== USER ====================
@dataclass
class User:
    username: str
    password: str
    availability: List[str] = field(default_factory=list)  # e.g., ["Mon-Fri: 9-5", "Sat: 10-12"]
    preferences: Dict[str, str] = field(default_factory=dict)
    pets: List['Pet'] = field(default_factory=list)
    
    def get_availability(self) -> List[str]:
        return self.availability
    
    def update_profile(self) -> None:
        """Updates user availability and preferences (called after form input)."""
        # In practice, this is called after Streamlit forms update the object
        pass


# ==================== TASK ====================
@dataclass
class Task:
    task_id: str
    pet_id: str
    name: str
    duration: int  # in minutes
    priority: int  # 1-5, 5 being highest
    category: str  # e.g., "feeding", "walk", "medication"
    is_medication: bool = False
    preferred_time: str = "flexible"  # "morning", "evening", "flexible"
    is_recurring: bool = False
    recurrence_pattern: str = "daily"  # "daily", "weekly", "every_other_day"
    recurrence_days: List[int] = field(default_factory=list)  # 0=Mon, 6=Sun (for weekly)
    next_due_date: Optional[datetime] = None  # Track next occurrence for recurring tasks
    
    def get_details(self) -> Dict:
        return {
            "task_id": self.task_id,
            "pet_id": self.pet_id,
            "name": self.name,
            "duration": self.duration,
            "priority": self.priority,
            "category": self.category,
            "is_medication": self.is_medication,
            "preferred_time": self.preferred_time,
            "is_recurring": self.is_recurring,
            "recurrence_pattern": self.recurrence_pattern,
            "recurrence_days": self.recurrence_days,
        }
    
    def update_priority(self, new_priority: int) -> None:
        """Update task priority (1-5, 5 being highest)."""
        if 1 <= new_priority <= 5:
            self.priority = new_priority
    
    def should_occur_on_date(self, date: datetime) -> bool:
        """Check if this recurring task should occur on the given date."""
        if not self.is_recurring:
            return True
        
        if self.recurrence_pattern == "daily":
            return True
        elif self.recurrence_pattern == "weekly":
            return date.weekday() in self.recurrence_days
        elif self.recurrence_pattern == "every_other_day":
            # Simplified: check if day is in recurrence_days (assumes caller handles logic)
            return date.weekday() in self.recurrence_days
        
        return True
    
    def calculate_next_due_date(self, current_date: datetime) -> Optional[datetime]:
        """Calculate the next due date for a recurring task using timedelta.
        
        Args:
            current_date: The date the task was completed
        
        Returns:
            The next datetime when this task is due, or None if not recurring
        """
        if not self.is_recurring:
            return None
        
        if self.recurrence_pattern == "daily":
            # Next occurrence: today + 1 day
            return current_date + timedelta(days=1)
        elif self.recurrence_pattern == "weekly":
            # Next occurrence: find the next matching weekday
            days_ahead = 7
            for days_offset in range(1, 8):
                next_date = current_date + timedelta(days=days_offset)
                if next_date.weekday() in self.recurrence_days:
                    days_ahead = days_offset
                    break
            return current_date + timedelta(days=days_ahead)
        elif self.recurrence_pattern == "every_other_day":
            # Next occurrence: today + 2 days
            return current_date + timedelta(days=2)
        
        return None


# ==================== PET ====================
@dataclass
class Pet:
    pet_id: str
    name: str
    species: str
    age: int
    health_info: str
    task_priorities: Dict[str, int] = field(default_factory=dict)  # task category -> priority
    user_preferences: Dict[str, str] = field(default_factory=dict)
    tasks: List[Task] = field(default_factory=list)
    
    def get_profile(self) -> Dict:
        return {
            "pet_id": self.pet_id,
            "name": self.name,
            "species": self.species,
            "age": self.age,
            "health_info": self.health_info,
            "task_priorities": self.task_priorities,
            "user_preferences": self.user_preferences,
            "tasks": [task.get_details() for task in self.tasks],
        }
    
    def update_profile(self) -> None:
        """Updates pet health info and preferences (called after form input)."""
        # In practice, this is called after Streamlit forms update the object
        pass
    
    def add_task(self, task: Task) -> None:
        """Add a task to this pet's task list."""
        self.tasks.append(task)


# ==================== SCHEDULED TASK ====================
@dataclass
class ScheduledTask:
    task_id: str
    start_time: time
    end_time: time
    pet_id: str
    task: Task = None
    status: str = "pending"  # pending, in_progress, completed
    scheduled_date: Optional[datetime] = None  # Track which date this instance is for
    
    def mark_complete(self, current_date: datetime = None) -> str:
        """Mark this scheduled task as completed and reschedule if recurring.
        
        For recurring tasks, automatically calculates the next due date using timedelta
        based on the recurrence pattern:
        - daily: current_date + 1 day
        - every_other_day: current_date + 2 days
        - weekly: find next matching weekday
        
        Args:
            current_date: The date the task was completed (defaults to scheduled_date or now)
        
        Returns:
            A message describing the completion and next due date if recurring
        """
        self.status = "completed"
        
        # If task is recurring, automatically schedule the next occurrence
        if self.task and self.task.is_recurring:
            if current_date is None:
                current_date = self.scheduled_date or datetime.now()
            
            next_due = self.task.calculate_next_due_date(current_date)
            self.task.next_due_date = next_due
            
            return f"✓ Completed '{self.task.name}'. Next due: {next_due.strftime('%A, %B %d, %Y') if next_due else 'N/A'}"
        
        return f"✓ Completed '{self.task.name if self.task else 'Unknown task'}'."
    
    def reschedule(self, new_start: time, new_end: time) -> None:
        """Reschedule task to new start and end times."""
        self.start_time = new_start
        self.end_time = new_end
        self.status = "pending"
    
    def get_time_string(self) -> str:
        """Return time range as 'HH:MM-HH:MM' string."""
        return f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
    
    def overlaps_with(self, other: 'ScheduledTask') -> bool:
        """Check if this task overlaps with another scheduled task."""
        return (self.start_time < other.end_time and self.end_time > other.start_time)


# ==================== DAILY SCHEDULE ====================
@dataclass
class DailySchedule:
    user_id: str
    date: datetime
    scheduled_tasks: List[ScheduledTask] = field(default_factory=list)
    explanation: str = ""
    conflicts: List[Tuple[ScheduledTask, ScheduledTask]] = field(default_factory=list)
    
    def get_tasks_by_time(self) -> List[ScheduledTask]:
        """Return tasks sorted by start time (HH:MM format)."""
        return sorted(
            self.scheduled_tasks,
            key=lambda t: (t.start_time.hour, t.start_time.minute)
        )
    
    def get_tasks_by_pet(self, pet_id: str) -> List[ScheduledTask]:
        """Filter and return tasks for a specific pet, sorted by time."""
        pet_tasks = [t for t in self.scheduled_tasks if t.pet_id == pet_id]
        return sorted(
            pet_tasks,
            key=lambda t: (t.start_time.hour, t.start_time.minute)
        )
    
    def get_tasks_by_status(self, status: str) -> List[ScheduledTask]:
        """Filter and return tasks by status (pending, in_progress, completed), sorted by time."""
        status_tasks = [t for t in self.scheduled_tasks if t.status == status]
        return sorted(
            status_tasks,
            key=lambda t: (t.start_time.hour, t.start_time.minute)
        )
    
    def get_tasks_in_time_range(self, start_time: time, end_time: time) -> List[ScheduledTask]:
        """Get all tasks that occur within a time range, sorted by start time."""
        range_tasks = [
            t for t in self.scheduled_tasks
            if t.start_time >= start_time and t.end_time <= end_time
        ]
        return sorted(
            range_tasks,
            key=lambda t: (t.start_time.hour, t.start_time.minute)
        )
    
    def get_explanation(self) -> str:
        """Return the scheduling explanation."""
        return self.explanation
    
    def has_conflicts(self) -> bool:
        """Check if schedule has any time conflicts."""
        return len(self.conflicts) > 0
    
    def get_conflict_summary(self) -> str:
        """Return a summary of conflicts in the schedule."""
        if not self.conflicts:
            return "No conflicts detected."
        
        summary = f"Found {len(self.conflicts)} conflict(s):\n"
        for task1, task2 in self.conflicts:
            summary += f"  • {task1.task.name} ({task1.get_time_string()}) overlaps with {task2.task.name} ({task2.get_time_string()})\n"
        return summary


# ==================== TASK SCHEDULER ====================
class TaskScheduler:
    def __init__(self, user: User):
        self.user = user
        self.pets = user.pets
    
    def schedule_tasks(self, date: datetime) -> DailySchedule:
        """Generate daily schedule based on user availability and task priorities."""
        # Get all tasks from all pets that should occur on this date
        all_tasks = []
        for pet in self.pets:
            for task in pet.tasks:
                if task.should_occur_on_date(date):
                    all_tasks.append(task)
        
        # Prioritize tasks (medications first, then by priority)
        prioritized_tasks = self._prioritize_tasks(all_tasks)
        
        # Fit tasks into schedule
        scheduled_tasks = self._fit_tasks_in_schedule(prioritized_tasks, date)
        
        # Create schedule
        schedule = DailySchedule(
            user_id=self.user.username,
            date=date,
            scheduled_tasks=scheduled_tasks,
        )
        
        # Detect conflicts
        schedule.conflicts = self._detect_conflicts(scheduled_tasks)
        
        # Generate explanation
        schedule.explanation = self._generate_explanation(schedule, all_tasks, scheduled_tasks)
        
        return schedule
    
    def _prioritize_tasks(self, tasks: List[Task]) -> List[Task]:
        """Sort tasks: medications first, then by priority, then by preferred time (morning->flexible->evening)."""
        medications = [t for t in tasks if t.is_medication]
        non_medications = [t for t in tasks if not t.is_medication]
        
        # Sort medications by priority
        medications.sort(key=lambda t: t.priority, reverse=True)
        
        # Sort non-medications: by priority (desc), then by preferred_time (morning > flexible > evening)
        time_order = {"morning": 0, "flexible": 1, "evening": 2}
        non_medications.sort(key=lambda t: (-t.priority, time_order.get(t.preferred_time, 1)))
        
        return medications + non_medications
    
    def _fit_tasks_in_schedule(self, prioritized_tasks: List[Task], date: datetime) -> List[ScheduledTask]:
        """Fit tasks into user's available time slots."""
        scheduled_tasks = []
        
        # Parse user availability into time slots
        available_slots = self._parse_availability(date)
        
        # Current time pointer for scheduling
        current_time = available_slots[0] if available_slots else time(9, 0)
        available_end = available_slots[1] if len(available_slots) > 1 else time(17, 0)
        
        scheduled_set = set()  # Track which tasks got scheduled
        
        for task in prioritized_tasks:
            task_duration = task.duration
            task_start = current_time
            
            # Calculate end time
            hours = task_duration // 60
            minutes = task_duration % 60
            end_hour = task_start.hour + hours
            end_minute = task_start.minute + minutes
            
            if end_minute >= 60:
                end_hour += 1
                end_minute -= 60
            
            task_end = time(end_hour, end_minute)
            
            # Check if task fits in available time
            if task_end <= available_end or task.is_medication:
                scheduled_task = ScheduledTask(
                    task_id=task.task_id,
                    start_time=task_start,
                    end_time=task_end,
                    pet_id=task.pet_id,
                    task=task,
                    status="pending",
                    scheduled_date=date,
                )
                scheduled_tasks.append(scheduled_task)
                scheduled_set.add(task.task_id)
                current_time = task_end
        
        return sorted(scheduled_tasks, key=lambda t: (t.start_time.hour, t.start_time.minute))
    
    def _detect_conflicts(self, scheduled_tasks: List[ScheduledTask]) -> List[Tuple[ScheduledTask, ScheduledTask]]:
        """Detect overlapping tasks in the schedule."""
        conflicts = []
        
        for i, task1 in enumerate(scheduled_tasks):
            for task2 in scheduled_tasks[i + 1:]:
                if task1.overlaps_with(task2):
                    conflicts.append((task1, task2))
        
        return conflicts
    
    def _generate_explanation(self, schedule: DailySchedule, all_tasks: List[Task], 
                             scheduled_tasks: List[ScheduledTask]) -> str:
        """Generate human-readable explanation for the schedule."""
        scheduled_ids = {t.task_id for t in scheduled_tasks}
        unscheduled = [t for t in all_tasks if t.task_id not in scheduled_ids]
        
        explanation = "Daily Schedule Generated:\n\n"
        
        if scheduled_tasks:
            explanation += "Scheduled Tasks (sorted by time):\n"
            for st in schedule.get_tasks_by_time():
                explanation += f"  • {st.task.name} ({st.pet_id}): {st.start_time.strftime('%H:%M')} - {st.end_time.strftime('%H:%M')} [Priority: {st.task.priority}]\n"
        
        if unscheduled:
            explanation += "\nUnable to Schedule (insufficient time):\n"
            for task in unscheduled:
                explanation += f"  • {task.name} ({task.pet_id}) - Duration: {task.duration} min [Priority: {task.priority}]\n"
        
        if schedule.has_conflicts():
            explanation += "\n" + schedule.get_conflict_summary()
        
        explanation += f"\nBased on your availability: {', '.join(self.user.availability)}"
        return explanation
    
    def _parse_availability(self, date: datetime) -> List[time]:
        """Parse availability strings into time objects."""
        # Simplified parser: assumes format like "9:00-17:00" or "9-5"
        if not self.user.availability:
            return [time(9, 0), time(17, 0)]
        
        # For now, just use the first availability slot
        avail_str = self.user.availability[0]
        try:
            if "-" in avail_str:
                parts = avail_str.split("-")
                start_str = parts[0].strip()
                end_str = parts[1].strip()
                
                # Handle both "9" and "9:00" formats
                if ":" in start_str:
                    start_time = datetime.strptime(start_str, "%H:%M").time()
                else:
                    start_time = time(int(start_str), 0)
                
                if ":" in end_str:
                    end_time = datetime.strptime(end_str, "%H:%M").time()
                else:
                    end_time = time(int(end_str), 0)
                
                return [start_time, end_time]
        except:
            pass
        
        # Default fallback
        return [time(9, 0), time(17, 0)]


# ==================== USER DATA MANAGER ====================
class UserDataManager:
    def __init__(self, storage_path: str = "users/"):
        self.storage_path = storage_path
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)
    
    def save_user(self, user: User) -> None:
        """Save user with all nested pets and tasks to JSON."""
        user_data = {
            "username": user.username,
            "password": user.password,
            "availability": user.availability,
            "preferences": user.preferences,
            "pets": [
                {
                    "pet_id": pet.pet_id,
                    "name": pet.name,
                    "species": pet.species,
                    "age": pet.age,
                    "health_info": pet.health_info,
                    "task_priorities": pet.task_priorities,
                    "user_preferences": pet.user_preferences,
                    "tasks": [
                        {
                            "task_id": task.task_id,
                            "pet_id": task.pet_id,
                            "name": task.name,
                            "duration": task.duration,
                            "priority": task.priority,
                            "category": task.category,
                            "is_medication": task.is_medication,
                            "preferred_time": task.preferred_time,
                            "is_recurring": task.is_recurring,
                            "recurrence_pattern": task.recurrence_pattern,
                            "recurrence_days": task.recurrence_days,
                            "next_due_date": task.next_due_date.isoformat() if task.next_due_date else None,
                        }
                        for task in pet.tasks
                    ],
                }
                for pet in user.pets
            ],
        }
        
        filepath = os.path.join(self.storage_path, f"{user.username}.json")
        with open(filepath, 'w') as f:
            json.dump(user_data, f, indent=2)
    
    def load_user(self, username: str) -> Optional[User]:
        """Load user with all nested pets and tasks from JSON."""
        filepath = os.path.join(self.storage_path, f"{username}.json")
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r') as f:
            user_data = json.load(f)
        
        # Reconstruct pets and tasks
        pets = []
        for pet_data in user_data.get("pets", []):
            tasks = [
                Task(
                    task_id=task_data["task_id"],
                    pet_id=task_data["pet_id"],
                    name=task_data["name"],
                    duration=task_data["duration"],
                    priority=task_data["priority"],
                    category=task_data["category"],
                    is_medication=task_data["is_medication"],
                    preferred_time=task_data.get("preferred_time", "flexible"),
                    is_recurring=task_data.get("is_recurring", False),
                    recurrence_pattern=task_data.get("recurrence_pattern", "daily"),
                    recurrence_days=task_data.get("recurrence_days", []),
                    next_due_date=datetime.fromisoformat(task_data["next_due_date"]) if task_data.get("next_due_date") else None,
                )
                for task_data in pet_data.get("tasks", [])
            ]
            
            pet = Pet(
                pet_id=pet_data["pet_id"],
                name=pet_data["name"],
                species=pet_data["species"],
                age=pet_data["age"],
                health_info=pet_data["health_info"],
                task_priorities=pet_data.get("task_priorities", {}),
                user_preferences=pet_data.get("user_preferences", {}),
                tasks=tasks,
            )
            pets.append(pet)
        
        user = User(
            username=user_data["username"],
            password=user_data["password"],
            availability=user_data.get("availability", []),
            preferences=user_data.get("preferences", {}),
            pets=pets,
        )
        return user
    
    def delete_user(self, username: str) -> None:
        """Delete user data file."""
        filepath = os.path.join(self.storage_path, f"{username}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
    
    def user_exists(self, username: str) -> bool:
        """Check if user data file exists."""
        filepath = os.path.join(self.storage_path, f"{username}.json")
        return os.path.exists(filepath)
    
    def save_schedule(self, schedule: DailySchedule) -> None:
        """Persist daily schedule to storage."""
        schedule_data = {
            "user_id": schedule.user_id,
            "date": schedule.date.isoformat(),
            "explanation": schedule.explanation,
            "scheduled_tasks": [
                {
                    "task_id": st.task_id,
                    "start_time": st.start_time.isoformat(),
                    "end_time": st.end_time.isoformat(),
                    "pet_id": st.pet_id,
                    "status": st.status,
                    "task_name": st.task.name if st.task else "Unknown",
                }
                for st in schedule.scheduled_tasks
            ],
        }
        
        schedule_dir = os.path.join(self.storage_path, schedule.user_id, "schedules")
        Path(schedule_dir).mkdir(parents=True, exist_ok=True)
        
        date_str = schedule.date.strftime("%Y-%m-%d")
        filepath = os.path.join(schedule_dir, f"{date_str}.json")
        
        with open(filepath, 'w') as f:
            json.dump(schedule_data, f, indent=2)
    
    def load_schedule(self, user_id: str, date: datetime) -> Optional[DailySchedule]:
        """Load schedule for user on specific date."""
        schedule_dir = os.path.join(self.storage_path, user_id, "schedules")
        date_str = date.strftime("%Y-%m-%d")
        filepath = os.path.join(schedule_dir, f"{date_str}.json")
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r') as f:
            schedule_data = json.load(f)
        
        scheduled_tasks = []
        for st_data in schedule_data.get("scheduled_tasks", []):
            st = ScheduledTask(
                task_id=st_data["task_id"],
                start_time=datetime.fromisoformat(st_data["start_time"]).time(),
                end_time=datetime.fromisoformat(st_data["end_time"]).time(),
                pet_id=st_data["pet_id"],
                status=st_data["status"],
            )
            scheduled_tasks.append(st)
        
        schedule = DailySchedule(
            user_id=schedule_data["user_id"],
            date=datetime.fromisoformat(schedule_data["date"]),
            scheduled_tasks=scheduled_tasks,
            explanation=schedule_data.get("explanation", ""),
        )
        return schedule
