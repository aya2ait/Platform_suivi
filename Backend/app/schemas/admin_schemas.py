from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator # Assurez-vous que field_validator est importé
from decimal import Decimal

# ====================================================================
# Schémas pour Direction CRUD
# ====================================================================

class DirectionBase(BaseModel):
    nom: str = Field(..., min_length=1, max_length=100, description="Nom de la direction")
    montantInitial: Decimal = Field(default=Decimal("0.00"), ge=0, description="Montant initial du budget")
    montantConsomme: Decimal = Field(default=Decimal("0.00"), ge=0, description="Montant consommé")
    mois: int = Field(..., ge=1, le=12, description="Mois (format numérique: 1-12)") # Type int, range 1-12
    annee: int = Field(..., ge=2020, le=2030, description="Année")

    # Le validateur 'mois' a été supprimé ici car le type int et les contraintes ge/le suffisent.
    # Si 'mois' vient d'une source externe qui peut être une chaîne de caractères,
    # une conversion devrait se faire avant d'atteindre ce modèle ou via un validateur 'before' si nécessaire.

    @field_validator('montantConsomme')
    def validate_montant_consomme(cls, v, info):
        # Utilisation de v is not None et info.data.get pour éviter les erreurs si les champs sont None ou absents
        if 'montantInitial' in info.data and v is not None and info.data['montantInitial'] is not None:
            if v > info.data['montantInitial']:
                raise ValueError('Le montant consommé ne peut pas dépasser le montant initial')
        return v

class DirectionCreate(DirectionBase):
    pass

class DirectionUpdate(BaseModel):
    nom: Optional[str] = Field(None, min_length=1, max_length=100)
    montantInitial: Optional[Decimal] = Field(None, ge=0)
    montantConsomme: Optional[Decimal] = Field(None, ge=0)
    # Reste Optional[int] car le validateur 'before' gère la conversion
    mois: Optional[int] = Field(None, ge=1, le=12)
    annee: Optional[int] = Field(None, ge=2020, le=2030)

    # Ce validateur est conservé car il gère la conversion des noms de mois/chaînes numériques en int.
    # Il est appelé 'before' la validation normale de Pydantic.
    @field_validator('mois', mode='before')
    def convert_month_name_to_int(cls, v):
        if v is None:
            return None # Permet aux champs optionnels de rester None
        if isinstance(v, str):
            month_map = {
                'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
                'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12
            }
            v_lower = v.lower()
            if v_lower in month_map:
                return month_map[v_lower]
            # Gère les chaînes numériques comme "07" ou "7"
            if v.isdigit():
                num_v = int(v)
                if 1 <= num_v <= 12:
                    return num_v
            raise ValueError("Mois invalide. Doit être un nom de mois, un nombre entre 1 et 12, ou une chaîne numérique.")
        # Si c'est déjà un int, le laisser passer pour la validation Pydantic normale (ge/le)
        if isinstance(v, int):
            return v
        raise ValueError("Type de mois invalide. Doit être un nombre entier ou une chaîne de caractères valide.")


    @field_validator('montantConsomme')
    def validate_montant_consomme_update(cls, v, info):
        # Utilisation de v is not None et info.data.get pour éviter les erreurs si les champs sont None ou absents
        if 'montantInitial' in info.data and v is not None and info.data['montantInitial'] is not None:
            if v > info.data['montantInitial']:
                raise ValueError('Le montant consommé ne peut pas dépasser le montant initial')
        return v


