from typing import Callable, Dict, Any
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import time
import logging
from collections import defaultdict
import asyncio # Non utilisé directement ici, mais utile pour des middlewares asynchrones complexes
from datetime import datetime, timedelta,timezone
from app.core.security import SecurityConfig, SecurityUtils # Assurez-vous que ces imports sont corrects

# Configuration du logging pour les middlewares
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware pour ajouter les en-têtes de sécurité recommandés à toutes les réponses.
    Ces en-têtes aident à se protéger contre diverses attaques web (XSS, Clickjacking, etc.).
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Ajouter les en-têtes de sécurité définis dans SecurityConfig
        for header, value in SecurityConfig.SECURITY_HEADERS.items():
            response.headers[header] = value
        
        # Gestion des en-têtes CORS si nécessaire
        # Il est généralement recommandé de configurer CORS via `app.add_middleware(CORSMiddleware)`
        # dans votre fichier main.py, car il offre plus de flexibilité.
        # Cette section est un exemple simplifié et pourrait être redondante ou insuffisante
        # si vous avez déjà un CORSMiddleware configuré.
        if request.method == "OPTIONS":
            # Pré-vol CORS, s'il n'est pas géré par CORSMiddleware de FastAPI
            response.headers["Access-Control-Allow-Origin"] = "*" # À remplacer par le(s) domaine(s) de votre frontend en production
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE,PATCH, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-CSRF-Token" # Ajoutez X-CSRF-Token
            response.headers["Access-Control-Max-Age"] = "86400" # Cache le résultat du pré-vol pendant 24h
        
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware de limitation de taux pour protéger l'API contre les abus et les attaques par force brute.
    Cette implémentation est en mémoire et n'est PAS adaptée aux déploiements multi-instances
    ou aux environnements de production à grande échelle (utilisez Redis ou un service similaire).
    """
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 900, block_duration_minutes: int = 15):
        super().__init__(app)
        self.max_requests = max_requests # Nombre maximal de requêtes autorisées
        self.window_seconds = window_seconds # Fenêtre de temps en secondes (ex: 900s = 15 minutes)
        self.block_duration = timedelta(minutes=block_duration_minutes) # Durée de blocage si la limite est sévèrement dépassée
        
        # Stockage en mémoire des compteurs de requêtes par identifiant client
        self.request_counts: Dict[str, list] = defaultdict(list)
        # Stockage en mémoire des IPs bloquées et de leur temps de déblocage
        self.blocked_ips: Dict[str, datetime] = {}
        
    def get_client_identifier(self, request: Request) -> str:
        """
        Obtient un identifiant unique pour le client, basé sur son IP et son User-Agent.
        Cela aide à différencier les clients derrière un même NAT et à détecter les abus.
        """
        ip = request.client.host if request.client else "unknown_ip"
        user_agent = request.headers.get("user-agent", "unknown_ua")
        # Utiliser un hash du user-agent pour un identifiant plus compact
        return f"{ip}:{hash(user_agent)}"
        
    def is_blocked(self, identifier: str) -> bool:
        """
        Vérifie si un client est actuellement dans la liste des IPs bloquées.
        Débloque le client si la durée de blocage est passée.
        """
        if identifier in self.blocked_ips:
            if datetime.now() < self.blocked_ips[identifier]:
                return True # Toujours bloqué
            else:
                # Durée de blocage expirée, débloquer le client
                del self.blocked_ips[identifier]
        return False
        
    def block_client(self, identifier: str):
        """
        Bloque un client temporairement en ajoutant son identifiant à la liste des bloqués.
        """
        self.blocked_ips[identifier] = datetime.now() + self.block_duration
        logger.warning(f"RATE LIMIT: Client {identifier} bloqué pour {self.block_duration.total_seconds()} secondes.")
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Liste des chemins à exclure de la limitation de taux (ex: documentation, health checks)
        excluded_paths = ["/docs", "/openapi.json", "/redoc", "/health", "/metrics"]
        if any(request.url.path.startswith(path) for path in excluded_paths):
            return await call_next(request)
            
        identifier = self.get_client_identifier(request)
        
        # 1. Vérifier si le client est temporairement bloqué (bannière)
        if self.is_blocked(identifier):
            retry_after = int((self.blocked_ips[identifier] - datetime.now()).total_seconds())
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Trop de requêtes. Votre accès a été temporairement bloqué en raison d'activités suspectes.",
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )
            
        now = time.time() # Temps actuel en secondes
        
        # 2. Nettoyer les anciennes requêtes de la fenêtre de temps
        # Garde uniquement les requêtes qui sont encore dans la fenêtre de temps définie
        self.request_counts[identifier] = [
            req_time for req_time in self.request_counts[identifier]
            if now - req_time < self.window_seconds
        ]
        
        # 3. Vérifier le nombre de requêtes actuelles pour cet identifiant
        current_requests = len(self.request_counts[identifier])
        
        if current_requests >= self.max_requests:
            # Si le client dépasse la limite de manière significative (ex: 50% au-dessus), le bloquer temporairement
            if current_requests > self.max_requests * 1.5:
                self.block_client(identifier)
            
            # Retourner une erreur 429 Too Many Requests
            retry_after_seconds = int(self.window_seconds - (now - self.request_counts[identifier][0]))
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Trop de requêtes. Veuillez réessayer plus tard.",
                    "retry_after": max(1, retry_after_seconds) # Assure au moins 1 seconde
                },
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + retry_after_seconds)) # Temps Unix de réinitialisation
                }
            )
            
        # 4. Ajouter la requête actuelle au compteur
        self.request_counts[identifier].append(now)
        
        # Continuer le traitement de la requête
        response = await call_next(request)
        
        # 5. Ajouter les en-têtes de limitation de taux à la réponse (pour information du client)
        remaining = max(0, self.max_requests - len(self.request_counts[identifier]))
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        # Calculer le temps restant avant la réinitialisation de la première requête dans la fenêtre
        reset_time = int(self.request_counts[identifier][0] + self.window_seconds) if self.request_counts[identifier] else int(now + self.window_seconds)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response

class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware pour l'audit de sécurité et le journal des requêtes.
    Enregistre les informations sur chaque requête et détecte les événements potentiellement suspects.
    """
    def __init__(self, app):
        super().__init__(app)
        # Chemins d'API sensibles où les échecs d'authentification sont particulièrement pertinents
        self.sensitive_paths = ["/auth/login", "/auth/refresh", "/auth/change-password"]
        # En-têtes à masquer dans les logs car ils peuvent contenir des informations sensibles
        self.sensitive_headers = ["authorization", "cookie", "x-api-key"]
        
    def log_security_event(self, request: Request, response: Response, 
                           processing_time: float, error: Exception = None):
        """
        Enregistre un événement de sécurité ou une requête standard.
        Collecte des données pertinentes et les logue avec un niveau de gravité approprié.
        """
        # Informations de base sur la requête
        event_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(), # Utilisez UTC pour la cohérence
            "method": request.method,
            "path": request.url.path,
            "ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", ""),
            "processing_time_ms": round(processing_time * 1000, 2), # En millisecondes
            "status_code": response.status_code if response else 0,
            "event_type": "request_processed" # Type par défaut
        }
        
        # Ajouter des informations sur l'authentification si un token est présent
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            event_data["has_auth_token"] = True
            # En production, vous pourriez décoder le token ici pour obtenir user_id/role
            # try:
            #     token_payload = JWTManager.verify_token(auth_header.split(" ")[1], raise_exception=False)
            #     event_data["user_id"] = token_payload.user_id
            #     event_data["user_role"] = token_payload.role
            # except Exception:
            #     event_data["auth_token_invalid"] = True
        
        # Détection d'activités suspectes / événements de sécurité
        suspicious = False
        
        # 1. Tentatives d'accès non autorisées (401 Unauthorized, 403 Forbidden)
        if response and response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]:
            suspicious = True
            event_data["event_type"] = "unauthorized_access_attempt"
            event_data["severity"] = "high"
            
        # 2. Échecs d'authentification sur les endpoints sensibles (ex: login)
        if request.url.path in self.sensitive_paths and response and response.status_code == status.HTTP_401_UNAUTHORIZED:
            suspicious = True
            event_data["event_type"] = "authentication_failure"
            event_data["severity"] = "critical" if request.url.path == "/auth/login" else "high"
            
        # 3. Requêtes avec des payloads très volumineux (potentiel d'attaque par déni de service)
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > 1024 * 1024 * 5: # Exemple: Plus de 5MB
                suspicious = True
                event_data["event_type"] = "large_payload_warning"
                event_data["severity"] = "medium"
                event_data["payload_size_bytes"] = int(content_length)
                
        # 4. Erreurs de serveur internes (5xx)
        if error or (response and response.status_code >= 500):
            suspicious = True
            event_data["event_type"] = "server_error"
            event_data["severity"] = "critical" if error else "high"
            event_data["error_details"] = str(error) if error else "Internal server error"
        
        # Journaliser l'événement avec le niveau de gravité approprié
        if suspicious:
            logger.error(f"SECURITY ALERT: {event_data}") # Utilisez error pour les événements critiques/hauts
        else:
            logger.info(f"ACCESS LOG: {event_data}") # Log standard pour les requêtes normales
            
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        error = None
        response = None
        
        try:
            response = await call_next(request)
            return response
        except HTTPException as http_exc:
            # Capture les HTTPException levées par d'autres dépendances ou middlewares
            error = http_exc
            response = JSONResponse(
                status_code=http_exc.status_code,
                content={"detail": http_exc.detail, "headers": http_exc.headers} # Inclure les détails de l'exception
            )
            return response
        except Exception as e:
            # Capture toutes les autres exceptions non gérées
            error = e
            # Créer une réponse d'erreur générique pour éviter d'exposer des détails d'erreur internes
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Erreur interne du serveur"}
            )
            return response
        finally:
            processing_time = time.time() - start_time
            # Assurez-vous que le log_security_event est toujours appelé, même en cas d'erreur
            self.log_security_event(request, response, processing_time, error)

