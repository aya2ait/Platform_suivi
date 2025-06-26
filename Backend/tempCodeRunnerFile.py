import pandas as pd
import pymysql
from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.orm import sessionmaker
import urllib.parse
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====================================================================
# Configuration des bases de données
# ====================================================================

# MySQL (source)
MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # votre mot de passe MySQL
    'database': 'ONEE_SuiviDeplacements',
    'port': 3306
}

# Azure SQL (destination)
AZURE_CONFIG = {
    'server': 'onee-sql-server-aya.database.windows.net',
    'database': 'ONEE-SuiviDeplacements',
    'username': 'onesql_admin',
    'password': 'OneeSQL2025!'
}

# ====================================================================
# Création des connexions
# ====================================================================

def create_mysql_engine():
    """Créer le moteur MySQL"""
    mysql_url = f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}"
    return create_engine(mysql_url)

def create_azure_engine():
    """Créer le moteur Azure SQL"""
    encoded_password = urllib.parse.quote_plus(AZURE_CONFIG['password'])
    azure_url = f"mssql+pyodbc://{AZURE_CONFIG['username']}:{encoded_password}@{AZURE_CONFIG['server']}/{AZURE_CONFIG['database']}?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no"
    return create_engine(azure_url, pool_pre_ping=True)

# ====================================================================
# Fonctions de migration
# ====================================================================

def get_mysql_tables(mysql_engine):
    """Récupérer la liste des tables MySQL"""
    with mysql_engine.connect() as conn:
        result = conn.execute(text("SHOW TABLES"))
        tables = [row[0] for row in result]
    return tables

def migrate_table_data(table_name, mysql_engine, azure_engine):
    """Migrer les données d'une table spécifique"""
    try:
        logger.info(f"Migration de la table: {table_name}")
        
        # Lire les données depuis MySQL
        df = pd.read_sql(f"SELECT * FROM {table_name}", mysql_engine)
        logger.info(f"Lignes trouvées dans {table_name}: {len(df)}")
        
        if len(df) > 0:
            # Écrire vers Azure SQL
            df.to_sql(
                table_name, 
                azure_engine, 
                if_exists='replace',  # ou 'append' si vous voulez ajouter
                index=False,
                method='multi'  # Plus rapide pour grandes tables
            )
            logger.info(f"✅ Table {table_name} migrée avec succès!")
        else:
            logger.info(f"ℹ️ Table {table_name} est vide")
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la migration de {table_name}: {e}")

def migrate_schema_with_sqlalchemy(mysql_engine, azure_engine):
    """Migrer le schéma en utilisant SQLAlchemy MetaData"""
    try:
        # Lire le schéma MySQL
        mysql_metadata = MetaData()
        mysql_metadata.reflect(bind=mysql_engine)
        
        # Créer les tables dans Azure SQL
        mysql_metadata.create_all(azure_engine)
        logger.info("✅ Schéma migré avec succès!")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la migration du schéma: {e}")

def test_connections():
    """Tester les connexions aux deux bases"""
    try:
        # Test MySQL
        mysql_engine = create_mysql_engine()
        with mysql_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Connexion MySQL OK")
        
        # Test Azure SQL
        azure_engine = create_azure_engine()
        with azure_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Connexion Azure SQL OK")
        
        return mysql_engine, azure_engine
        
    except Exception as e:
        logger.error(f"❌ Erreur de connexion: {e}")
        return None, None

def full_migration():
    """Migration complète"""
    logger.info("🚀 Début de la migration...")
    
    # Test des connexions
    mysql_engine, azure_engine = test_connections()
    if not mysql_engine or not azure_engine:
        return
    
    try:
        # 1. Migrer le schéma
        logger.info("📋 Migration du schéma...")
        migrate_schema_with_sqlalchemy(mysql_engine, azure_engine)
        
        # 2. Récupérer les tables
        tables = get_mysql_tables(mysql_engine)
        logger.info(f"📊 Tables trouvées: {tables}")
        
        # 3. Migrer chaque table
        for table in tables:
            migrate_table_data(table, mysql_engine, azure_engine)
        
        logger.info("🎉 Migration terminée avec succès!")
        
    except Exception as e:
        logger.error(f"❌ Erreur générale: {e}")
    
    finally:
        mysql_engine.dispose()
        azure_engine.dispose()

def migrate_specific_tables(table_list):
    """Migrer seulement certaines tables"""
    mysql_engine, azure_engine = test_connections()
    if not mysql_engine or not azure_engine:
        return
    
    try:
        for table in table_list:
            migrate_table_data(table, mysql_engine, azure_engine)
        logger.info("🎉 Migration des tables spécifiées terminée!")
        
    finally:
        mysql_engine.dispose()
        azure_engine.dispose()

# ====================================================================
# Utilisation
# ====================================================================

if __name__ == "__main__":
    # Option 1: Migration complète
    #full_migration()
    
    # Option 2: Migration de tables spécifiques
    # migrate_specific_tables(['users', 'vehicules', 'deplacements'])
    
    # Option 3: Test des connexions seulement
    test_connections()