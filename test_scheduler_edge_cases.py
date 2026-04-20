import pytest
from datetime import datetime, time, timedelta
from anicare_system import User, Pet, Task, ScheduledTask, DailySchedule, TaskScheduler


# ==================== SORTING CORRECTNESS TESTS ====================

class TestSortingCorrectness:
    """Verify tasks are returned in chronological order."""
    
    def test_get_tasks_by_time_chronological_order(self):
        """Tasks should be sorted by start time in ascending order."""
        schedule = DailySchedule(
            user_id="user1",
            date=datetime(2026, 2, 15)
        )
        
        # Add tasks in reverse chronological order
        task3 = ScheduledTask(task_id="t3", start_time=time(15, 0), end_time=time(15, 30), pet_id="p1", status="pending")
        task1 = ScheduledTask(task_id="t1", start_time=time(9, 0), end_time=time(9, 30), pet_id="p1", status="pending")
        task2 = ScheduledTask(task_id="t2", start_time=time(12, 0), end_time=time(12, 30), pet_id="p1", status="pending")
        
        schedule.scheduled_tasks = [task3, task1, task2]
        
        sorted_tasks = schedule.get_tasks_by_time()
        
        assert sorted_tasks[0].task_id == "t1"
        assert sorted_tasks[1].task_id == "t2"
        assert sorted_tasks[2].task_id == "t3"
    
    def test_get_tasks_by_time_with_minutes(self):
        """Sorting should respect minutes in addition to hours."""
        schedule = DailySchedule(
            user_id="user1",
            date=datetime(2026, 2, 15)
        )
        
        task1 = ScheduledTask(task_id="t1", start_time=time(9, 45), end_time=time(10, 0), pet_id="p1", status="pending")
        task2 = ScheduledTask(task_id="t2", start_time=time(9, 30), end_time=time(9, 45), pet_id="p1", status="pending")
        task3 = ScheduledTask(task_id="t3", start_time=time(9, 0), end_time=time(9, 30), pet_id="p1", status="pending")
        
        schedule.scheduled_tasks = [task1, task2, task3]
        
        sorted_tasks = schedule.get_tasks_by_time()
        
        assert sorted_tasks[0].start_time == time(9, 0)
        assert sorted_tasks[1].start_time == time(9, 30)
        assert sorted_tasks[2].start_time == time(9, 45)
    
    def test_get_tasks_by_time_single_task(self):
        """Single task should return list with one element."""
        schedule = DailySchedule(
            user_id="user1",
            date=datetime(2026, 2, 15)
        )
        
        task = ScheduledTask(task_id="t1", start_time=time(9, 0), end_time=time(9, 30), pet_id="p1", status="pending")
        schedule.scheduled_tasks = [task]
        
        sorted_tasks = schedule.get_tasks_by_time()
        
        assert len(sorted_tasks) == 1
        assert sorted_tasks[0].task_id == "t1"
    
    def test_get_tasks_by_time_empty_schedule(self):
        """Empty schedule should return empty list."""
        schedule = DailySchedule(
            user_id="user1",
            date=datetime(2026, 2, 15)
        )
        
        sorted_tasks = schedule.get_tasks_by_time()
        
        assert sorted_tasks == []
    
    def test_prioritization_medications_first(self):
        """Medications should be prioritized before non-medications."""
        user = User(username="john", password="pass", availability=["9-17"])
        pet = Pet(pet_id="p1", name="Buddy", species="Dog", age=2, health_info="")
        user.pets = [pet]
        
        # Create tasks: non-medication priority 5, medication priority 1
        med_task = Task(
            task_id="med1", pet_id="p1", name="Medication", duration=5,
            priority=1, category="medication", is_medication=True
        )
        high_priority_task = Task(
            task_id="t1", pet_id="p1", name="Play", duration=30,
            priority=5, category="play", is_medication=False
        )
        
        pet.tasks = [high_priority_task, med_task]
        
        scheduler = TaskScheduler(user)
        prioritized = scheduler._prioritize_tasks(pet.tasks)
        
        # Medication should come first despite lower priority
        assert prioritized[0].task_id == "med1"
        assert prioritized[1].task_id == "t1"
    
    def test_prioritization_by_priority_level(self):
        """Non-medications should be sorted by priority (descending)."""
        user = User(username="john", password="pass", availability=["9-17"])
        pet = Pet(pet_id="p1", name="Buddy", species="Dog", age=2, health_info="")
        user.pets = [pet]
        
        task1 = Task(
            task_id="t1", pet_id="p1", name="Task1", duration=10,
            priority=3, category="play", is_medication=False
        )
        task2 = Task(
            task_id="t2", pet_id="p1", name="Task2", duration=10,
            priority=5, category="play", is_medication=False
        )
        task3 = Task(
            task_id="t3", pet_id="p1", name="Task3", duration=10,
            priority=1, category="play", is_medication=False
        )
        
        pet.tasks = [task1, task2, task3]
        scheduler = TaskScheduler(user)
        prioritized = scheduler._prioritize_tasks(pet.tasks)
        
        assert prioritized[0].priority == 5
        assert prioritized[1].priority == 3
        assert prioritized[2].priority == 1
    
    def test_prioritization_preferred_time_order(self):
        """Same priority tasks should sort morning > flexible > evening."""
        user = User(username="john", password="pass", availability=["9-17"])
        pet = Pet(pet_id="p1", name="Buddy", species="Dog", age=2, health_info="")
        user.pets = [pet]
        
        morning_task = Task(
            task_id="t1", pet_id="p1", name="Morning Task", duration=10,
            priority=3, category="play", is_medication=False, preferred_time="morning"
        )
        flexible_task = Task(
            task_id="t2", pet_id="p1", name="Flexible Task", duration=10,
            priority=3, category="play", is_medication=False, preferred_time="flexible"
        )
        evening_task = Task(
            task_id="t3", pet_id="p1", name="Evening Task", duration=10,
            priority=3, category="play", is_medication=False, preferred_time="evening"
        )
        
        pet.tasks = [evening_task, flexible_task, morning_task]
        scheduler = TaskScheduler(user)
        prioritized = scheduler._prioritize_tasks(pet.tasks)
        
        assert prioritized[0].preferred_time == "morning"
        assert prioritized[1].preferred_time == "flexible"
        assert prioritized[2].preferred_time == "evening"