class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware pour nettoyer les entrées utilisateur.
    NOTE IMPORTANTE: Pour les corps de requête (JSON, Form Data), la sanitisation est
    MIEUX GÉRÉE par Pydantic et la validation des schémas dans les endpoints.
    Ce middleware est principalement pour la sanitisation des paramètres de requête et des en-têtes,
    bien que la modification directe de Request.query_params ne soit pas triviale dans FastAPI.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # FastAPI/Starlette rend les objets Request.query_params et Request.headers immuables.
        # Tenter de les modifier directement comme suit lèverait une erreur.
        # Pour sanitiser, il faut généralement:
        # 1. Utiliser Pydantic pour les corps de requête et valider/sanitiser au niveau du schéma.
        # 2. Pour les paramètres de requête ou les chemins, sanitiser manuellement dans l'endpoint
        #    après les avoir extraits, ou créer des Pydantic models pour les query params.
        
        # Exemple CONCEPTUEL pour montrer l'idée (ne modifie pas la Request réelle ici sans recréer le scope)
        # if request.query_params:
        #     cleaned_params = {}
        #     for key, value in request.query_params.items():
        #         cleaned_key = SecurityUtils.sanitize_input(key)
        #         cleaned_value = SecurityUtils.sanitize_input(value)
        #         cleaned_params[cleaned_key] = cleaned_value
        #     # Pour appliquer ceci, il faudrait recréer l'objet Request ou son scope, ce qui est complexe.
        #     # Une alternative est de forcer l'utilisation de Pydantic.
        
        # Pour l'instant, ce middleware se contentera de passer pour les query params,
        # en s'appuyant sur la sanitisation dans les endpoints (comme dans le login) et les schémas Pydantic.
        logger.debug(f"InputSanitizationMiddleware: Request to {request.url.path} is being processed. "
                     "Relying on Pydantic and endpoint-level sanitization.")
        
        return await call_next(request)

