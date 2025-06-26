import pandas as pd
import pymysql
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Text, DateTime, Numeric, Boolean, ForeignKey
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
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
    azure_url = f"mssql+pyodbc://{AZURE_CONFIG['username']}:{encoded_password}@{AZURE_CONFIG['server']}/{AZURE_CONFIG['database']}?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no"
    return create_engine(azure_url, pool_pre_ping=True)

# ====================================================================
# Correction pour les colonnes IDENTITY dans Azure SQL
# ====================================================================

def fix_identity_columns(azure_engine):
    """Corriger les colonnes IDENTITY pour Azure SQL"""
    
    # Liste des tables et leurs colonnes id qui doivent être IDENTITY
    tables_to_fix = [
        'TypeCollaborateur', 'Direction', 'Utilisateur', 'Directeur', 
        'TauxIndemnite', 'Collaborateur', 'Vehicule', 'Mission', 
        'Affectation', 'Trajet', 'Anomalie', 'Remboursement'
    ]
    
    with azure_engine.connect() as conn:
        for table_name in tables_to_fix:
            try:
                logger.info(f"Correction de la colonne IDENTITY pour {table_name}")
                
                # Vérifier si la colonne est déjà IDENTITY
                check_query = text(f"""
                    SELECT COLUMNPROPERTY(OBJECT_ID('{table_name}'), 'id', 'IsIdentity') as is_identity
                """)
                result = conn.execute(check_query).fetchone()
                
                if result and result[0] == 0:  # Pas IDENTITY
                    logger.info(f"Correction nécessaire pour {table_name}")
                    
                    # Script pour recréer la table avec IDENTITY
                    temp_table = f"{table_name}_temp"
                    
                    # 1. Créer une table temporaire avec la structure correcte
                    create_temp_query = text(f"""
                        SELECT * INTO {temp_table} FROM {table_name}
                    """)
                    conn.execute(create_temp_query)
                    
                    # 2. Supprimer la table originale
                    drop_query = text(f"DROP TABLE {table_name}")
                    conn.execute(drop_query)
                    
                    # 3. Recréer la table avec IDENTITY selon le modèle
                    if table_name == 'Mission':
                        create_query = text(f"""
                            CREATE TABLE {table_name} (
                                id int IDENTITY(1,1) PRIMARY KEY,
                                objet nvarchar(max) NOT NULL,
                                dateDebut datetime2 NOT NULL,
                                dateFin datetime2 NOT NULL,
                                moyenTransport nvarchar(50),
                                trajet_predefini nvarchar(max),
                                statut nvarchar(50) DEFAULT 'CREEE',
                                vehicule_id int,
                                directeur_id int NOT NULL,
                                created_at datetime2 DEFAULT GETDATE(),
                                updated_at datetime2 DEFAULT GETDATE(),
                                FOREIGN KEY (vehicule_id) REFERENCES Vehicule(id),
                                FOREIGN KEY (directeur_id) REFERENCES Directeur(id)
                            )
                        """)
                    elif table_name == 'TypeCollaborateur':
                        create_query = text(f"""
                            CREATE TABLE {table_name} (
                                id int IDENTITY(1,1) PRIMARY KEY,
                                nom nvarchar(50) UNIQUE NOT NULL,
                                created_at datetime2 DEFAULT GETDATE(),
                                updated_at datetime2 DEFAULT GETDATE()
                            )
                        """)
                    elif table_name == 'Direction':
                        create_query = text(f"""
                            CREATE TABLE {table_name} (
                                id int IDENTITY(1,1) PRIMARY KEY,
                                nom nvarchar(100) NOT NULL,
                                montantInitial decimal(15,2) DEFAULT 0.00,
                                montantConsomme decimal(15,2) DEFAULT 0.00,
                                mois nvarchar(10) NOT NULL,
                                annee int NOT NULL,
                                created_at datetime2 DEFAULT GETDATE(),
                                updated_at datetime2 DEFAULT GETDATE()
                            )
                        """)
                    elif table_name == 'Utilisateur':
                        create_query = text(f"""
                            CREATE TABLE {table_name} (
                                id int IDENTITY(1,1) PRIMARY KEY,
                                login nvarchar(100) UNIQUE NOT NULL,
                                motDePasse nvarchar(255) NOT NULL,
                                role nvarchar(50) NOT NULL,
                                created_at datetime2 DEFAULT GETDATE(),
                                updated_at datetime2 DEFAULT GETDATE()
                            )
                        """)
                    elif table_name == 'Directeur':
                        create_query = text(f"""
                            CREATE TABLE {table_name} (
                                id int IDENTITY(1,1) PRIMARY KEY,
                                utilisateur_id int NOT NULL,
                                direction_id int NOT NULL,
                                nom nvarchar(100) NOT NULL,
                                prenom nvarchar(100) NOT NULL,
                                created_at datetime2 DEFAULT GETDATE(),
                                updated_at datetime2 DEFAULT GETDATE(),
                                FOREIGN KEY (utilisateur_id) REFERENCES Utilisateur(id),
                                FOREIGN KEY (direction_id) REFERENCES Direction(id)
                            )
                        """)
                    elif table_name == 'TauxIndemnite':
                        create_query = text(f"""
                            CREATE TABLE {table_name} (
                                id int IDENTITY(1,1) PRIMARY KEY,
                                type_collaborateur_id int NOT NULL,
                                tauxDejeuner decimal(10,2) DEFAULT 0.00,
                                tauxDinner decimal(10,2) DEFAULT 0.00,
                                tauxAccouchement decimal(10,2) DEFAULT 0.00,
                                created_at datetime2 DEFAULT GETDATE(),
                                updated_at datetime2 DEFAULT GETDATE(),
                                FOREIGN KEY (type_collaborateur_id) REFERENCES TypeCollaborateur(id)
                            )
                        """)
                    elif table_name == 'Collaborateur':
                        create_query = text(f"""
                            CREATE TABLE {table_name} (
                                id int IDENTITY(1,1) PRIMARY KEY,
                                nom nvarchar(100) NOT NULL,
                                matricule nvarchar(50) UNIQUE NOT NULL,
                                type_collaborateur_id int NOT NULL,
                                direction_id int NOT NULL,
                                taux_indemnite_id int NOT NULL,
                                disponible bit DEFAULT 1,
                                created_at datetime2 DEFAULT GETDATE(),
                                updated_at datetime2 DEFAULT GETDATE(),
                                FOREIGN KEY (type_collaborateur_id) REFERENCES TypeCollaborateur(id),
                                FOREIGN KEY (direction_id) REFERENCES Direction(id),
                                FOREIGN KEY (taux_indemnite_id) REFERENCES TauxIndemnite(id)
                            )
                        """)
                    elif table_name == 'Vehicule':
                        create_query = text(f"""
                            CREATE TABLE {table_name} (
                                id int IDENTITY(1,1) PRIMARY KEY,
                                immatriculation nvarchar(20) UNIQUE NOT NULL,
                                marque nvarchar(50) NOT NULL,
                                modele nvarchar(50),
                                created_at datetime2 DEFAULT GETDATE(),
                                updated_at datetime2 DEFAULT GETDATE()
                            )
                        """)
                    elif table_name == 'Affectation':
                        create_query = text(f"""
                            CREATE TABLE {table_name} (
                                id int IDENTITY(1,1) PRIMARY KEY,
                                mission_id int NOT NULL,
                                collaborateur_id int NOT NULL,
                                dejeuner int DEFAULT 0,
                                dinner int DEFAULT 0,
                                accouchement int DEFAULT 0,
                                montantCalcule decimal(15,2) DEFAULT 0.00,
                                created_at datetime2 DEFAULT GETDATE(),
                                updated_at datetime2 DEFAULT GETDATE(),
                                FOREIGN KEY (mission_id) REFERENCES Mission(id) ON DELETE CASCADE,
                                FOREIGN KEY (collaborateur_id) REFERENCES Collaborateur(id) ON DELETE CASCADE
                            )
                        """)
                    elif table_name == 'Trajet':
                        create_query = text(f"""
                            CREATE TABLE {table_name} (
                                id int IDENTITY(1,1) PRIMARY KEY,
                                mission_id int NOT NULL,
                                timestamp datetime2 DEFAULT GETDATE(),
                                latitude decimal(10,8) NOT NULL,
                                longitude decimal(11,8) NOT NULL,
                                vitesse decimal(5,2) DEFAULT 0.00,
                                created_at datetime2 DEFAULT GETDATE(),
                                FOREIGN KEY (mission_id) REFERENCES Mission(id) ON DELETE CASCADE
                            )
                        """)
                    elif table_name == 'Anomalie':
                        create_query = text(f"""
                            CREATE TABLE {table_name} (
                                id int IDENTITY(1,1) PRIMARY KEY,
                                mission_id int NOT NULL,
                                type nvarchar(100) NOT NULL,
                                description nvarchar(max),
                                dateDetection datetime2 DEFAULT GETDATE() NOT NULL,
                                created_at datetime2 DEFAULT GETDATE(),
                                FOREIGN KEY (mission_id) REFERENCES Mission(id) ON DELETE CASCADE
                            )
                        """)
                    elif table_name == 'Remboursement':
                        create_query = text(f"""
                            CREATE TABLE {table_name} (
                                id int IDENTITY(1,1) PRIMARY KEY,
                                affectation_id int NOT NULL,
                                matriculeMission nvarchar(100),
                                nom nvarchar(100) NOT NULL,
                                mois nvarchar(10) NOT NULL,
                                annee int NOT NULL,
                                montant decimal(15,2) NOT NULL,
                                created_at datetime2 DEFAULT GETDATE(),
                                updated_at datetime2 DEFAULT GETDATE(),
                                FOREIGN KEY (affectation_id) REFERENCES Affectation(id) ON DELETE CASCADE
                            )
                        """)
                    
                    conn.execute(create_query)
                    
                    # 4. Réinsérer les données en excluant la colonne id pour l'auto-incrémentation
                    insert_query = text(f"""
                        SET IDENTITY_INSERT {table_name} ON;
                        INSERT INTO {table_name} SELECT * FROM {temp_table};
                        SET IDENTITY_INSERT {table_name} OFF;
                    """)
                    conn.execute(insert_query)
                    
                    # 5. Supprimer la table temporaire
                    drop_temp_query = text(f"DROP TABLE {temp_table}")
                    conn.execute(drop_temp_query)
                    
                    logger.info(f"✅ {table_name} corrigée avec IDENTITY")
                else:
                    logger.info(f"✅ {table_name} a déjà IDENTITY")
                    
            except Exception as e:
                logger.error(f"❌ Erreur lors de la correction de {table_name}: {e}")
        
        # Commit les changements
        conn.commit()

