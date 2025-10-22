from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os


DB_URL = os.getenv("DB_URL", "sqlite:///./bali_gigs.db")


engine = create_engine(
DB_URL,
connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
