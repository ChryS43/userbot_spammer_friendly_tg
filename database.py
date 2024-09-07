from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

# Configurazione SQLAlchemy
Base = declarative_base()

class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, unique=True)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Crea il database e la connessione
engine = create_engine('sqlite:///groups.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
