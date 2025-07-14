from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import settings
from models.user import Base as UserBase
from models.expense import Base as ExpenseBase
from models.transaction import Base as TransactionBase

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    UserBase.metadata.create_all(bind=engine)
    ExpenseBase.metadata.create_all(bind=engine)
    TransactionBase.metadata.create_all(bind=engine)
