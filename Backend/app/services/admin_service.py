# app/services/admin_service.py
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from fastapi import HTTPException, status
from app.models.models import Direction, Utilisateur, Directeur, Mission, Collaborateur
from app.schemas.admin_schemas import (
    DirectionCreate, DirectionUpdate, DirectionFilter,
    UtilisateurCreate, UtilisateurUpdate, UtilisateurFilter,
    DirecteurCreate, DirecteurUpdate, DirecteurFilter, DirecteurCreateWithUser
)
from app.core.security import PasswordManager

# math est importé mais non utilisé. On peut le retirer.
# import math

class AdminService:
    """Service pour les opérations CRUD admin"""

    # ====================================================================
    # Services Direction
    # ====================================================================

    @staticmethod
    def create_direction(db: Session, direction_data: DirectionCreate) -> Direction:
        """Créer une nouvelle direction"""
        # Vérifier si le nom existe déjà pour la même période
        existing = db.query(Direction).filter(
            and_(
                Direction.nom == direction_data.nom,
                Direction.mois == direction_data.mois,
                Direction.annee == direction_data.annee
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Une direction avec le nom '{direction_data.nom}' existe déjà pour le mois {direction_data.mois} de l'année {direction_data.annee}"
            )

        direction = Direction(**direction_data.model_dump())
        db.add(direction)
        db.commit()
        db.refresh(direction)
        return direction

    @staticmethod
    def get_direction(db: Session, direction_id: int) -> Optional[Direction]:
        """Récupérer une direction par ID"""
        return db.query(Direction).filter(Direction.id == direction_id).first()

    @staticmethod
    def get_directions(
        db: Session,
        skip: int = 0,
        limit: int = 10,
        filters: Optional[DirectionFilter] = None
    ) -> Tuple[List[Direction], int]:
        """Récupérer la liste des directions avec pagination et filtres"""
        query = db.query(Direction)

        if filters:
            if filters.nom:
                query = query.filter(Direction.nom.ilike(f"%{filters.nom}%"))
            if filters.annee:
                query = query.filter(Direction.annee == filters.annee)
            # --- FIX: Comparaison pour 'mois'. Le filtre mois est un INT maintenant. ---
            if filters.mois:
                # Si Direction.mois est un INT et filters.mois est un INT (comme corrigé dans les schémas),
                # alors une égalité directe est nécessaire, pas ilike.
                # Si tu veux chercher par nom de mois, il faut une logique de conversion ici
                # ou dans le schéma DirectionFilter lui-même.
                # En assumant que DirectionFilter.mois est un int (1-12) après les corrections précédentes:
                query = query.filter(Direction.mois == filters.mois)

        total = query.count()
        # --- FIX: Ajout de l'ORDER BY pour la pagination MSSQL ---
        query = query.order_by(Direction.id)
        directions = query.offset(skip).limit(limit).all()

        return directions, total

    @staticmethod
    def get_direction_with_stats(db: Session, direction_id: int) -> Optional[dict]:
        """Récupérer une direction avec ses statistiques"""
        direction = AdminService.get_direction(db, direction_id)
        if not direction:
            return None

        # Compter les statistiques
        nombre_directeurs = db.query(func.count(Directeur.id)).filter(
            Directeur.direction_id == direction_id
        ).scalar() or 0 # Add or 0 to ensure non-None value

        nombre_collaborateurs = db.query(func.count(Collaborateur.id)).filter(
            Collaborateur.direction_id == direction_id
        ).scalar() or 0 # Add or 0

        nombre_missions = db.query(func.count(Mission.id)).join(
            Directeur, Mission.directeur_id == Directeur.id
        ).filter(Directeur.direction_id == direction_id).scalar() or 0 # Add or 0

        budget_restant = direction.montantInitial - direction.montantConsomme

        # Construction explicite du dictionnaire pour éviter les problèmes de sérialisation implicite
        return {
            "id": direction.id,
            "nom": direction.nom,
            "montantInitial": direction.montantInitial,
            "montantConsomme": direction.montantConsomme,
            "mois": direction.mois, # Ceci doit être un INT, correspondant à la DB
            "annee": direction.annee,
            "created_at": direction.created_at,
            "updated_at": direction.updated_at,
            "nombre_directeurs": nombre_directeurs,
            "nombre_collaborateurs": nombre_collaborateurs,
            "nombre_missions": nombre_missions,
            "budget_restant": budget_restant
        }

    @staticmethod
    def update_direction(
        db: Session,
        direction_id: int,
        direction_data: DirectionUpdate
    ) -> Optional[Direction]:
        """Mettre à jour une direction"""
        direction = AdminService.get_direction(db, direction_id)
        if not direction:
            return None

        # Vérifier l'unicité du nom si modifié
        if direction_data.nom and direction_data.nom != direction.nom:
            mois = direction_data.mois if direction_data.mois is not None else direction.mois
            annee = direction_data.annee if direction_data.annee is not None else direction.annee

            existing = db.query(Direction).filter(
                and_(
                    Direction.nom == direction_data.nom,
                    Direction.mois == mois,
                    Direction.annee == annee,
                    Direction.id != direction_id
                )
            ).first()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Une direction avec le nom '{direction_data.nom}' existe déjà pour le mois {mois} de l'année {annee}"
                )

        # Mettre à jour les champs
        update_data = direction_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(direction, field, value)

        db.commit()
        db.refresh(direction)
        return direction

    @staticmethod
    def delete_direction(db: Session, direction_id: int) -> bool:
        """Supprimer une direction"""
        direction = AdminService.get_direction(db, direction_id)
        if not direction:
            return False

        # Vérifier s'il y a des directeurs associés
        directeurs_count = db.query(func.count(Directeur.id)).filter(
            Directeur.direction_id == direction_id
        ).scalar()

        if directeurs_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de supprimer la direction car elle a des directeurs associés"
            )

        # Vérifier s'il y a des collaborateurs associés
        collaborateurs_count = db.query(func.count(Collaborateur.id)).filter(
            Collaborateur.direction_id == direction_id
        ).scalar()

        if collaborateurs_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de supprimer la direction car elle a des collaborateurs associés"
            )

        db.delete(direction)
        db.commit()
        return True

    # ====================================================================
    # Services Utilisateur
    # ====================================================================

    @staticmethod
    def create_utilisateur(db: Session, user_data: UtilisateurCreate) -> Utilisateur:
        """Créer un nouvel utilisateur"""
        # Vérifier si le login existe déjà
        existing = db.query(Utilisateur).filter(
            Utilisateur.login == user_data.login
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Un utilisateur avec le login '{user_data.login}' existe déjà"
            )

        # Hasher le mot de passe
        hashed_password = PasswordManager.get_password_hash(user_data.motDePasse)

        user = Utilisateur(
            login=user_data.login,
            motDePasse=hashed_password,
            role=user_data.role
        )

        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_utilisateur(db: Session, user_id: int) -> Optional[Utilisateur]:
        """Récupérer un utilisateur par ID"""
        return db.query(Utilisateur).filter(Utilisateur.id == user_id).first()

    @staticmethod
    def get_utilisateurs(
        db: Session,
        skip: int = 0,
        limit: int = 10,
        filters: Optional[UtilisateurFilter] = None
    ) -> Tuple[List[Utilisateur], int]:
        """Récupérer la liste des utilisateurs avec pagination et filtres"""
        query = db.query(Utilisateur)

        if filters:
            if filters.login:
                query = query.filter(Utilisateur.login.ilike(f"%{filters.login}%"))
            if filters.role:
                query = query.filter(Utilisateur.role == filters.role)

        total = query.count()
        # --- FIX: Ajout de l'ORDER BY pour la pagination MSSQL ---
        query = query.order_by(Utilisateur.id)
        users = query.offset(skip).limit(limit).all()

        return users, total

    @staticmethod
    def update_utilisateur(
        db: Session,
        user_id: int,
        user_data: UtilisateurUpdate
    ) -> Optional[Utilisateur]:
        """Mettre à jour un utilisateur"""
        user = AdminService.get_utilisateur(db, user_id)
        if not user:
            return None

        # Vérifier l'unicité du login si modifié
        if user_data.login and user_data.login != user.login:
            existing = db.query(Utilisateur).filter(
                and_(
                    Utilisateur.login == user_data.login,
                    Utilisateur.id != user_id
                )
            ).first()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Un utilisateur avec le login '{user_data.login}' existe déjà"
                )

        # Mettre à jour les champs
        update_data = user_data.model_dump(exclude_unset=True)

        # Hasher le nouveau mot de passe si fourni
        if 'motDePasse' in update_data:
            update_data['motDePasse'] = PasswordManager.get_password_hash(update_data['motDePasse'])

        for field, value in update_data.items():
            setattr(user, field, value)

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_utilisateur(db: Session, user_id: int) -> bool:
        """Supprimer un utilisateur"""
        user = AdminService.get_utilisateur(db, user_id)
        if not user:
            return False

        # Vérifier s'il y a un directeur associé
        directeur = db.query(Directeur).filter(
            Directeur.utilisateur_id == user_id
        ).first()

        if directeur:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de supprimer l'utilisateur car il a un profil directeur associé"
            )

        db.delete(user)
        db.commit()
        return True

    # ====================================================================
    # Services Directeur
    # ====================================================================

    @staticmethod
    def create_directeur(db: Session, directeur_data: DirecteurCreate) -> Directeur:
        """Créer un nouveau directeur"""
        try:
            # Vérifier que l'utilisateur existe et n'a pas déjà un profil directeur
            user = db.query(Utilisateur).filter(
                Utilisateur.id == directeur_data.utilisateur_id
            ).first()

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Utilisateur non trouvé"
                )

            if str(user.role) != "directeur":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="L'utilisateur doit avoir le rôle DIRECTEUR pour être assigné comme directeur"
                )

            existing_directeur = db.query(Directeur).filter(
                Directeur.utilisateur_id == directeur_data.utilisateur_id
            ).first()

            if existing_directeur:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cet utilisateur a déjà un profil directeur"
                )

            # Vérifier que la direction existe
            direction = db.query(Direction).filter(
                Direction.id == directeur_data.direction_id
            ).first()

            if not direction:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Direction non trouvée"
                )

            directeur = Directeur(**directeur_data.model_dump())
            db.add(directeur)
            db.commit()
            db.refresh(directeur)
            return directeur
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur lors de la création du directeur: {str(e)}"
            )

    @staticmethod
    def create_directeur_with_user(
        db: Session,
        directeur_data: DirecteurCreateWithUser
    ) -> Tuple[Utilisateur, Directeur]:
        """Créer un utilisateur et son profil directeur en une seule opération"""
        # Créer l'utilisateur
        user_data = UtilisateurCreate(
            login=directeur_data.login,
            motDePasse=directeur_data.motDePasse,
            role="directeur"
        )

        user = AdminService.create_utilisateur(db, user_data)

        try:
            # Créer le directeur
            directeur_create_data = DirecteurCreate(
                utilisateur_id=int(user.id),
                nom=directeur_data.nom,
                prenom=directeur_data.prenom,
                direction_id=directeur_data.direction_id
            )

            directeur = AdminService.create_directeur(db, directeur_create_data)
            return user, directeur

        except Exception as e:
            # Si la création du directeur échoue, supprimer l'utilisateur
            db.delete(user)
            db.commit()
            raise e

    @staticmethod
    def get_directeur(db: Session, directeur_id: int) -> Optional[Directeur]:
        """Récupérer un directeur par ID"""
        return db.query(Directeur).options(
            joinedload(Directeur.utilisateur_rel),
            joinedload(Directeur.direction_rel)
        ).filter(Directeur.id == directeur_id).first()

    @staticmethod
    def get_directeurs(
        db: Session,
        skip: int = 0,
        limit: int = 10,
        filters: Optional[DirecteurFilter] = None
    ) -> Tuple[List[Directeur], int]:
        """Récupérer la liste des directeurs avec pagination et filtres"""
        query = db.query(Directeur).options(
            joinedload(Directeur.utilisateur_rel),
            joinedload(Directeur.direction_rel)
        )

        if filters:
            if filters.nom:
                query = query.filter(Directeur.nom.ilike(f"%{filters.nom}%"))
            if filters.prenom:
                query = query.filter(Directeur.prenom.ilike(f"%{filters.prenom}%"))
            if filters.direction_id:
                query = query.filter(Directeur.direction_id == filters.direction_id)

        total = query.count()
        # --- FIX: Ajout de l'ORDER BY pour la pagination MSSQL ---
        query = query.order_by(Directeur.id)
        directeurs = query.offset(skip).limit(limit).all()

        return directeurs, total

    @staticmethod
    def get_directeur_with_details(db: Session, directeur_id: int) -> Optional[dict]:
        """Récupérer un directeur avec ses détails complets"""
        directeur = AdminService.get_directeur(db, directeur_id)
        if not directeur:
            return None

        # Compter les missions
        nombre_missions = db.query(func.count(Mission.id)).filter(
            Mission.directeur_id == directeur_id
        ).scalar() or 0 # Add or 0

        # Assurez-vous que directeur.utilisateur_rel et directeur.direction_rel sont chargés
        return {
            "id": directeur.id,
            "utilisateur_id": directeur.utilisateur_id,
            "direction_id": directeur.direction_id,
            "nom": directeur.nom,
            "prenom": directeur.prenom,
            "created_at": directeur.created_at,
            "updated_at": directeur.updated_at,
            "utilisateur_login": directeur.utilisateur_rel.login,
            "utilisateur_role": directeur.utilisateur_rel.role,
            "direction_nom": directeur.direction_rel.nom,
            "nombre_missions": nombre_missions
        }

    @staticmethod
    def update_directeur(
        db: Session,
        directeur_id: int,
        directeur_data: DirecteurUpdate
    ) -> Optional[Directeur]:
        """Mettre à jour un directeur"""
        try:
            directeur = AdminService.get_directeur(db, directeur_id)
            if not directeur:
                return None

            # Vérifier les contraintes si nécessaire
            if directeur_data.utilisateur_id and directeur_data.utilisateur_id != directeur.utilisateur_id:
                # Vérifier que le nouvel utilisateur existe et n'a pas déjà de profil directeur
                existing_directeur = db.query(Directeur).filter(
                    and_(
                        Directeur.utilisateur_id == directeur_data.utilisateur_id,
                        Directeur.id != directeur_id
                    )
                ).first()

                if existing_directeur:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cet utilisateur a déjà un profil directeur"
                    )
                # Optional: Check if the new user has "DIRECTEUR" role if you strictly enforce this at update
                # new_user = db.query(Utilisateur).filter(Utilisateur.id == directeur_data.utilisateur_id).first()
                # if new_user and new_user.role != "DIRECTEUR":
                #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le nouvel utilisateur doit avoir le rôle DIRECTEUR")

            if directeur_data.direction_id:
                direction = db.query(Direction).filter(
                    Direction.id == directeur_data.direction_id
                ).first()

                if not direction:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Direction non trouvée"
                    )

            # Mettre à jour les champs
            update_data = directeur_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(directeur, field, value)

            db.commit()
            db.refresh(directeur)
            return directeur
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur lors de la mise à jour du directeur: {str(e)}"
            )

    @staticmethod
    def delete_directeur(db: Session, directeur_id: int) -> bool:
        """Supprimer un directeur"""
        directeur = AdminService.get_directeur(db, directeur_id)
        if not directeur:
            return False

        # Vérifier s'il y a des missions associées
        missions_count = db.query(func.count(Mission.id)).filter(
            Mission.directeur_id == directeur_id
        ).scalar()

        if missions_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de supprimer le directeur car il a des missions associées"
            )

        db.delete(directeur)
        db.commit()
        return True

    # ====================================================================
    # Services utilitaires
    # ====================================================================

    @staticmethod
    def bulk_delete_directions(db: Session, direction_ids: List[int]) -> Tuple[int, List[int], List[str]]:
        """Suppression en lot des directions"""
        deleted_count = 0
        failed_ids = []
        errors = []

        for direction_id in direction_ids:
            try:
                # Appelle la méthode de suppression individuelle qui gère les exceptions
                if AdminService.delete_direction(db, direction_id):
                    deleted_count += 1
                else:
                    failed_ids.append(direction_id)
                    errors.append(f"Direction {direction_id} non trouvée")
            except HTTPException as e:
                failed_ids.append(direction_id)
                errors.append(f"Direction {direction_id}: {e.detail}")
            except Exception as e:
                failed_ids.append(direction_id)
                errors.append(f"Direction {direction_id}: Erreur inconnue - {str(e)}")
        # db.commit() # Removed as delete_direction already commits per item
        return deleted_count, failed_ids, errors

    @staticmethod
    def get_dashboard_stats(db: Session) -> dict:
        """Récupérer les statistiques globales pour le tableau de bord admin."""
        total_directions = db.query(func.count(Direction.id)).scalar() or 0
        total_utilisateurs = db.query(func.count(Utilisateur.id)).scalar() or 0
        total_directeurs = db.query(func.count(Directeur.id)).scalar() or 0
        total_missions = db.query(func.count(Mission.id)).scalar() or 0
        total_collaborateurs = db.query(func.count(Collaborateur.id)).scalar() or 0

        # Calculer le budget total initial et consommé de toutes les directions
        total_initial_budget = db.query(func.sum(Direction.montantInitial)).scalar() or 0
        total_consumed_budget = db.query(func.sum(Direction.montantConsomme)).scalar() or 0
        total_remaining_budget = total_initial_budget - total_consumed_budget

        return {
            "total_directions": total_directions,
            "total_utilisateurs": total_utilisateurs,
            "total_directeurs": total_directeurs,
            "total_missions": total_missions,
            "total_collaborateurs": total_collaborateurs,
            "total_initial_budget": total_initial_budget,
            "total_consumed_budget": total_consumed_budget,
            "total_remaining_budget": total_remaining_budget
        }