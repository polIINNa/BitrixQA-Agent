import os

from dotenv import load_dotenv
from sqlalchemy.orm import declarative_base

load_dotenv()

Base = declarative_base()

DB_URL = f"postgresql+asyncpg://{os.getenv("DB_USER")}:{os.getenv("DB_PASSWORD")}@{os.getenv("DB_HOST")}:{os.getenv("DB_PORT")}/{os.getenv("DB_NAME")}"

DB_URL_TEST = f"postgresql+asyncpg://{os.getenv('DB_USER_TEST')}@{os.getenv('DB_HOST_TEST')}:{os.getenv('DB_PORT_TEST')}/{os.getenv('DB_NAME_TEST')}"
