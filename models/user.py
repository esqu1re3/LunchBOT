from sqlalchemy import Column, Integer, String, Boolean
from .base import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    is_admin = Column(Boolean, default=False)
    is_duty = Column(Boolean, default=False)
