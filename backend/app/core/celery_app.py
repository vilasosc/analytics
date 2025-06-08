from celery import Celery
from app.core.config import settings

# Initialize Celery
# The first argument to Celery is the name of the current module.
# This is only needed so that names can be auto-generated when tasks are defined in the __main__ module.
celery_app = Celery(
    "worker",  # Or any suitable name for your Celery app
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['app.tasks.sync_tasks']  # Tells Celery to look for tasks in this module
)

# Optional Celery configuration, see Celery docs for more options
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],  # Ignore other content
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Add other configurations as needed
)

# If you want to auto-discover tasks from a specific path or naming convention:
# celery_app.autodiscover_tasks(['app.tasks']) # Example, if tasks are in app.tasks
# For now, we will explicitly register tasks or include modules.

if __name__ == "__main__":
    # This allows running celery worker directly using: python -m app.core.celery_app worker -l info
    celery_app.start()
