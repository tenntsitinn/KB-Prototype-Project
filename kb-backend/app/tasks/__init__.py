from celery import Celery
from app.config import settings

celery_app = Celery("kb", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.timezone = "Asia/Shanghai"

# 自动发现并注册所有任务模块
celery_app.autodiscover_tasks(["app.tasks.faq_mining", "app.tasks.import_task", "app.tasks.point_task"])