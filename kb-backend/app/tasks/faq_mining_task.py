"""
Celery Beat 定时调度配置。
启动方式: celery -A app.tasks.faq_mining_task beat --loglevel=info
"""

# ============================================================
# 定时任务配置（通过环境变量覆盖，不硬编码）
# ============================================================
import os

# FAQ 自动挖掘：crontab 各字段，默认每周一凌晨 3:00
BEAT_FAQ_MINING_MINUTE = os.getenv("BEAT_FAQ_MINING_MINUTE", "0")
BEAT_FAQ_MINING_HOUR = os.getenv("BEAT_FAQ_MINING_HOUR", "3")
BEAT_FAQ_MINING_DAY_OF_WEEK = os.getenv("BEAT_FAQ_MINING_DAY_OF_WEEK", "1")  # 0=周日, 1=周一

# ============================================================

from celery.schedules import crontab
from app.tasks import celery_app

celery_app.conf.timezone = "Asia/Shanghai"
celery_app.conf.beat_schedule = {
    "faq-auto-mining": {
        "task": "faq.mine",
        "schedule": crontab(
            minute=BEAT_FAQ_MINING_MINUTE,
            hour=BEAT_FAQ_MINING_HOUR,
            day_of_week=BEAT_FAQ_MINING_DAY_OF_WEEK,
        ),
    },
}