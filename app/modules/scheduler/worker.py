"""
Background worker for processing scheduled posts

For MVP: Run this as a separate process or use a task queue like Celery
In production: Use Celery, RQ, or similar task queue system
"""
import time
from app.database import SessionLocal
from app.modules.scheduler.service import SchedulerService


def run_scheduler_worker(interval: int = 60):
    """Run scheduler worker that checks for due posts every interval seconds"""
    db = SessionLocal()
    
    try:
        while True:
            print(f"Checking for due posts...")
            published = SchedulerService.process_due_posts(db)
            if published:
                print(f"Published {len(published)} posts")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Scheduler worker stopped")
    finally:
        db.close()


if __name__ == "__main__":
    run_scheduler_worker(interval=60)  # Check every minute