# ==================== RECURRENCE LOGIC TESTS ====================

class TestRecurrenceLogic:
    """Confirm that marking tasks complete creates new occurrences correctly."""
    
    def test_daily_recurrence_next_due_date(self):
        """Daily task marked complete should be due the next day."""
        task = Task(
            task_id="t1", pet_id="p1", name="Daily Feed", duration=10,
            priority=3, category="feeding", is_medication=False,
            is_recurring=True, recurrence_pattern="daily"
        )
        
        current_date = datetime(2026, 2, 15)
        next_due = task.calculate_next_due_date(current_date)
        
        expected = datetime(2026, 2, 16)
        assert next_due == expected
    
    def test_daily_recurrence_across_month_boundary(self):
        """Daily task on last day of month should correctly roll to next month."""
        task = Task(
            task_id="t1", pet_id="p1", name="Daily Feed", duration=10,
            priority=3, category="feeding", is_medication=False,
            is_recurring=True, recurrence_pattern="daily"
        )
        
        # February 28, 2026 (non-leap year)
        current_date = datetime(2026, 2, 28)
        next_due = task.calculate_next_due_date(current_date)
        
        expected = datetime(2026, 3, 1)
        assert next_due == expected
    
    def test_daily_recurrence_across_year_boundary(self):
        """Daily task on Dec 31 should be due Jan 1."""
        task = Task(
            task_id="t1", pet_id="p1", name="Daily Feed", duration=10,
            priority=3, category="feeding", is_medication=False,
            is_recurring=True, recurrence_pattern="daily"
        )
        
        current_date = datetime(2025, 12, 31)
        next_due = task.calculate_next_due_date(current_date)
        
        expected = datetime(2026, 1, 1)
        assert next_due == expected
    
    def test_weekly_recurrence_next_matching_weekday(self):
        """Weekly task should find next matching weekday (0=Mon, 6=Sun)."""
        task = Task(
            task_id="t1", pet_id="p1", name="Weekly Walk", duration=30,
            priority=2, category="walk", is_medication=False,
            is_recurring=True, recurrence_pattern="weekly",
            recurrence_days=[0, 2, 4]  # Mon, Wed, Fri
        )
        
        # Sunday, Feb 15, 2026
        current_date = datetime(2026, 2, 15)  # Sunday
        next_due = task.calculate_next_due_date(current_date)
        
        # Next should be Monday (Feb 16)
        expected = datetime(2026, 2, 16)
        assert next_due == expected
        assert next_due.weekday() == 0  # Monday
    
    def test_weekly_recurrence_same_day_skip_to_next_week(self):
        """Weekly task on matching day should go to same day next week."""
        task = Task(
            task_id="t1", pet_id="p1", name="Weekly Walk", duration=30,
            priority=2, category="walk", is_medication=False,
            is_recurring=True, recurrence_pattern="weekly",
            recurrence_days=[0]  # Monday only
        )
        
        # Monday, Feb 16, 2026
        current_date = datetime(2026, 2, 16)
        next_due = task.calculate_next_due_date(current_date)
        
        # Next Monday is Feb 23
        expected = datetime(2026, 2, 23)
        assert next_due == expected
        assert next_due.weekday() == 0
    
    def test_weekly_recurrence_multiple_days_across_month_boundary(self):
        """Weekly task spanning month boundary should correctly find next occurrence."""
        task = Task(
            task_id="t1", pet_id="p1", name="Weekly Walk", duration=30,
            priority=2, category="walk", is_medication=False,
            is_recurring=True, recurrence_pattern="weekly",
            recurrence_days=[2, 4]  # Wed, Fri
        )
        
        # Friday, Feb 27, 2026
        current_date = datetime(2026, 2, 27)
        next_due = task.calculate_next_due_date(current_date)
        
        # Next should be Wednesday, March 4
        expected = datetime(2026, 3, 4)
        assert next_due == expected
        assert next_due.weekday() == 2  # Wednesday
    
    def test_every_other_day_recurrence(self):
        """Every other day task should be due 2 days later."""
        task = Task(
            task_id="t1", pet_id="p1", name="Every Other Day Task", duration=15,
            priority=3, category="play", is_medication=False,
            is_recurring=True, recurrence_pattern="every_other_day"
        )
        
        current_date = datetime(2026, 2, 15)
        next_due = task.calculate_next_due_date(current_date)
        
        expected = datetime(2026, 2, 17)
        assert next_due == expected
    
    def test_every_other_day_across_month_boundary(self):
        """Every other day task should correctly handle month boundaries."""
        task = Task(
            task_id="t1", pet_id="p1", name="Every Other Day Task", duration=15,
            priority=3, category="play", is_medication=False,
            is_recurring=True, recurrence_pattern="every_other_day"
        )
        
        # Feb 27, 2026
        current_date = datetime(2026, 2, 27)
        next_due = task.calculate_next_due_date(current_date)
        
        expected = datetime(2026, 3, 1)
        assert next_due == expected
    
    def test_non_recurring_task_returns_none(self):
        """Non-recurring task should return None for next due date."""
        task = Task(
            task_id="t1", pet_id="p1", name="One-time Task", duration=20,
            priority=2, category="play", is_medication=False,
            is_recurring=False
        )
        
        current_date = datetime(2026, 2, 15)
        next_due = task.calculate_next_due_date(current_date)
        
        assert next_due is None
    
    def test_mark_complete_updates_next_due_date(self):
        """Marking a scheduled recurring task complete should update next_due_date."""
        task = Task(
            task_id="t1", pet_id="p1", name="Daily Feed", duration=10,
            priority=3, category="feeding", is_medication=True,
            is_recurring=True, recurrence_pattern="daily"
        )
        
        scheduled_task = ScheduledTask(
            task_id="t1",
            start_time=time(9, 0),
            end_time=time(9, 10),
            pet_id="p1",
            task=task,
            status="pending",
            scheduled_date=datetime(2026, 2, 15)
        )
        
        # Mark complete
        result = scheduled_task.mark_complete(datetime(2026, 2, 15))
        
        # Verify status changed
        assert scheduled_task.status == "completed"
        
        # Verify next due date was calculated
        assert task.next_due_date is not None
        assert task.next_due_date == datetime(2026, 2, 16)
        
        # Verify message includes next due date
        assert "Next due" in result


