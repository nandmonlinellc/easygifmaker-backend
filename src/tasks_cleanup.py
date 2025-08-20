import os
import time
import logging
import shutil
from flask import current_app
from src.celery_app import celery as celery_app

@celery_app.task(name="tasks.cleanup_old_files")
def cleanup_old_files():
    """Cleans up old temporary user directories from the UPLOAD_FOLDER."""
    try:
        # Use a path relative to the configured UPLOAD_FOLDER
        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not upload_folder or not os.path.isdir(upload_folder):
            logging.warning(f"UPLOAD_FOLDER '{upload_folder}' not configured or does not exist. Cleanup task skipped.")
            return

        user_uploads_dir = os.path.join(upload_folder, "user_uploads")
        if not os.path.isdir(user_uploads_dir):
            logging.info(f"User uploads directory does not exist, skipping: {user_uploads_dir}")
            return

        # Use a configurable max age
        max_age_seconds = current_app.config.get('TEMP_FILE_MAX_AGE')
        now = time.time()
        deleted_count = 0
        
        logging.info(f"Running cleanup on {user_uploads_dir} for items older than {max_age_seconds} seconds.")

        for item_name in os.listdir(user_uploads_dir):
            item_path = os.path.join(user_uploads_dir, item_name)
            try:
                # We are cleaning up the session directories
                if os.path.isdir(item_path):
                    item_age = now - os.path.getmtime(item_path)
                    if item_age > max_age_seconds:
                        shutil.rmtree(item_path, ignore_errors=True)
                        logging.info(f"Deleted old temporary directory: {item_path}")
                        deleted_count += 1
            except FileNotFoundError:
                # Can happen if another process deletes it
                continue
        logging.info(f"Cleanup complete. Deleted {deleted_count} old directories.")
    except Exception as e:
        logging.error(f"Error in cleanup task: {e}", exc_info=True)

# Scheduled via Celery beat using TEMP_FILE_CLEANUP_INTERVAL.
