import os

from celery import Celery
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# REDIS CONFIGURATION
# ============================================================
#
# Local development:
#
#     redis://127.0.0.1:6379/0
#
# Render:
#
#     REDIS_URL
#     or
#     CELERY_BROKER_URL
#
# We support both so the same code works locally and on Render.
# ============================================================

REDIS_URL = os.getenv("REDIS_URL")

CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL"
) or REDIS_URL or "redis://127.0.0.1:6379/0"

CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND"
) or REDIS_URL or CELERY_BROKER_URL


# ============================================================
# DEBUG CONFIGURATION
# ============================================================

print("=" * 70)
print("DOC AI CELERY CONFIGURATION")
print("=" * 70)

print(
    f"CELERY BROKER CONFIGURED: "
    f"{bool(CELERY_BROKER_URL)}"
)

print(
    f"CELERY RESULT BACKEND CONFIGURED: "
    f"{bool(CELERY_RESULT_BACKEND)}"
)

# Don't print the complete Redis URL because it may contain
# credentials.

if CELERY_BROKER_URL:

    if "@" in CELERY_BROKER_URL:

        print(
            "CELERY BROKER: configured with credentials"
        )

    else:

        print(
            f"CELERY BROKER: {CELERY_BROKER_URL}"
        )

print("=" * 70)


# ============================================================
# CREATE CELERY APPLICATION
# ============================================================

celery = Celery(
    "doc_ai",

    broker=CELERY_BROKER_URL,

    backend=CELERY_RESULT_BACKEND
)


# ============================================================
# CELERY CONFIGURATION
# ============================================================

celery.conf.update(

    # --------------------------------------------------------
    # Serialization
    # --------------------------------------------------------

    task_serializer="json",

    accept_content=[
        "json"
    ],

    result_serializer="json",

    # --------------------------------------------------------
    # Timezone
    # --------------------------------------------------------

    timezone="Asia/Kolkata",

    enable_utc=False,

    # --------------------------------------------------------
    # Worker behavior
    # --------------------------------------------------------
    #
    # OCR models are heavy.
    #
    # We intentionally process ONE OCR task at a time.
    #

    worker_concurrency=1,

    worker_prefetch_multiplier=1,

    # --------------------------------------------------------
    # Reliability
    # --------------------------------------------------------

    task_acks_late=True,

    task_reject_on_worker_lost=True,

    # --------------------------------------------------------
    # Track task state
    # --------------------------------------------------------

    task_track_started=True,

    # --------------------------------------------------------
    # Prevent tasks from running forever
    #
    # 45 minutes should be more than enough for one document.
    # --------------------------------------------------------

    task_soft_time_limit=40 * 60,

    task_time_limit=45 * 60,

    # --------------------------------------------------------
    # Connection retry
    # --------------------------------------------------------

    broker_connection_retry_on_startup=True,

    # --------------------------------------------------------
    # Result expiration
    # --------------------------------------------------------

    result_expires=3600
)