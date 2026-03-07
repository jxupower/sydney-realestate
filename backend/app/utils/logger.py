import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog for structured JSON logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_logger_name,
            structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def init_sentry(dsn: str, environment: str = "production", release: str | None = None) -> None:
    """Initialise Sentry SDK if a DSN is configured.

    Call once at application startup (before request handling begins).
    No-ops silently if dsn is empty.
    """
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            traces_sample_rate=0.1,   # 10% of requests traced for performance
            profiles_sample_rate=0.05,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                CeleryIntegration(monitor_beat_tasks=True),
            ],
            # Don't send PII (IP addresses, user agents)
            send_default_pii=False,
        )
    except ImportError:
        # sentry-sdk not installed — skip silently
        pass
