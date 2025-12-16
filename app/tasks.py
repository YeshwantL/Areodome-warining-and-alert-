from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from . import database, models

def delete_old_alerts():
    db = database.SessionLocal()
    try:
        # Delete alerts older than 6 months (or 24h for active? Requirement says "Auto-delete alerts older than the retention period (6 months)")
        # Also "History View: Dashboard must display a "Past 24 Hours" view".
        # So we keep them for 6 months.
        cutoff = datetime.utcnow() - timedelta(days=180)
        deleted_count = db.query(models.Alert).filter(models.Alert.created_at < cutoff).delete()
        db.commit()
        if deleted_count:
            print(f"Deleted {deleted_count} old alerts.")
    except Exception as e:
        print(f"Error in cleanup task: {e}")
    finally:
        db.close()

scheduler = BackgroundScheduler()
scheduler.add_job(delete_old_alerts, 'interval', hours=24)