# ==================== CONFLICT DETECTION TESTS ====================

class TestConflictDetection:
    """Verify that the scheduler flags overlapping times."""
    
    def test_detect_simple_overlap(self):
        """Tasks with overlapping times should be flagged as conflicts."""
        scheduler = TaskScheduler(User(username="john", password="pass", availability=["9-17"], pets=[]))
        
        task1 = ScheduledTask(
            task_id="t1", start_time=time(9, 0), end_time=time(9, 30),
            pet_id="p1", status="pending"
        )
        task2 = ScheduledTask(
            task_id="t2", start_time=time(9, 15), end_time=time(9, 45),
            pet_id="p2", status="pending"
        )
        
        conflicts = scheduler._detect_conflicts([task1, task2])
        
        assert len(conflicts) == 1
        assert conflicts[0] == (task1, task2)
    
    def test_no_conflict_back_to_back_tasks(self):
        """Back-to-back tasks (no overlap) should not conflict."""
        scheduler = TaskScheduler(User(username="john", password="pass", availability=["9-17"], pets=[]))
        
        task1 = ScheduledTask(
            task_id="t1", start_time=time(9, 0), end_time=time(9, 15),
            pet_id="p1", status="pending"
        )
        task2 = ScheduledTask(
            task_id="t2", start_time=time(9, 15), end_time=time(9, 30),
            pet_id="p2", status="pending"
        )
        
        conflicts = scheduler._detect_conflicts([task1, task2])
        
        assert len(conflicts) == 0
    
    def test_no_conflict_non_overlapping_tasks(self):
        """Non-overlapping tasks should have no conflicts."""
        scheduler = TaskScheduler(User(username="john", password="pass", availability=["9-17"], pets=[]))
        
        task1 = ScheduledTask(
            task_id="t1", start_time=time(9, 0), end_time=time(9, 30),
            pet_id="p1", status="pending"
        )
        task2 = ScheduledTask(
            task_id="t2", start_time=time(10, 0), end_time=time(10, 30),
            pet_id="p2", status="pending"
        )
        
        conflicts = scheduler._detect_conflicts([task1, task2])
        
        assert len(conflicts) == 0
    
    def test_detect_multiple_conflicts(self):
        """Multiple overlapping pairs should all be detected."""
        scheduler = TaskScheduler(User(username="john", password="pass", availability=["9-17"], pets=[]))
        
        task1 = ScheduledTask(
            task_id="t1", start_time=time(9, 0), end_time=time(9, 30),
            pet_id="p1", status="pending"
        )
        task2 = ScheduledTask(
            task_id="t2", start_time=time(9, 15), end_time=time(9, 45),
            pet_id="p2", status="pending"
        )
        task3 = ScheduledTask(
            task_id="t3", start_time=time(9, 20), end_time=time(9, 50),
            pet_id="p3", status="pending"
        )
        
        conflicts = scheduler._detect_conflicts([task1, task2, task3])
        
        # Should have conflicts: (t1,t2), (t1,t3), (t2,t3)
        assert len(conflicts) == 3
    
    def test_conflict_with_containment(self):
        """Task completely contained within another should be flagged."""
        scheduler = TaskScheduler(User(username="john", password="pass", availability=["9-17"], pets=[]))
        
        task1 = ScheduledTask(
            task_id="t1", start_time=time(9, 0), end_time=time(10, 0),
            pet_id="p1", status="pending"
        )
        task2 = ScheduledTask(
            task_id="t2", start_time=time(9, 15), end_time=time(9, 30),
            pet_id="p2", status="pending"
        )
        
        conflicts = scheduler._detect_conflicts([task1, task2])
        
        assert len(conflicts) == 1
    
    def test_schedule_has_conflicts_flag(self):
        """DailySchedule should correctly report if conflicts exist."""
        schedule = DailySchedule(
            user_id="user1",
            date=datetime(2026, 2, 15)
        )
        
        assert not schedule.has_conflicts()
        
        task1 = ScheduledTask(
            task_id="t1", start_time=time(9, 0), end_time=time(9, 30),
            pet_id="p1", status="pending"
        )
        task2 = ScheduledTask(
            task_id="t2", start_time=time(9, 15), end_time=time(9, 45),
            pet_id="p2", status="pending"
        )
        
        schedule.scheduled_tasks = [task1, task2]
        schedule.conflicts = [(task1, task2)]
        
        assert schedule.has_conflicts()
    
    def test_conflict_summary_message(self):
        """Conflict summary should describe each conflict clearly."""
        task1 = Task(task_id="t1", pet_id="p1", name="Feed Buddy", duration=10, priority=3, category="feeding")
        task2 = Task(task_id="t2", pet_id="p2", name="Walk Max", duration=20, priority=2, category="walk")
        
        st1 = ScheduledTask(
            task_id="t1", start_time=time(9, 0), end_time=time(9, 10),
            pet_id="p1", task=task1, status="pending"
        )
        st2 = ScheduledTask(
            task_id="t2", start_time=time(9, 5), end_time=time(9, 25),
            pet_id="p2", task=task2, status="pending"
        )
        
        schedule = DailySchedule(
            user_id="user1",
            date=datetime(2026, 2, 15),
            scheduled_tasks=[st1, st2],
            conflicts=[(st1, st2)]
        )
        
        summary = schedule.get_conflict_summary()
        
        assert "conflict" in summary.lower()
        assert "Feed Buddy" in summary
        assert "Walk Max" in summary


