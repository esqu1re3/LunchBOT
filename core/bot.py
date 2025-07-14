import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from core.handlers import register_handlers
from config import settings
import logging

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher()
    register_handlers(dp)
    await dp.start_polling(bot)
