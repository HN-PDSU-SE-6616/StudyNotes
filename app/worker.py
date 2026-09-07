"""Celery 应用入口（broker/result = Redis）

队列划分：
- parse：文件解析（parse_document）
- index：向量索引与推荐（index_note / delete_note_index / refresh_recommendations）
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "taot_kb",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.parse",
        "app.tasks.index",
        "app.tasks.recommend",
    ],
)

celery_app.conf.update(
    task_default_queue="parse",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    timezone="Asia/Shanghai",
    enable_utc=False,
    result_expires=3600,
    task_routes={
        "app.tasks.index.*": {"queue": "index"},
        "app.tasks.recommend.*": {"queue": "index"},
        "app.tasks.parse.*": {"queue": "parse"},
    },
    beat_schedule={
        "refresh-recommendations-daily": {
            "task": "app.tasks.recommend.refresh_recommendations",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)
