"""Celery Beat periodic schedule.

All times in Australia/Sydney timezone (set in celery_app.py).
"""

from celery.schedules import crontab

BEAT_SCHEDULE = {
    # Domain API: every 4 hours (free tier ~500 req/day)
    "ingest-domain-api": {
        "task": "ingestion.run",
        "schedule": crontab(minute=0, hour="*/4"),
        "args": ("domain_api",),
    },
    # Batch ML prediction: daily at 3am AEST
    "ml-predict-all": {
        "task": "ml.predict_all",
        "schedule": crontab(minute=0, hour=3),
    },
    # Model retrain: weekly Sunday at 2am AEST
    "ml-retrain-weekly": {
        "task": "ml.retrain",
        "schedule": crontab(minute=0, hour=2, day_of_week="sunday"),
    },
    # OSM amenity refresh: monthly on the 1st at 4am AEST
    "osm-enrich-monthly": {
        "task": "ingestion.osm_enrich",
        "schedule": crontab(minute=0, hour=4, day_of_month=1),
    },
}
