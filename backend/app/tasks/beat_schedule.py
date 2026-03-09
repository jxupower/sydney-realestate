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
    # Homely.com.au scrape: daily at 1am AEST (server-side rendered — no headless browser needed)
    "ingest-homely-daily": {
        "task": "ingestion.run",
        "schedule": crontab(minute=0, hour=1),
        "args": ("homely",),
    },
    # Fuzzy VG match: daily at 5am AEST (after VG import and ingestion)
    "fuzzy-vg-match-daily": {
        "task": "ingestion.run",
        "schedule": crontab(minute=0, hour=5),
        "args": ("fuzzy_vg_match",),
    },
    # OSM amenity refresh: monthly on the 1st at 4am AEST
    "osm-enrich-monthly": {
        "task": "ingestion.osm_enrich",
        "schedule": crontab(minute=0, hour=4, day_of_month=1),
    },
    # Optuna hyperparameter tuning: monthly on the 1st at 2am AEST
    "optuna-tune-monthly": {
        "task": "ml.tune",
        "schedule": crontab(minute=0, hour=2, day_of_month=1),
        "kwargs": {"n_trials": 100},
    },
}
