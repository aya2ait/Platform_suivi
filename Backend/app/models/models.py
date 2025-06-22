from sqlalchemy import Column, Integer, String, Text, DateTime, Numeric, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func # For default timestamps
from app.core.database import Base # Import Base from our database.py

# ====================================================================
# SQLAlchemy Models (corresponding to your MySQL schema)
# ====================================================================

class TypeCollaborateur(Base):
    __tablename__ = "TypeCollaborateur"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nom = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    collaborateurs = relationship("Collaborateur", back_populates="type_collaborateur_rel")
    taux_indemnites = relationship("TauxIndemnite", back_populates="type_collaborateur_rel")

class Direction(Base):
    __tablename__ = "Direction"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nom = Column(String(100), nullable=False)
    montantInitial = Column(Numeric(15, 2), default=0.00)
    montantConsomme = Column(Numeric(15, 2), default=0.00)
    mois = Column(String(10), nullable=False)
    annee = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    directeurs = relationship("Directeur", back_populates="direction_rel")
    collaborateurs = relationship("Collaborateur", back_populates="direction_rel")

class Utilisateur(Base):
    __tablename__ = "Utilisateur"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    login = Column(String(100), unique=True, nullable=False)
    motDePasse = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    directeur = relationship("Directeur", back_populates="utilisateur_rel", uselist=False)

class Directeur(Base):
    __tablename__ = "Directeur"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    utilisateur_id = Column(Integer, ForeignKey("Utilisateur.id"), nullable=False)
    direction_id = Column(Integer, ForeignKey("Direction.id"), nullable=False)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    utilisateur_rel = relationship("Utilisateur", back_populates="directeur")
    direction_rel = relationship("Direction", back_populates="directeurs")
    missions = relationship("Mission", back_populates="directeur_rel")

class TauxIndemnite(Base):
    __tablename__ = "TauxIndemnite"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    type_collaborateur_id = Column(Integer, ForeignKey("TypeCollaborateur.id"), nullable=False)
    tauxDejeuner = Column(Numeric(10, 2), default=0.00)
    tauxDinner = Column(Numeric(10, 2), default=0.00)
    tauxAccouchement = Column(Numeric(10, 2), default=0.00) # Assuming this is a typo and means accommodation
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    type_collaborateur_rel = relationship("TypeCollaborateur", back_populates="taux_indemnites")
    collaborateurs = relationship("Collaborateur", back_populates="taux_indemnite_rel")

class Collaborateur(Base):
    __tablename__ = "Collaborateur"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nom = Column(String(100), nullable=False)
    matricule = Column(String(50), unique=True, nullable=False)
    type_collaborateur_id = Column(Integer, ForeignKey("TypeCollaborateur.id"), nullable=False)
    direction_id = Column(Integer, ForeignKey("Direction.id"), nullable=False)
    taux_indemnite_id = Column(Integer, ForeignKey("TauxIndemnite.id"), nullable=False)
    disponible = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    type_collaborateur_rel = relationship("TypeCollaborateur", back_populates="collaborateurs")
    direction_rel = relationship("Direction", back_populates="collaborateurs")
    taux_indemnite_rel = relationship("TauxIndemnite", back_populates="collaborateurs")
    affectations = relationship("Affectation", back_populates="collaborateur_rel")

class Vehicule(Base):
    __tablename__ = "Vehicule"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    immatriculation = Column(String(20), unique=True, nullable=False)
    marque = Column(String(50), nullable=False)
    modele = Column(String(50))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    missions = relationship("Mission", back_populates="vehicule_rel")

class Mission(Base):
    __tablename__ = "Mission"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    objet = Column(Text, nullable=False)
    dateDebut = Column(DateTime, nullable=False)
    dateFin = Column(DateTime, nullable=False)
    moyenTransport = Column(String(50))
    trajet_predefini = Column(Text, nullable=True)
    statut = Column(String(50), default="CREEE")
    vehicule_id = Column(Integer, ForeignKey("Vehicule.id"), nullable=True)
    directeur_id = Column(Integer, ForeignKey("Directeur.id"), nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    vehicule_rel = relationship("Vehicule", back_populates="missions")
    directeur_rel = relationship("Directeur", back_populates="missions")
    # --- MODIFICATION START ---
    affectations = relationship(
        "Affectation",
        back_populates="mission_rel",
        cascade="all, delete-orphan" # This tells SQLAlchemy to delete child Affectation records
    )
    # --- MODIFICATION END ---
    trajets = relationship("Trajet", back_populates="mission_rel")
    anomalies = relationship("Anomalie", back_populates="mission_rel")

class Affectation(Base):
    __tablename__ = "Affectation"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # --- MODIFICATION START ---
    # Ensure ondelete="CASCADE" is present on the ForeignKey for database schema
    mission_id = Column(Integer, ForeignKey("Mission.id", ondelete="CASCADE"), nullable=False)
    # Adding cascade for collaborateur_id relationship just in case, though not directly related to your current error
    collaborateur_id = Column(Integer, ForeignKey("Collaborateur.id", ondelete="CASCADE"), nullable=False)
    # --- MODIFICATION END ---
    dejeuner = Column(Integer, default=0)
    dinner = Column(Integer, default=0)
    accouchement = Column(Integer, default=0) # Assuming accommodation or related, adjust if needed
    montantCalcule = Column(Numeric(15, 2), default=0.00)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    mission_rel = relationship("Mission", back_populates="affectations")
    collaborateur_rel = relationship("Collaborateur", back_populates="affectations")
    remboursements = relationship("Remboursement", back_populates="affectation_rel")

class Trajet(Base):
    __tablename__ = "Trajet"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # --- MODIFICATION START ---
    # It's good practice to add cascade for relationships where deleting the parent should delete children
    mission_id = Column(Integer, ForeignKey("Mission.id", ondelete="CASCADE"), nullable=False)
    # --- MODIFICATION END ---
    timestamp = Column(DateTime, default=func.now())
    latitude = Column(Numeric(10, 8), nullable=False)
    longitude = Column(Numeric(11, 8), nullable=False)
    vitesse = Column(Numeric(5, 2), default=0.00)
    created_at = Column(DateTime, default=func.now())

    mission_rel = relationship("Mission", back_populates="trajets")

class Anomalie(Base):
    __tablename__ = "Anomalie"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # --- MODIFICATION START ---
    # It's good practice to add cascade for relationships where deleting the parent should delete children
    mission_id = Column(Integer, ForeignKey("Mission.id", ondelete="CASCADE"), nullable=False)
    # --- MODIFICATION END ---
    type = Column(String(100), nullable=False)
    description = Column(Text)
    dateDetection = Column(DateTime, default=func.now(), nullable=False)
    created_at = Column(DateTime, default=func.now())

    mission_rel = relationship("Mission", back_populates="anomalies")

class Remboursement(Base):
    __tablename__ = "Remboursement"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # --- MODIFICATION START ---
    # It's good practice to add cascade for relationships where deleting the parent should delete children
    affectation_id = Column(Integer, ForeignKey("Affectation.id", ondelete="CASCADE"), nullable=False)
    # --- MODIFICATION END ---
    matriculeMission = Column(String(100)) # Renamed from MatriculeMission to match python naming conventions
    nom = Column(String(100), nullable=False)
    mois = Column(String(10), nullable=False)
    annee = Column(Integer, nullable=False)
    montant = Column(Numeric(15, 2), nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    affectation_rel = relationship("Affectation", back_populates="remboursements")