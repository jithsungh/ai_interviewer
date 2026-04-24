"""
Auth API Routes

FastAPI router for authentication endpoints.
Delegates all business logic to AuthService (domain layer).

Endpoints:
    POST /register/admin     → Register admin user        (201)
    POST /register/candidate → Register candidate user    (201)
    POST /login              → Authenticate and get tokens (200)
    POST /refresh            → Refresh access token        (200)
    POST /logout             → Revoke refresh token        (200)
    GET  /me                 → Current user profile        (200)
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.bootstrap.dependencies import (
    get_db_session_with_commit,
    get_db_session,
    get_identity,
)
from app.shared.auth_context import IdentityContext
from app.shared.observability import get_context_logger

from app.auth.contracts import (
    # Request schemas
    AdminRegistrationRequest,
    CandidateRegistrationRequest,
    LoginRequest,
    RefreshTokenRequest,
    LogoutRequest,
    ChangePasswordRequest,
    # Response schemas
    RegistrationResponse,
    LoginResponse,
    TokenRefreshResponse,
    ChangePasswordResponse,
    CurrentUserResponse,
    UserProfileResponse,
)
from app.auth.domain import (
    AuthService,
    PasswordHasher,
    JWTService,
    RegisterAdminCommand,
    RegisterCandidateCommand,
    LoginCommand,
    RefreshTokenCommand,
    LogoutCommand,
    ChangePasswordCommand,
    UserProfile,
)

logger = get_context_logger(__name__)

router = APIRouter()


# =============================================================================
# HELPERS (private to this module)
# =============================================================================


def _build_auth_service(session: Session) -> AuthService:
    """
    Construct AuthService with injected dependencies from config.

    Reads JWT keys and password hashing settings from app config.
    This factory is called per-request to get a session-scoped service.
    """
    from app.config import settings

    sec = settings.security

    # Resolve JWT keys based on algorithm
    if sec.jwt_algorithm == "RS256":
        with open(sec.jwt_private_key_path, "r") as f:
            private_key = f.read()
        with open(sec.jwt_public_key_path, "r") as f:
            public_key = f.read()
    else:
        # HS256: symmetric key used for both signing and verification
        private_key = sec.jwt_secret_key
        public_key = sec.jwt_secret_key

    jwt_service = JWTService(
        private_key=private_key,
        public_key=public_key,
        algorithm=sec.jwt_algorithm,
        access_token_ttl_minutes=sec.access_token_expire_minutes,
        refresh_token_ttl_days=sec.refresh_token_expire_days,
    )

    password_hasher = PasswordHasher(
        cost_factor=sec.password_hash_rounds,
    )

    return AuthService(
        session=session,
        password_hasher=password_hasher,
        jwt_service=jwt_service,
    )


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting X-Forwarded-For."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # First IP in the chain is the original client
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _profile_to_user_response(profile: UserProfile) -> UserProfileResponse:
    """Map domain UserProfile to API UserProfileResponse."""
    return UserProfileResponse(
        user_id=profile.user_id,
        email=profile.email,
        user_type=profile.user_type,
        admin_id=profile.admin_id,
        organization_id=profile.organization_id,
        admin_role=profile.admin_role,
        candidate_id=profile.candidate_id,
        full_name=profile.full_name,
    )


def _profile_to_current_user_response(profile: UserProfile) -> CurrentUserResponse:
    """Map domain UserProfile to API CurrentUserResponse."""
    return CurrentUserResponse(
        user_id=profile.user_id,
        email=profile.email,
        user_type=profile.user_type,
        user_status=profile.user_status,
        admin_id=profile.admin_id,
        organization_id=profile.organization_id,
        admin_role=profile.admin_role,
        admin_status=profile.admin_status,
        candidate_id=profile.candidate_id,
        full_name=profile.full_name,
        candidate_status=profile.candidate_status,
        last_login_at=profile.last_login_at,
    )


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post(
    "/register/admin",
    status_code=201,
    response_model=RegistrationResponse,
    summary="Register admin user",
    description="Create a new admin user linked to an existing organization.",
)
def register_admin(
    request: Request,
    body: AdminRegistrationRequest,
    db: Session = Depends(get_db_session_with_commit),
) -> RegistrationResponse:
    """
    Register a new admin user.

    - Validates password complexity (Pydantic + domain layer)
    - Checks email uniqueness
    - Validates organization exists and is active
    - Cannot self-assign superadmin role
    """
    logger.info(
        "Admin registration request received",
        event_type="auth.api.register_admin",
        metadata={"email": body.email, "organization_id": body.organization_id},
    )

    auth_service = _build_auth_service(db)

    command = RegisterAdminCommand(
        email=body.email,
        password=body.password,
        organization_id=body.organization_id,
        admin_role=body.admin_role,
        full_name=body.full_name,
        request_ip=_get_client_ip(request),
        request_user_agent=request.headers.get("User-Agent"),
    )

    profile = auth_service.register_admin(command)

    return RegistrationResponse(
        user_id=profile.user_id,
        email=profile.email,
        user_type=profile.user_type,
        message="Registration successful",
    )


@router.post(
    "/register/candidate",
    status_code=201,
    response_model=RegistrationResponse,
    summary="Register candidate user",
    description="Create a new candidate user with free plan.",
)
def register_candidate(
    request: Request,
    body: CandidateRegistrationRequest,
    db: Session = Depends(get_db_session_with_commit),
) -> RegistrationResponse:
    """
    Register a new candidate user.

    - Validates password complexity
    - Checks email uniqueness
    - Creates user with free plan
    """
    logger.info(
        "Candidate registration request received",
        event_type="auth.api.register_candidate",
        metadata={"email": body.email},
    )

    auth_service = _build_auth_service(db)

    command = RegisterCandidateCommand(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        phone=body.phone,
        location=body.location,
        bio=body.bio,
        experience_years=body.experience_years,
        skills=body.skills,
        linkedin_url=body.linkedin_url,
        github_url=body.github_url,
        request_ip=_get_client_ip(request),
        request_user_agent=request.headers.get("User-Agent"),
    )

    profile = auth_service.register_candidate(command)

    return RegistrationResponse(
        user_id=profile.user_id,
        email=profile.email,
        user_type=profile.user_type,
        message="Registration successful",
    )


@router.post(
    "/login",
    status_code=200,
    response_model=LoginResponse,
    summary="User login",
    description="Authenticate with email/password and receive JWT access + refresh tokens.",
)
def login(
    request: Request,
    body: LoginRequest,
    db: Session = Depends(get_db_session_with_commit),
) -> LoginResponse:
    """
    Authenticate user and issue tokens.

    - Validates credentials
    - Checks user/admin/org status
    - Returns access token (short-lived) + refresh token (long-lived)
    """
    logger.info(
        "Login request received",
        event_type="auth.api.login",
        metadata={"email": body.email},
    )

    auth_service = _build_auth_service(db)

    command = LoginCommand(
        email=body.email,
        password=body.password,
        request_ip=_get_client_ip(request),
        request_user_agent=request.headers.get("User-Agent"),
        device_info=request.headers.get("User-Agent"),
    )

    result = auth_service.login(command)

    return LoginResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
        user=_profile_to_user_response(result.user_profile),
    )


@router.post(
    "/refresh",
    status_code=200,
    response_model=TokenRefreshResponse,
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new access + refresh token pair.",
)
def refresh_token(
    request: Request,
    body: RefreshTokenRequest,
    db: Session = Depends(get_db_session_with_commit),
) -> TokenRefreshResponse:
    """
    Refresh access token using refresh token.

    - Validates refresh token
    - Rotates refresh token (old one is revoked)
    - Detects token reuse (revokes all user tokens if detected)
    """
    logger.info(
        "Token refresh request received",
        event_type="auth.api.refresh",
    )

    auth_service = _build_auth_service(db)

    command = RefreshTokenCommand(
        refresh_token=body.refresh_token,
        request_ip=_get_client_ip(request),
    )

    result = auth_service.refresh_token(command)

    return TokenRefreshResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
    )


@router.post(
    "/logout",
    status_code=200,
    summary="User logout",
    description="Revoke a refresh token. Idempotent — succeeds even if token already revoked.",
)
def logout(
    request: Request,
    body: LogoutRequest,
    db: Session = Depends(get_db_session_with_commit),
) -> dict:
    """
    Logout by revoking refresh token.

    Idempotent: succeeds even if token doesn't exist or is already revoked.
    """
    logger.info(
        "Logout request received",
        event_type="auth.api.logout",
    )

    auth_service = _build_auth_service(db)

    command = LogoutCommand(
        refresh_token=body.refresh_token,
        request_ip=_get_client_ip(request),
    )

    auth_service.logout(command)

    return {"message": "Logout successful"}


@router.post(
    "/change-password",
    status_code=200,
    response_model=ChangePasswordResponse,
    summary="Change password",
    description="Update the authenticated user's password after verifying the current password.",
)
def change_password(
    request: Request,
    body: ChangePasswordRequest,
    identity: IdentityContext = Depends(get_identity),
    db: Session = Depends(get_db_session_with_commit),
) -> ChangePasswordResponse:
    logger.info(
        "Change password request received",
        event_type="auth.api.change_password",
        metadata={"user_id": identity.user_id},
    )

    auth_service = _build_auth_service(db)

    command = ChangePasswordCommand(
        current_password=body.current_password,
        new_password=body.new_password,
        request_ip=_get_client_ip(request),
        request_user_agent=request.headers.get("User-Agent"),
    )

    auth_service.change_password(user_id=identity.user_id, command=command)

    return ChangePasswordResponse(message="Password updated successfully")


@router.get(
    "/me",
    status_code=200,
    response_model=CurrentUserResponse,
    summary="Current user profile",
    description="Get the authenticated user's full profile. Requires valid access token.",
)
def get_me(
    identity: IdentityContext = Depends(get_identity),
    db: Session = Depends(get_db_session),
) -> CurrentUserResponse:
    """
    Get current authenticated user profile.

    Uses IdentityContext from middleware (JWT already validated).
    Fetches full profile from database.
    """
    logger.info(
        "Get current user request",
        event_type="auth.api.me",
        metadata={"user_id": identity.user_id},
    )

    auth_service = _build_auth_service(db)
    profile = auth_service.get_current_user(user_id=identity.user_id)

    return _profile_to_current_user_response(profile)
