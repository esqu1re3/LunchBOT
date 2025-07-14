from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import settings
from models.base import Base
from models.user import User
from models.expense import Expense
from models.transaction import Transaction

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
