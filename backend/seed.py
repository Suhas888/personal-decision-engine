from app.database.core import SessionLocal, engine, Base
from app.models.core import UserProfile, Task, FixedEvent


def seed_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # User Profile
    if not db.query(UserProfile).first():
        profile = UserProfile(
            name="Suhas",
            preferred_start_hour=450,  # 7:30
            preferred_end_hour=1350,  # 22:30
            sleep_start=1380,  # 23:00
            sleep_end=420,  # 7:00
            max_focus_block_minutes=120,
        )
        db.add(profile)

    # Tasks
    if not db.query(Task).first():
        tasks = [
            Task(title="GATE preparation", estimated_minutes=900, priority=1),
            Task(
                title="VLSI project",
                estimated_minutes=480,
                priority=1,
                deadline="Friday",
            ),
            Task(title="LLM development", estimated_minutes=300, priority=2),
            Task(title="YouTube", estimated_minutes=180, priority=3),
        ]
        db.add_all(tasks)

    # Fixed Events
    if not db.query(FixedEvent).first():
        events = []
        for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            events.append(
                FixedEvent(title="College", day_of_week=d, start_time=540, end_time=960)
            )
        db.add_all(events)

    db.commit()
    db.close()
    print("Database seeded with sample data.")


if __name__ == "__main__":
    seed_db()