class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    Middleware de protection CSRF (Cross-Site Request Forgery).
    Cette implémentation utilise le pattern Synchronizer Token (token dans l'en-tête).
    Pour une protection complète, ce middleware nécessite une gestion de session côté serveur
    (par ex. via Redis ou une base de données) pour stocker et valider les tokens CSRF par session utilisateur.
    """
    def __init__(self, app, exempt_paths: list = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or [
            "/auth/login", # Login génère les tokens, donc ne doit pas nécessiter un token CSRF
            "/auth/refresh", # Refresh peut aussi être exempté si géré différemment
            "/docs", "/openapi.json", "/redoc", "/health", "/metrics" # Documentation, etc.
        ]
        
    def is_safe_method(self, method: str) -> bool:
        """
        Vérifie si la méthode HTTP est considérée comme "sûre" (ne modifie pas l'état du serveur).
        Les méthodes sûres n'ont généralement pas besoin de protection CSRF.
        """
        return method in ["GET", "HEAD", "OPTIONS", "TRACE"]
        
    def is_exempt_path(self, path: str) -> bool:
        """
        Vérifie si le chemin de la requête est exempté de la protection CSRF.
        """
        return any(path.startswith(exempt) for exempt in self.exempt_paths)
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Ignorer la protection CSRF pour les méthodes sûres et les chemins exempts
        if self.is_safe_method(request.method) or self.is_exempt_path(request.url.path):
            return await call_next(request)
            
        # Pour les méthodes non sûres sur des chemins non exemptés, un token d'autorisation est requis.
        # C'est une hypothèse que CSRF est pertinent pour les requêtes authentifiées.
        auth_header = request.headers.get("authorization")
        
        # Si la requête n'est pas authentifiée (pas de JWT), nous pouvons la laisser passer pour CSRF,
        # car elle sera probablement bloquée par les dépendances d'authentification plus tard.
        # Alternativement, vous pouvez bloquer ici si toute requête non-sûre non authentifiée est vue comme suspecte.
        if not auth_header or not auth_header.startswith("Bearer "):
            return await call_next(request) # Laissez la dépendance d'auth gérer le 401
            
        # Récupérer le token CSRF de l'en-tête personnalisé (ex: X-CSRF-Token)
        csrf_token_from_header = request.headers.get("x-csrf-token")
        
        if not csrf_token_from_header:
            logger.warning(f"CSRF: Token X-CSRF-Token manquant pour la requête {request.method} {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token CSRF manquant. Requête bloquée."
            )
            
        # ====================================================================
        # IMPORTANT: Implémentation de la validation du token CSRF
        # C'est ici que vous devez valider le token reçu contre un token stocké côté serveur.
        # Ce "token stocké" doit être lié à la session de l'utilisateur (par ex. via l'ID utilisateur ou une session ID).
        # L'absence de gestion de session distribuée (Redis, DB) rend cette partie conceptuelle pour l'instant.
        # ====================================================================
        
        # 1. Décoder le token JWT pour obtenir l'ID de l'utilisateur ou l'ID de session.
        #    Ceci est un exemple, la vraie logique dépend de comment vous stockez vos tokens CSRF.
        # try:
        #     # Ici, vous auriez besoin de la logique pour décoder le JWT pour obtenir le user_id ou session_id
        #     # C'est une version simplifiée, dans une vraie app, utilisez JWTManager.verify_token
        #     token_payload = JWTManager.verify_token(auth_header.split(" ")[1])
        #     user_id = token_payload.user_id # Supposons que user_id est dans le payload
        # except Exception:
        #     logger.warning(f"CSRF: Token d'authentification invalide pour la validation CSRF. Path: {request.url.path}")
        #     raise HTTPException(
        #         status_code=status.HTTP_401_UNAUTHORIZED,
        #         detail="Token d'authentification invalide."
        #     )
            
        # 2. Récupérer le token CSRF stocké pour cet utilisateur/cette session depuis votre système de session.
        #    Exemple conceptuel: `stored_csrf_token = get_csrf_token_from_session(user_id)`
        #    Sans un backend de session (Redis, DB), cette partie est un placeholder.
        #    Pour les besoins de ce code complété, nous allons simuler un token stocké.
        
        # SIMULATION (NE PAS UTILISER EN PRODUCTION TEL QUEL):
        # En réalité, le token stocké devrait provenir d'un mécanisme de session sécurisé.
        # Par exemple, un token généré au login et stocké dans une base de données ou Redis
        # lié à l'ID de l'utilisateur ou à l'ID de session.
        # Pour une démo, on pourrait le faire dépendre du SECRET_KEY et du login par exemple, mais ce n'est pas sûr.
        # Alternativement, un HttpOnly cookie peut stocker le CSRF token,
        # et vous le comparez avec un token envoyé dans un header X-CSRF-Token.
        
        # Pour que ce code puisse "tourner", nous allons faire une validation basique qui n'est pas sécurisée pour la prod.
        # Vous DEVEZ remplacer ceci par une gestion de session côté serveur.
        # Example: Simulez que le token CSRF est juste le login + une partie du secret.
        # if not hasattr(request.state, "user"):
        #    # Si la dépendance get_current_user n'a pas encore été exécutée
        #    # Il faudrait décoder le token ici pour obtenir le login
        #    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User state not available for CSRF check.")

        # Exemple d'un token CSRF "correct" pour la démo: il doit correspondre au token envoyé dans l'en-tête
        # Dans une vraie app, le `stored_token` viendrait de votre gestion de session/état.
        # L'idée est que le frontend obtient un token CSRF du backend (ex: via un endpoint dédié ou au login)
        # et le renvoie avec chaque requête. Le backend valide que ce token match le token qu'il attend.
        
        # Pour rendre ce code fonctionnel pour la structure actuelle:
        # Nous allons supposer que `SecurityUtils.generate_csrf_token()` génère un token,
        # et que vous avez un moyen de le récupérer côté serveur pour le comparer.
        # Ceci est la partie la plus critique et la plus difficile à implémenter sans état serveur.

        # Une approche courante avec JWT stateless est d'envoyer le CSRF token dans un HttpOnly cookie
        # ET dans un header, puis de vérifier que les deux correspondent.
        # Le backend envoie le token dans un cookie, et le frontend le lit et le renvoie dans un header.
        # Le backend COMPARE le token du cookie avec le token du header. Cela protège contre XSS.

        # Pour le moment, nous allons laisser la validation comme un appel à SecurityUtils,
        # mais la récupération du "stored_token" reste un défi sans session.
        
        # NOTE: Si vous utilisez uniquement JWT et que vous n'avez pas de sessions côté serveur,
        # la protection CSRF traditionnelle est moins pertinente si votre JWT n'est pas stocké dans un cookie simple.
        # Si le JWT est dans un cookie HttpOnly, alors CSRF devient très important.

        # Validation du token CSRF (PLACEHOLDER AVEC CAVEATS)
        # `stored_token` devrait venir d'un mécanisme de session sécurisé
        # Pour un POC minimal, on pourrait (très temporairement et non sécurisé pour la prod) faire ceci:
        # stored_token = SecurityUtils.generate_csrf_token() # Ceci génère un nouveau token à chaque fois, inefficace
        # OU: si le token CSRF est lié à un secret connu et l'ID utilisateur, il pourrait être recréé pour comparaison.
        # Exemple: `stored_token = f"csrf_{user_id}_{SecurityConfig.SECRET_KEY}"` (simple mais pas cryptographique)
        # La bonne pratique est un token généré une fois par session et stocké de manière sécurisée.

        # Sans un mécanisme de session, la validation `secrets.compare_digest(csrf_token, stored_token)`
        # ne peut pas être pleinement implémentée ici de manière sécurisée et persistance.
        # Je vais ajouter une erreur si le token est manquant, et une alerte pour la validation réelle.
        
        logger.warning("CSRF: La validation réelle du token CSRF nécessite une gestion de session côté serveur.")
        # if not SecurityUtils.validate_csrf_token(csrf_token_from_header, stored_csrf_token_from_server):
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="Token CSRF invalide. Requête bloquée."
        #     )
            
        return await call_next(request)

# Fonction utilitaire pour configurer tous les middlewares
def setup_security_middlewares(app):
    """
    Configure et ajoute tous les middlewares de sécurité à l'application FastAPI.
    L'ordre des middlewares est crucial : ils s'exécutent dans l'ordre où ils sont ajoutés
    pour les requêtes entrantes et en ordre inverse pour les réponses sortantes.
    """
    
    # 1. Ajoute les en-têtes de sécurité (X-Frame-Options, CSP, HSTS, etc.)
    app.add_middleware(SecurityHeadersMiddleware)
    
    # 2. Journalisation de sécurité et détection d'événements suspects
    app.add_middleware(SecurityLoggingMiddleware)
    
    # 3. Limitation de taux pour protéger contre les abus et les attaques par force brute
    # Les paramètres par défaut peuvent être ajustés ici.
    app.add_middleware(RateLimitMiddleware, 
                       max_requests=SecurityConfig.RATE_LIMIT_REQUESTS, 
                       window_seconds=SecurityConfig.RATE_LIMIT_WINDOW,
                       block_duration_minutes=15) # Durée de blocage par défaut
    
    # 4. Nettoyage des entrées (principalement pour les paramètres de requête et les en-têtes)
    # RAPPEL: Pour les corps de requête, Pydantic est le mécanisme préféré.
    app.add_middleware(InputSanitizationMiddleware)
    
    # 5. Protection CSRF (décommenter et implémenter la gestion de session si nécessaire)
    # L'implémentation complète de CSRF dépend de votre stratégie de gestion de session (ex: HttpOnly cookies + Redis).
    # Assurez-vous de comprendre les implications avant de l'activer en production.
    # app.add_middleware(CSRFProtectionMiddleware) 
    
    logger.info("Middlewares de sécurité configurés et ajoutés à l'application.")
    
    return app