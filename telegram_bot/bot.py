import os
import re
import sys
import random
import asyncio
import logging

from dotenv import load_dotenv
from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from db_service import init_db, get_all_users, add_user, get_admins


load_dotenv()
TOKEN = os.environ["TELEGRAM_API_TOKEN_TEST"]

dp = Dispatcher()
bot = Bot(
    TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)