# ==================== INTEGRATION TESTS ====================

class TestSchedulerIntegration:
    """Test sorting, recurrence, and conflicts working together."""
    
    def test_full_schedule_generation_with_recurring_tasks(self):
        """Full schedule should correctly prioritize and schedule recurring tasks."""
        user = User(
            username="john",
            password="pass",
            availability=["9-17"],
            pets=[]
        )
        
        pet = Pet(pet_id="p1", name="Buddy", species="Dog", age=2, health_info="")
        
        # Medication (recurring daily)
        med_task = Task(
            task_id="med1", pet_id="p1", name="Medication", duration=5,
            priority=5, category="medication", is_medication=True,
            is_recurring=True, recurrence_pattern="daily"
        )
        
        # Regular task (non-recurring)
        play_task = Task(
            task_id="t1", pet_id="p1", name="Play", duration=30,
            priority=3, category="play", is_medication=False,
            is_recurring=False
        )
        
        pet.tasks = [play_task, med_task]
        user.pets = [pet]
        
        scheduler = TaskScheduler(user)
        schedule = scheduler.schedule_tasks(datetime(2026, 2, 15))
        
        # Verify tasks are scheduled
        assert len(schedule.scheduled_tasks) == 2
        
        # Verify medication is scheduled first (by time)
        tasks_by_time = schedule.get_tasks_by_time()
        assert tasks_by_time[0].task.is_medication
        assert tasks_by_time[0].start_time == time(9, 0)
    
    def test_schedule_respects_availability_bounds(self):
        """Tasks should not be scheduled outside user availability."""
        user = User(
            username="john",
            password="pass",
            availability=["9-12"],  # Only 3 hours available
            pets=[]
        )
        
        pet = Pet(pet_id="p1", name="Buddy", species="Dog", age=2, health_info="")
        
        # Large task that won't fit
        large_task = Task(
            task_id="t1", pet_id="p1", name="Long Task", duration=240,  # 4 hours
            priority=1, category="play", is_medication=False
        )
        
        pet.tasks = [large_task]
        user.pets = [pet]
        
        scheduler = TaskScheduler(user)
        schedule = scheduler.schedule_tasks(datetime(2026, 2, 15))
        
        # Task should not be scheduled
        assert len(schedule.scheduled_tasks) == 0
        assert "Unable to Schedule" in schedule.explanation
    
    def test_medication_overrides_availability(self):
        """Medications should be scheduled even if they exceed availability."""
        user = User(
            username="john",
            password="pass",
            availability=["9-12"],
            pets=[]
        )
        
        pet = Pet(pet_id="p1", name="Buddy", species="Dog", age=2, health_info="")
        
        # Medication that exceeds availability
        med_task = Task(
            task_id="med1", pet_id="p1", name="Critical Medication", duration=300,
            priority=5, category="medication", is_medication=True
        )
        
        pet.tasks = [med_task]
        user.pets = [pet]
        
        scheduler = TaskScheduler(user)
        schedule = scheduler.schedule_tasks(datetime(2026, 2, 15))
        
        # Medication should be scheduled despite exceeding availability
        assert len(schedule.scheduled_tasks) == 1
        assert schedule.scheduled_tasks[0].task.is_medication