class DirectionResponse(DirectionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DirectionWithStats(DirectionResponse):
    """Direction avec statistiques"""
    nombre_directeurs: int = 0
    nombre_collaborateurs: int = 0
    nombre_missions: int = 0
    budget_restant: Decimal = Decimal("0.00")

# ====================================================================
# Schémas pour Utilisateur CRUD
# ====================================================================

class UtilisateurBase(BaseModel):
    login: str = Field(..., min_length=3, max_length=100, description="Login utilisateur")
    role: str = Field(..., description="Rôle de l'utilisateur")

    @field_validator('role')
    def validate_role(cls, v):
        roles_valides = ['admin', 'directeur', 'controleur','collaborateur']
        if v not in roles_valides:
            raise ValueError(f'Rôle doit être un de: {roles_valides}')
        return v

class UtilisateurCreate(UtilisateurBase):
    motDePasse: str = Field(..., min_length=8, description="Mot de passe (min 8 caractères)")

    @field_validator('motDePasse')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Le mot de passe doit contenir au moins 8 caractères')
        # Optionnel: ajouter d'autres règles de complexité
        return v

class UtilisateurUpdate(BaseModel):
    login: Optional[str] = Field(None, min_length=3, max_length=100)
    motDePasse: Optional[str] = Field(None, min_length=8)
    role: Optional[str] = None

    @field_validator('role')
    def validate_role(cls, v):
        if v is not None:
            roles_valides = ['admin', 'directeur', 'controleur']
            if v not in roles_valides:
                raise ValueError(f'Rôle doit être un de: {roles_valides}')
        return v

    @field_validator('motDePasse')
    def validate_password(cls, v):
        if v is not None and len(v) < 8:
            raise ValueError('Le mot de passe doit contenir au moins 8 caractères')
        return v

class UtilisateurResponse(UtilisateurBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ChangePasswordRequest(BaseModel):
    ancien_mot_de_passe: str = Field(..., description="Ancien mot de passe")
    nouveau_mot_de_passe: str = Field(..., min_length=8, description="Nouveau mot de passe")

    @field_validator('nouveau_mot_de_passe')
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('Le nouveau mot de passe doit contenir au moins 8 caractères')
        return v

# ====================================================================
# Schémas pour Directeur CRUD
# ====================================================================

class DirecteurBase(BaseModel):
    nom: str = Field(..., min_length=1, max_length=100, description="Nom du directeur")
    prenom: str = Field(..., min_length=1, max_length=100, description="Prénom du directeur")
    direction_id: int = Field(..., gt=0, description="ID de la direction")

class DirecteurCreate(DirecteurBase):
    utilisateur_id: int = Field(..., gt=0, description="ID de l'utilisateur associé")

class DirecteurUpdate(BaseModel):
    nom: Optional[str] = Field(None, min_length=1, max_length=100)
    prenom: Optional[str] = Field(None, min_length=1, max_length=100)
    direction_id: Optional[int] = Field(None, gt=0)
    utilisateur_id: Optional[int] = Field(None, gt=0)

class DirecteurResponse(DirecteurBase):
    id: int
    utilisateur_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DirecteurWithDetails(DirecteurResponse):
    """Directeur avec détails de l'utilisateur et de la direction"""
    utilisateur_login: str
    utilisateur_role: str
    direction_nom: str
    nombre_missions: int = 0

class DirecteurCreateWithUser(BaseModel):
    """Schéma pour créer un directeur avec son utilisateur en une seule opération"""
    # Informations utilisateur
    login: str = Field(..., min_length=3, max_length=100)
    motDePasse: str = Field(..., min_length=8)

    # Informations directeur
    nom: str = Field(..., min_length=1, max_length=100)
    prenom: str = Field(..., min_length=1, max_length=100)
    direction_id: int = Field(..., gt=0)

    @field_validator('motDePasse')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Le mot de passe doit contenir au moins 8 caractères')
        return v

# ====================================================================
# Schémas pour les réponses de liste et pagination
# ====================================================================

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Numéro de page")
    size: int = Field(default=10, ge=1, le=100, description="Nombre d'éléments par page")

class PaginatedResponse(BaseModel):
    items: List[BaseModel] # Note: Vous pourriez vouloir rendre ce type plus spécifique selon le contexte
    total: int
    page: int
    size: int
    pages: int

class DirectionListResponse(BaseModel):
    items: List[DirectionWithStats]
    total: int
    page: int
    size: int
    pages: int

class UtilisateurListResponse(BaseModel):
    items: List[UtilisateurResponse]
    total: int
    page: int
    size: int
    pages: int

class DirecteurListResponse(BaseModel):
    items: List[DirecteurWithDetails]
    total: int
    page: int
    size: int
    pages: int

# ====================================================================
# Schémas pour les filtres de recherche
# ====================================================================

class DirectionFilter(BaseModel):
    nom: Optional[str] = None
    annee: Optional[int] = None
    # --- CORRECTION ICI ---
    # `mois` doit être un int pour correspondre à la base de données et éviter les erreurs de type
    mois: Optional[int] = Field(None, ge=1, le=12)


class UtilisateurFilter(BaseModel):
    login: Optional[str] = None
    role: Optional[str] = None

class DirecteurFilter(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    direction_id: Optional[int] = None

# ====================================================================
# Schémas pour les réponses d'erreur et de succès
# ====================================================================

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None

class SuccessResponse(BaseModel):
    message: str
    data: Optional[dict] = None

class BulkDeleteRequest(BaseModel):
    ids: List[int] = Field(..., min_length=1, description="Liste des IDs à supprimer")

class BulkDeleteResponse(BaseModel):
    deleted_count: int
    failed_ids: List[int] = []
    errors: List[str] = []