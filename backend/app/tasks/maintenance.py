from celery import shared_task
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def cleanup_temp_files(self):
    """Clean up temporary files older than 24 hours"""
    try:
        logger.info("Cleaning up temporary files...")
        temp_path = "/data/temp"
        if os.path.exists(temp_path):
            now = datetime.now()
            for filename in os.listdir(temp_path):
                filepath = os.path.join(temp_path, filename)
                file_modified = datetime.fromtimestamp(os.path.getmtime(filepath))
                if now - file_modified > timedelta(hours=24):
                    os.remove(filepath)
                    logger.info(f"Deleted old temp file: {filename}")
        return {"status": "completed", "cleaned_at": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Error cleaning temp files: {str(e)}")
        raise


@shared_task(bind=True)
def schedule_maintenance(self, item_id: str, maintenance_type: str):
    """Schedule maintenance for an airport item"""
    try:
        logger.info(f"Scheduling {maintenance_type} maintenance for item {item_id}")
        # TODO: Implement maintenance scheduling logic
        return {
            "status": "scheduled",
            "item_id": item_id,
            "maintenance_type": maintenance_type,
            "scheduled_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error scheduling maintenance: {str(e)}")
        raise