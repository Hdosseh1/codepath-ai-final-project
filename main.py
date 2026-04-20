from datetime import datetime, time
from anicare_system import User, Pet, Task, TaskScheduler, UserDataManager

def main():
    """Test the Anicare+ system with advanced features: filtering, conflicts, and recurring tasks."""
    
    print("=" * 60)
    print("Anicare+ System Test (Advanced)")
    print("=" * 60)
    
    # ==================== CREATE USER ====================
    print("\n1. Creating user...")
    user = User(
        username="johndoe",
        password="secure123",
        availability=["9:00-17:00"],
        preferences={"pet_care_style": "balanced", "preferred_times": "morning"}
    )
    print(f"   ✓ User created: {user.username}")
    print(f"   ✓ Availability: {user.availability}")
    
    # ==================== CREATE PETS ====================
    print("\n2. Creating pets...")
    dog = Pet(
        pet_id="pet_001",
        name="Max",
        species="Dog",
        age=3,
        health_info="Healthy, needs daily walks",
        task_priorities={"walk": 5, "feeding": 4, "play": 3},
        user_preferences={"preferred_walk_time": "morning", "frequency": "2x daily"}
    )
    print(f"   ✓ Pet created: {dog.name} ({dog.species})")
    
    cat = Pet(
        pet_id="pet_002",
        name="Whiskers",
        species="Cat",
        age=5,
        health_info="Healthy, on medication",
        task_priorities={"feeding": 5, "medication": 5, "play": 2},
        user_preferences={"preferred_feeding_time": "morning and evening"}
    )
    print(f"   ✓ Pet created: {cat.name} ({cat.species})")
    
    user.pets = [dog, cat]
    
    # ==================== CREATE TASKS (with recurring support) ====================
    print("\n3. Adding tasks (including recurring)...")
    
    # Dog: recurring morning walk (daily)
    dog_walk_morning = Task(
        task_id="task_001",
        pet_id="pet_001",
        name="Morning Walk",
        duration=30,
        priority=5,
        category="walk",
        is_medication=False,
        preferred_time="morning",
        is_recurring=True,
        recurrence_pattern="daily",
        recurrence_days=[]
    )
    dog.add_task(dog_walk_morning)
    print(f"   ✓ RECURRING: {dog_walk_morning.name} (daily)")
    
    dog_feeding = Task(
        task_id="task_002",
        pet_id="pet_001",
        name="Feeding",
        duration=15,
        priority=4,
        category="feeding",
        is_medication=False,
        preferred_time="flexible",
        is_recurring=True,
        recurrence_pattern="daily"
    )
    dog.add_task(dog_feeding)
    print(f"   ✓ RECURRING: {dog_feeding.name} (daily)")
    
    dog_evening_walk = Task(
        task_id="task_003",
        pet_id="pet_001",
        name="Evening Walk",
        duration=30,
        priority=5,
        category="walk",
        is_medication=False,
        preferred_time="evening",
        is_recurring=True,
        recurrence_pattern="daily"
    )
    dog.add_task(dog_evening_walk)
    print(f"   ✓ RECURRING: {dog_evening_walk.name} (daily)")
    
    # Cat: medication (high priority)
    cat_medication = Task(
        task_id="task_004",
        pet_id="pet_002",
        name="Morning Medication",
        duration=5,
        priority=5,
        category="medication",
        is_medication=True,
        preferred_time="morning",
        is_recurring=True,
        recurrence_pattern="daily"
    )
    cat.add_task(cat_medication)
    print(f"   ✓ RECURRING: {cat_medication.name} (MEDICATION)")
    
    cat_feeding_morning = Task(
        task_id="task_005",
        pet_id="pet_002",
        name="Morning Feeding",
        duration=10,
        priority=5,
        category="feeding",
        is_medication=False,
        preferred_time="morning",
        is_recurring=True,
        recurrence_pattern="daily"
    )
    cat.add_task(cat_feeding_morning)
    print(f"   ✓ RECURRING: {cat_feeding_morning.name} (daily)")
    
    cat_play = Task(
        task_id="task_006",
        pet_id="pet_002",
        name="Playtime",
        duration=20,
        priority=2,
        category="play",
        is_medication=False,
        preferred_time="flexible",
        is_recurring=False
    )
    cat.add_task(cat_play)
    print(f"   ✓ ONE-TIME: {cat_play.name}")
    
    # ==================== GENERATE SCHEDULE ====================
    print("\n4. Generating daily schedule...")
    scheduler = TaskScheduler(user)
    today = datetime.now()
    schedule = scheduler.schedule_tasks(today)
    
    print(f"   ✓ Schedule generated for {today.strftime('%A, %B %d, %Y')}")
    
    # ==================== DISPLAY SCHEDULE ====================
    print("\n" + "=" * 60)
    print("TODAY'S SCHEDULE")
    print("=" * 60)
    
    print(f"\nUser: {user.username}")
    print(f"Date: {today.strftime('%A, %B %d, %Y')}")
    print(f"Available: {', '.join(user.availability)}")
    
    print("\n" + "-" * 60)
    print("ALL TASKS (sorted by time using lambda key):")
    print("-" * 60)
    
    tasks_by_time = schedule.get_tasks_by_time()
    if tasks_by_time:
        for i, scheduled_task in enumerate(tasks_by_time, 1):
            pet_name = next((p.name for p in user.pets if p.pet_id == scheduled_task.pet_id), "Unknown")
            print(f"\n{i}. {scheduled_task.task.name}")
            print(f"   Pet: {pet_name} | Time: {scheduled_task.get_time_string()} | Priority: {scheduled_task.task.priority}/5")
    
    # ==================== FILTER BY PET ====================
    print("\n" + "-" * 60)
    print(f"TASKS FOR MAX (pet_001) - sorted by time:")
    print("-" * 60)
    dog_tasks = schedule.get_tasks_by_pet("pet_001")
    if dog_tasks:
        for task in dog_tasks:
            print(f"  • {task.task.name}: {task.get_time_string()}")
    else:
        print("  No tasks scheduled for Max")
    
    # ==================== FILTER BY STATUS ====================
    print("\n" + "-" * 60)
    print("PENDING TASKS (sorted by time):")
    print("-" * 60)
    pending = schedule.get_tasks_by_status("pending")
    if pending:
        for task in pending:
            print(f"  • {task.task.name}: {task.get_time_string()}")
    
    # ==================== FILTER BY TIME RANGE ====================
    print("\n" + "-" * 60)
    print("TASKS BETWEEN 9:00 AM and 12:00 PM:")
    print("-" * 60)
    morning_tasks = schedule.get_tasks_in_time_range(time(9, 0), time(12, 0))
    if morning_tasks:
        for task in morning_tasks:
            print(f"  • {task.task.name}: {task.get_time_string()}")
    else:
        print("  No tasks in this time range")
    
    # ==================== CONFLICT DETECTION ====================
    print("\n" + "-" * 60)
    print("CONFLICT DETECTION:")
    print("-" * 60)
    if schedule.has_conflicts():
        print(schedule.get_conflict_summary())
    else:
        print("  ✓ No conflicts detected!")
    
    # ==================== FULL EXPLANATION ====================
    print("\n" + "-" * 60)
    print("SCHEDULING EXPLANATION:")
    print("-" * 60)
    print(schedule.get_explanation())
    
    print("\n" + "=" * 60)
    print("6. Testing automatic task rescheduling...")
    print("=" * 60)
    
    # Mark a recurring task as complete
    if tasks_by_time:
        print(f"\nMarking '{tasks_by_time[0].task.name}' as completed...")
        completion_msg = tasks_by_time[0].mark_complete(today)
        print(f"   {completion_msg}")
        
        if tasks_by_time[0].task.is_recurring and tasks_by_time[0].task.next_due_date:
            print(f"\n   Task Details:")
            print(f"   - Status: {tasks_by_time[0].status}")
            print(f"   - Original Date: {today.strftime('%A, %B %d, %Y')}")
            print(f"   - Next Due: {tasks_by_time[0].task.next_due_date.strftime('%A, %B %d, %Y')}")
            print(f"   - Days Until Next: {(tasks_by_time[0].task.next_due_date - today).days} day(s)")
    
    # ==================== SAVE DATA ====================
    print("\n" + "=" * 60)
    print("7. Saving user data and schedule...")
    data_manager = UserDataManager()
    data_manager.save_user(user)
    data_manager.save_schedule(schedule)
    print(f"   ✓ Data saved successfully")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
