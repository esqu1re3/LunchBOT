from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    amount = Column(Float, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    duty_user_id = Column(Integer, ForeignKey("users.id"))
    duty_user = relationship("User")
