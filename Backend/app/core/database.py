import os
import urllib.parse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func  # For default timestamps

# ====================================================================
# Database Configuration - Azure SQL
# ====================================================================

# Encodage du mot de passe
encoded_password = urllib.parse.quote_plus("OneeSQL2025!")

# Connexion à Azure SQL
DATABASE_URL = (
    f"mssql+pyodbc://onesql_admin:{encoded_password}"
    f"@onee-sql-server-aya.database.windows.net/ONEE-SuiviDeplacements"
    f"?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
