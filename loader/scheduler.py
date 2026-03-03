"""Долгоживущий планировщик loader'а. Запускает main() по расписанию (воскресенье 18:00)."""
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from loader.config import get_config
from loader.main import main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_scheduler() -> None:
    cfg = get_config()
    trigger = CronTrigger(
        day_of_week=cfg.schedule_day_of_week,
        hour=cfg.schedule_hour,
        minute=cfg.schedule_minute,
    )
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.ensure_future(main()), trigger)
    scheduler.start()
    logger.info(
        "Scheduler запущен. Расписание: %s %02d:%02d",
        cfg.schedule_day_of_week,
        cfg.schedule_hour,
        cfg.schedule_minute,
    )
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(run_scheduler())
