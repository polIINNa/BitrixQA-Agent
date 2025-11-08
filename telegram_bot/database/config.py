import os

from dotenv import load_dotenv
from sqlalchemy.orm import declarative_base

load_dotenv()

Base = declarative_base()

DB_URL = (
    os.environ["DB_URI"]
)