# ====================================================================
# Fonctions de migration modifiées
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

def full_migration_with_identity_fix():
    """Migration complète avec correction des colonnes IDENTITY"""
    logger.info("🚀 Début de la migration avec correction IDENTITY...")
    
    # Test des connexions
    mysql_engine, azure_engine = test_connections()
    if not mysql_engine or not azure_engine:
        return
    
    try:
        # 1. Récupérer les tables
        tables = get_mysql_tables(mysql_engine)
        logger.info(f"📊 Tables trouvées: {tables}")
        
        # 2. Migrer chaque table
        for table in tables:
            migrate_table_data(table, mysql_engine, azure_engine)
        
        # 3. Corriger les colonnes IDENTITY après migration
        logger.info("🔧 Correction des colonnes IDENTITY...")
        fix_identity_columns(azure_engine)
        
        logger.info("🎉 Migration terminée avec succès!")
        
    except Exception as e:
        logger.error(f"❌ Erreur générale: {e}")
    
    finally:
        mysql_engine.dispose()
        azure_engine.dispose()

def fix_existing_azure_tables():
    """Corriger seulement les colonnes IDENTITY des tables existantes"""
    logger.info("🔧 Correction des colonnes IDENTITY existantes...")
    
    # Test des connexions
    _, azure_engine = test_connections()
    if not azure_engine:
        return
    
    try:
        fix_identity_columns(azure_engine)
        logger.info("🎉 Correction des colonnes IDENTITY terminée!")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la correction: {e}")
    
    finally:
        azure_engine.dispose()

# ====================================================================
# Utilisation
# ====================================================================

if __name__ == "__main__":
    # Option 1: Migration complète avec correction IDENTITY
    # full_migration_with_identity_fix()
    
    # Option 2: Corriger seulement les colonnes IDENTITY des tables existantes
    fix_existing_azure_tables()
    
    # Option 3: Test des connexions seulement
    # test_connections()