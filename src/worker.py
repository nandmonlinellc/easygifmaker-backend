from src.main import create_app
# Import tasks to ensure they are registered with Celery
from src import tasks

flask_app = create_app()
celery_app = flask_app.celery