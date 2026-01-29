from sqlalchemy import Column, Integer, String, Float
from app.db.database import Base

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    strategy = Column(String)
    max_loss = Column(Float)
    timestamp = Column(String)
