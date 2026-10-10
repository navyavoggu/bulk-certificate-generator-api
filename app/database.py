from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

def build_database(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args, future=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
    return engine, SessionLocal
