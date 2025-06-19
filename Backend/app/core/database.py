import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.sql import func # For default timestamps

# ====================================================================
# Database Configuration
# ====================================================================

# Replace these values with your MySQL database information
DATABASE_URL = "mysql+mysqlconnector://root:@localhost:3306/ONEE_SuiviDeplacements"
# Example: "mysql+mysqlconnector://user:password@host:port/ONEE_SuiviDeplacements"

# If using Docker Compose or environment variables, you can define them here
# DATABASE_URL = os.getenv("DATABASE_URL", "mysql+mysqlconnector://user:password@host:port/ONEE_SuiviDeplacements")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get DB session
def get_db():
    """
    Dependency function to provide a database session.
    Ensures the session is closed after the request is processed.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# The 'func' object is needed in models for default timestamps,
# so we'll export it from here or ensure models import it directly from sqlalchemy.
# For simplicity, models will import func directly from sqlalchemy.