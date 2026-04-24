"""
Auth Service - Core Authentication Business Logic

Orchestrates authentication workflows:
- User registration (admin, candidate)
- Login and token issuance
- Token refresh and validation
- Logout and token revocation

This service contains ZERO HTTP/API concerns - pure business logic.
Dependencies (repositories, JWT service, password hasher) are injected.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import exists, func, text

from app.shared.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
    InfrastructureError
)
from app.shared.auth_context import IdentityContext, UserType, AdminRole
from app.shared.observability import get_context_logger

from .contracts import (
    RegisterAdminCommand,
    RegisterCandidateCommand,
    LoginCommand,
    RefreshTokenCommand,
    LogoutCommand,
    ChangePasswordCommand,
    ValidateTokenCommand,
    AuthenticationResult,
    UserProfile,
    TokenValidationResult,
)
from .password_hasher import PasswordHasher
from .jwt_service import JWTService

logger = get_context_logger(__name__)


class AuthService:
    """
    Core authentication service.
    
    Handles user registration, login, token management,and validation.
    All repositories and services injected via constructor.
    """
    
    def __init__(
        self,
        session: Session,
        password_hasher: PasswordHasher,
        jwt_service: JWTService
    ):
        """
        Initialize auth service.
        
        Args:
            session: SQLAlchemy session
            password_hasher: Password hashing service
            jwt_service: JWT token service
        """
        self.session = session
        self.password_hasher = password_hasher
        self.jwt_service = jwt_service
        
        logger.debug(
            "AuthService initialized",
            event_type="auth_service.initialized"
        )
    
    # ============================================================================
    # REGISTRATION
    # ============================================================================
    
    def register_admin(self, command: RegisterAdminCommand) -> UserProfile:
        """
        Register a new admin user.
        
        Steps:
        1. Validate password complexity
        2. Check email uniqueness
        3. Validate organization exists and is active
        4. Hash password
        5. Create user record (user_type='admin')
        6. Create admin record
        7. Log audit event
        8. Return user profile
        
        Args:
            command: RegisterAdminCommand
            
        Returns:
            UserProfile of created admin
            
        Raises:
            ValidationError: Password complexity failure
            ConflictError: Email already exists
            NotFoundError: Organization not found or inactive
        """
        from app.auth.persistence import User, Admin
        
        logger.info(
            "Admin registration initiated",
            event_type="auth.register_admin.started",
            metadata={
                "email": command.email,
                "organization_id": command.organization_id,
                "admin_role": command.admin_role
            }
        )
        
        # 1. Validate password complexity (will raise ValidationError if fails)
        self.password_hasher.validate_complexity(command.password)
        
        # 2. Check email uniqueness
        email_lower = command.email.lower()
        if self.session.query(
            exists().where(func.lower(User.email) == email_lower)
        ).scalar():
            logger.warning(
                "Admin registration failed - email exists",
                event_type="auth.register_admin.email_exists",
                metadata={"email": command.email}
            )
            raise ConflictError(
                message="Email already registered",
                metadata={"email": command.email}
            )
        
        # 3. Validate organization (temporary direct query until admin module implemented)
        org = self.session.execute(
            text("SELECT id, status FROM organizations WHERE id = :id"),
            {"id": command.organization_id}
        ).first()
        
        if not org:
            raise NotFoundError(
                resource_type="Organization",
                resource_id=command.organization_id
            )
        
        if org[1] != 'active':
            raise ValidationError(
                message=f"Organization is {org[1]}",
                metadata={"organization_id": command.organization_id, "status": org[1]}
            )
        
        # 4. Hash password
        password_hash = self.password_hasher.hash(command.password)
        
        # 5. Create user record
        user = User(
            name=command.full_name or command.email.split('@')[0],
            email=command.email,
            password_hash=password_hash,
            user_type='admin',
            status='active',
            token_version=1
        )
        self.session.add(user)
        self.session.flush()  # Get user.id
        
        # 6. Create admin record
        admin = Admin(
            user_id=user.id,
            organization_id=command.organization_id,
            role=command.admin_role,
            status='active'
        )
        self.session.add(admin)
        self.session.flush()
        
        # 7. Log audit event
        self._log_audit_event(
            user_id=user.id,
            event_type='user_registered',
            ip_address=command.request_ip,
            user_agent=command.request_user_agent,
            metadata={
                'user_type': 'admin',
                'admin_role': command.admin_role,
                'organization_id': command.organization_id
            }
        )
        
        logger.info(
            "Admin registered successfully",
            event_type="auth.register_admin.success",
            metadata={
                "user_id": user.id,
                "admin_id": admin.id,
                "organization_id": command.organization_id
            }
        )
        
        # 8. Return profile
        return self._build_admin_profile(user, admin)
    
    def register_candidate(self, command: RegisterCandidateCommand) -> UserProfile:
        """
        Register a new candidate user.
        
        Steps:
        1. Validate password complexity
        2. Check email uniqueness
        3. Hash password
        4. Create user record (user_type='candidate')
        5. Create candidate record
        6. Log audit event
        7. Return user profile
        
        Args:
            command: RegisterCandidateCommand
            
        Returns:
            UserProfile of created candidate
            
        Raises:
            ValidationError: Password complexity failure
            ConflictError: Email already exists
        """
        from app.auth.persistence import User, Candidate
        
        logger.info(
            "Candidate registration initiated",
            event_type="auth.register_candidate.started",
            metadata={"email": command.email}
        )
        
        # 1. Validate password complexity
        self.password_hasher.validate_complexity(command.password)
        
        # 2. Check email uniqueness
        email_lower = command.email.lower()
        if self.session.query(
            exists().where(func.lower(User.email) == email_lower)
        ).scalar():
            logger.warning(
                "Candidate registration failed - email exists",
                event_type="auth.register_candidate.email_exists",
                metadata={"email": command.email}
            )
            raise ConflictError(
                message="Email already registered",
                metadata={"email": command.email}
            )
        
        # 3. Hash password
        password_hash = self.password_hasher.hash(command.password)
        
        # 4. Create user record
        user = User(
            name=command.full_name or command.email.split('@')[0],
            email=command.email,
            password_hash=password_hash,
            user_type='candidate',
            status='active',
            token_version=1
        )
        self.session.add(user)
        self.session.flush()
        
        # 5. Create candidate record
        profile_metadata = {}
        if command.full_name:
            profile_metadata['full_name'] = command.full_name
        if command.phone:
            profile_metadata['phone'] = command.phone
        if command.location:
            profile_metadata['location'] = command.location
        if command.bio:
            profile_metadata['bio'] = command.bio
        if command.experience_years is not None:
            profile_metadata['experience_years'] = command.experience_years
        if command.skills:
            profile_metadata['skills'] = command.skills
        if command.linkedin_url:
            profile_metadata['linkedin_url'] = command.linkedin_url
        if command.github_url:
            profile_metadata['github_url'] = command.github_url
        
        candidate = Candidate(
            user_id=user.id,
            plan='free',
            status='active',
            profile_metadata=profile_metadata if profile_metadata else None
        )
        self.session.add(candidate)
        self.session.flush()
        
        # 6. Log audit event
        self._log_audit_event(
            user_id=user.id,
            event_type='user_registered',
            ip_address=command.request_ip,
            user_agent=command.request_user_agent,
            metadata={'user_type': 'candidate'}
        )
        
        logger.info(
            "Candidate registered successfully",
            event_type="auth.register_candidate.success",
            metadata={
                "user_id": user.id,
                "candidate_id": candidate.id
            }
        )
        
        # 7. Return profile
        return self._build_candidate_profile(user, candidate)
    
    # ============================================================================
    # LOGIN
    # ============================================================================
    
    def login(self, command: LoginCommand) -> AuthenticationResult:
        """
        Authenticate user and issue tokens.
        
        Steps:
        1. Find user by email (case-insensitive)
        2. Verify password
        3. Check user status (active/inactive/banned)
        4. If admin: check admin and organization status
        5. Generate access token (JWT)
        6. Generate refresh token (cryptographic random)
        7. Store refresh token hash
        8. Update last_login_at
        9. Log audit event
        10. Return tokens + profile
        
        Args:
            command: LoginCommand
            
        Returns:
            AuthenticationResult with tokens and profile
            
        Raises:
            AuthenticationError: Invalid credentials, inactive user, etc.
        """
        from app.auth.persistence import User, Admin, Candidate, RefreshToken
        
        logger.info(
            "Login initiated",
            event_type="auth.login.started",
            metadata={
                "email": command.email,
                "ip_address": command.request_ip
            }
        )
        
        # 1. Find user by email
        email_lower = command.email.lower()
        user = self.session.query(User).filter(
            func.lower(User.email) == email_lower
        ).first()
        
        if not user:
            self._log_failed_login(
                email=command.email,
                reason='user_not_found',
                ip_address=command.request_ip,
                user_agent=command.request_user_agent
            )
            raise AuthenticationError(
                message="Invalid credentials",
                metadata={"reason": "user_not_found"}
            )
        
        # 2. Verify password
        if not self.password_hasher.verify(command.password, user.password_hash):
            self._log_failed_login(
                email=command.email,
                user_id=user.id,
                reason='invalid_password',
                ip_address=command.request_ip,
                user_agent=command.request_user_agent
            )
            raise AuthenticationError(
                message="Invalid credentials",
                metadata={"reason": "invalid_password"}
            )
        
        # 3. Check user status
        if user.status != 'active':
            self._log_failed_login(
                email=command.email,
                user_id=user.id,
                reason=f'user_{user.status}',
                ip_address=command.request_ip,
                user_agent=command.request_user_agent
            )
            raise AuthenticationError(
                message=f"User is {user.status}",
                metadata={"reason": f"user_{user.status}", "status": user.status}
            )
        
        admin = None
        candidate = None
        
        # 4. If admin, validate admin + org status
        if user.user_type == 'admin':
            admin = self.session.query(Admin).filter_by(user_id=user.id).first()
            
            if not admin:
                raise InfrastructureError(
                    message="Admin record not found for admin user",
                    metadata={"user_id": user.id}
                )
            
            if admin.status != 'active':
                self._log_failed_login(
                    email=command.email,
                    user_id=user.id,
                    reason=f'admin_{admin.status}',
                    ip_address=command.request_ip,
                    user_agent=command.request_user_agent
                )
                raise AuthenticationError(
                    message=f"Admin is {admin.status}",
                    metadata={"reason": f"admin_{admin.status}", "status": admin.status}
                )
            
            # Check organization status
            org = self.session.execute(
                text("SELECT status FROM organizations WHERE id = :id"),
                {"id": admin.organization_id}
            ).first()
            
            if not org:
                raise InfrastructureError(
                    message="Organization not found for admin",
                    metadata={"organization_id": admin.organization_id}
                )
            
            if org[0] == 'suspended':
                self._log_failed_login(
                    email=command.email,
                    user_id=user.id,
                    reason='organization_suspended',
                    ip_address=command.request_ip,
                    user_agent=command.request_user_agent
                )
                raise AuthenticationError(
                    message="Organization is suspended",
                    metadata={"reason": "organization_suspended"}
                )
            
            if org[0] != 'active':
                self._log_failed_login(
                    email=command.email,
                    user_id=user.id,
                    reason=f'organization_{org[0]}',
                    ip_address=command.request_ip,
                    user_agent=command.request_user_agent
                )
                raise AuthenticationError(
                    message=f"Organization is {org[0]}",
                    metadata={"reason": f"organization_{org[0]}", "status": org[0]}
                )
        
        else:  # candidate
            candidate = self.session.query(Candidate).filter_by(user_id=user.id).first()
            
            if not candidate:
                raise InfrastructureError(
                    message="Candidate record not found for candidate user",
                    metadata={"user_id": user.id}
                )
        
        # 5. Generate access token
        access_token = self.jwt_service.generate_access_token(
            user_id=user.id,
            user_type=user.user_type,
            token_version=user.token_version,
            admin_id=admin.id if admin else None,
            organization_id=admin.organization_id if admin else None,
            admin_role=admin.role if admin else None,
            candidate_id=candidate.id if candidate else None
        )
        
        # 6. Generate refresh token
        refresh_token = self.jwt_service.generate_refresh_token()
        
        # 7. Store refresh token hash
        token_hash = self.jwt_service.hash_refresh_token(refresh_token)
        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            device_info=command.device_info,
            ip_address=command.request_ip,
            expires_at=self.jwt_service.get_refresh_token_expiry()
        )
        self.session.add(refresh_token_record)
        
        # 8. Update last login
        user.last_login_at = datetime.now(timezone.utc)
        
        # 9. Log audit event
        self._log_audit_event(
            user_id=user.id,
            event_type='login_success',
            ip_address=command.request_ip,
            user_agent=command.request_user_agent,
            metadata={
                'user_type': user.user_type,
                'organization_id': admin.organization_id if admin else None
            }
        )
        
        logger.info(
            "Login successful",
            event_type="auth.login.success",
            metadata={
                "user_id": user.id,
                "user_type": user.user_type
            }
        )
        
        # 10. Return result
        if admin:
            profile = self._build_admin_profile(user, admin)
        else:
            profile = self._build_candidate_profile(user, candidate)
        
        return AuthenticationResult(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(self.jwt_service.access_token_ttl.total_seconds()),
            user_profile=profile
        )
    
    # ============================================================================
    # TOKEN REFRESH
    # ============================================================================
    
    def refresh_token(self, command: RefreshTokenCommand) -> AuthenticationResult:
        """
        Refresh access token using refresh token.
        
        Steps:
        1. Hash incoming refresh token
        2. Find token in database
        3. Check not expired
        4. Check not revoked (detect reuse)
        5. Get user
        6. Revoke old token (if rotation enabled)
        7. Generate new access token
        8. Generate new refresh token (if rotation enabled)
        9. Log audit event
        10. Return new tokens
        
        Args:
            command: RefreshTokenCommand
            
        Returns:
            AuthenticationResult with new tokens
            
        Raises:
            AuthenticationError: Invalid, expired, or revoked token
        """
        from app.auth.persistence import User, Admin, Candidate, RefreshToken
        
        logger.debug(
            "Token refresh initiated",
            event_type="auth.refresh.started",
            metadata={"ip_address": command.request_ip}
        )
        
        # 1. Hash incoming token
        token_hash = self.jwt_service.hash_refresh_token(command.refresh_token)
        
        # 2. Find token in DB
        stored_token = self.session.query(RefreshToken).filter_by(
            token_hash=token_hash
        ).first()
        
        if not stored_token:
            logger.warning(
                "Token refresh failed - token not found",
                event_type="auth.refresh.token_not_found",
                metadata={"ip_address": command.request_ip}
            )
            raise AuthenticationError(
                message="Invalid refresh token",
                metadata={"reason": "token_not_found"}
            )
        
        # 3. Check not expired
        if stored_token.expires_at < datetime.now(timezone.utc):
            logger.warning(
                "Token refresh failed - token expired",
                event_type="auth.refresh.token_expired",
                metadata={
                    "user_id": stored_token.user_id,
                    "expired_at": stored_token.expires_at.isoformat()
                }
            )
            raise AuthenticationError(
                message="Refresh token expired",
                metadata={"reason": "token_expired"}
            )
        
        # 4. Check not revoked (token reuse detection)
        if stored_token.revoked_at is not None:
            # Token reuse detected! Revoke all tokens for this user
            logger.critical(
                "Token reuse detected - revoking all user tokens",
                event_type="auth.refresh.token_reused",
                metadata={
                    "user_id": stored_token.user_id,
                    "ip_address": command.request_ip
                }
            )
            
            # Revoke all refresh tokens for this user
            self.session.query(RefreshToken).filter_by(
                user_id=stored_token.user_id
            ).filter(
                RefreshToken.revoked_at == None
            ).update({
                "revoked_at": datetime.now(timezone.utc),
                "revoked_reason": "token_reuse"
            })
            
            # Log suspicious activity
            self._log_audit_event(
                user_id=stored_token.user_id,
                event_type='suspicious_activity',
                ip_address=command.request_ip,
                metadata={'reason': 'refresh_token_reuse'}
            )
            
            raise AuthenticationError(
                message="Suspicious activity detected",
                metadata={"reason": "token_reused"}
            )
        
        # 5. Get user
        user = self.session.query(User).filter_by(id=stored_token.user_id).first()
        
        if not user or user.status != 'active':
            logger.warning(
                "Token refresh failed - user inactive",
                event_type="auth.refresh.user_inactive",
                metadata={
                    "user_id": stored_token.user_id,
                    "user_status": user.status if user else None
                }
            )
            raise AuthenticationError(
                message=f"User is {user.status if user else 'not found'}",
                metadata={"reason": "user_inactive"}
            )
        
        # Get admin or candidate record
        admin = None
        candidate = None
        if user.user_type == 'admin':
            admin = self.session.query(Admin).filter_by(user_id=user.id).first()
        else:
            candidate = self.session.query(Candidate).filter_by(user_id=user.id).first()
        
        # 6. Revoke old token (rotation)
        stored_token.revoked_at = datetime.now(timezone.utc)
        stored_token.revoked_reason = 'rotation'
        
        # 7. Generate new access token
        access_token = self.jwt_service.generate_access_token(
            user_id=user.id,
            user_type=user.user_type,
            token_version=user.token_version,
            admin_id=admin.id if admin else None,
            organization_id=admin.organization_id if admin else None,
            admin_role=admin.role if admin else None,
            candidate_id=candidate.id if candidate else None
        )
        
        # 8. Generate new refresh token
        new_refresh_token = self.jwt_service.generate_refresh_token()
        new_token_hash = self.jwt_service.hash_refresh_token(new_refresh_token)
        
        new_token_record = RefreshToken(
            user_id=user.id,
            token_hash=new_token_hash,
            device_info=stored_token.device_info,
            ip_address=command.request_ip,
            expires_at=self.jwt_service.get_refresh_token_expiry()
        )
        self.session.add(new_token_record)
        
        # 9. Log audit event
        self._log_audit_event(
            user_id=user.id,
            event_type='token_refreshed',
            ip_address=command.request_ip,
            metadata={'user_type': user.user_type}
        )
        
        logger.info(
            "Token refreshed successfully",
            event_type="auth.refresh.success",
            metadata={"user_id": user.id}
        )
        
        # 10. Return new tokens
        if admin:
            profile = self._build_admin_profile(user, admin)
        else:
            profile = self._build_candidate_profile(user, candidate)
        
        return AuthenticationResult(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=int(self.jwt_service.access_token_ttl.total_seconds()),
            user_profile=profile
        )
    
    # ============================================================================
    # LOGOUT
    # ============================================================================
    
    def logout(self, command: LogoutCommand) -> None:
        """
        Revoke refresh token (logout).
        
        Idempotent - succeeds even if token already revoked or doesn't exist.
        
        Args:
            command: LogoutCommand
        """
        from app.auth.persistence import RefreshToken
        
        logger.debug(
            "Logout initiated",
            event_type="auth.logout.started",
            metadata={"ip_address": command.request_ip}
        )
        
        # Hash token
        token_hash = self.jwt_service.hash_refresh_token(command.refresh_token)
        
        # Find token
        stored_token = self.session.query(RefreshToken).filter_by(
            token_hash=token_hash
        ).first()
        
        if not stored_token:
            # Token doesn't exist or already deleted - idempotent success
            logger.debug(
                "Logout - token not found (idempotent)",
                event_type="auth.logout.token_not_found"
            )
            return
        
        if stored_token.revoked_at is not None:
            # Already revoked - idempotent success
            logger.debug(
                "Logout - token already revoked (idempotent)",
                event_type="auth.logout.already_revoked",
                metadata={"user_id": stored_token.user_id}
            )
            return
        
        # Revoke token
        stored_token.revoked_at = datetime.now(timezone.utc)
        stored_token.revoked_reason = 'logout'
        
        # Log audit event
        self._log_audit_event(
            user_id=stored_token.user_id,
            event_type='logout',
            ip_address=command.request_ip,
            metadata={}
        )
        
        logger.info(
            "Logout successful",
            event_type="auth.logout.success",
            metadata={"user_id": stored_token.user_id}
        )

    def change_password(self, user_id: int, command: ChangePasswordCommand) -> None:
        """
        Change the authenticated user's password.

        Verifies the current password, stores the new hash, increments token_version,
        and revokes all active refresh tokens so existing sessions are invalidated.
        """
        from app.auth.persistence import User, RefreshToken

        user = self.session.query(User).filter_by(id=user_id).first()
        if not user:
            raise NotFoundError(resource_type="User", resource_id=user_id)

        if not self.password_hasher.verify(command.current_password, user.password_hash):
            logger.warning(
                "Password change failed - invalid current password",
                event_type="auth.password_change.invalid_current_password",
                metadata={"user_id": user_id},
            )
            raise AuthenticationError(
                message="Current password is incorrect",
                metadata={"error_type": "invalid_current_password"},
            )

        new_hash = self.password_hasher.hash(command.new_password)
        user.password_hash = new_hash
        user.token_version = (user.token_version or 1) + 1
        user.updated_at = datetime.now(timezone.utc)

        revoked = self.session.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        ).update(
            {
                "revoked_at": datetime.now(timezone.utc),
                "revoked_reason": "password_change",
            },
            synchronize_session="fetch",
        )

        self._log_audit_event(
            user_id=user.id,
            event_type="password_change",
            ip_address=command.request_ip,
            user_agent=command.request_user_agent,
            metadata={"revoked_tokens": revoked},
        )

        logger.info(
            "Password changed successfully",
            event_type="auth.password_change.success",
            metadata={"user_id": user.id, "revoked_tokens": revoked},
        )
    
    # ============================================================================
    # TOKEN VALIDATION
    # ============================================================================
    
    def validate_access_token(self, command: ValidateTokenCommand) -> TokenValidationResult:
        """
        Validate JWT access token and build auth context.
        
        Steps:
        1. Verify JWT signature and decode
        2. Check expiration
        3. Extract user_id
        4. Check user still active
        5. Check token_version (for forced logout)
        6. If admin: check org status
        7. Build IdentityContext
        
        Args:
            command: ValidateTokenCommand
            
        Returns:
            TokenValidationResult with auth_context if valid
        """
        from app.auth.persistence import User
        
        try:
            # 1. Verify JWT signature and decode
            claims = self.jwt_service.verify_access_token(command.access_token)
            
            # 2. Expiration already checked by JWT library
            
            # 3. Extract user_id
            user_id = claims.get('sub')
            if not user_id:
                return TokenValidationResult(
                    valid=False,
                    error='missing_subject'
                )
            
            # 4. Check user still active
            user = self.session.query(User).filter_by(id=user_id).first()
            if not user or user.status != 'active':
                return TokenValidationResult(
                    valid=False,
                    error='user_inactive'
                )
            
            # 5. Check token version
            token_version = claims.get('token_version', 0)
            if token_version < user.token_version:
                return TokenValidationResult(
                    valid=False,
                    error='token_revoked'
                )
            
            # 6. If admin, check org status
            if claims.get('type') == 'admin':
                org_id = claims.get('organization_id')
                if org_id:
                    org = self.session.execute(
                        text("SELECT status FROM organizations WHERE id = :id"),
                        {"id": org_id}
                    ).first()
                    
                    if not org:
                        return TokenValidationResult(
                            valid=False,
                            error='organization_not_found'
                        )
                    
                    if org[0] == 'suspended':
                        return TokenValidationResult(
                            valid=False,
                            error='org_suspended'
                        )
            
            # 7. Build IdentityContext
            auth_context = self._build_identity_context(claims)
            
            return TokenValidationResult(
                valid=True,
                claims=claims,
                auth_context=auth_context
            )
            
        except AuthenticationError as e:
            return TokenValidationResult(
                valid=False,
                error=e.metadata.get('error_type', 'unknown')
            )
        except Exception as e:
            logger.error(
                "Token validation error",
                event_type="auth.validate_token.error",
                metadata={"error": str(e)}
            )
            return TokenValidationResult(
                valid=False,
                error='validation_error'
            )
    
    # ============================================================================
    # CURRENT USER
    # ============================================================================

    def get_current_user(self, user_id: int) -> UserProfile:
        """
        Fetch full user profile by user_id.

        Used by the /me endpoint after JWT is validated by middleware.

        Args:
            user_id: Authenticated user's ID (from IdentityContext)

        Returns:
            UserProfile with all role-specific fields

        Raises:
            NotFoundError: If user not found or inactive
        """
        from app.auth.persistence import User, Admin, Candidate

        user = self.session.query(User).filter_by(id=user_id).first()

        if not user:
            raise NotFoundError(
                resource_type="User",
                resource_id=user_id,
            )

        if user.user_type == "admin":
            admin = self.session.query(Admin).filter_by(user_id=user.id).first()
            if not admin:
                raise InfrastructureError(
                    message="Admin record not found for admin user",
                    metadata={"user_id": user.id},
                )
            return self._build_admin_profile(user, admin)
        else:
            candidate = self.session.query(Candidate).filter_by(user_id=user.id).first()
            if not candidate:
                raise InfrastructureError(
                    message="Candidate record not found for candidate user",
                    metadata={"user_id": user.id},
                )
            return self._build_candidate_profile(user, candidate)

    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _build_admin_profile(self, user, admin) -> UserProfile:
        """Build UserProfile for admin."""
        return UserProfile(
            user_id=user.id,
            email=user.email,
            user_type='admin',
            user_status=user.status,
            admin_id=admin.id,
            organization_id=admin.organization_id,
            admin_role=admin.role,
            admin_status=admin.status,
            last_login_at=user.last_login_at,
            created_at=user.created_at
        )
    
    def _build_candidate_profile(self, user, candidate) -> UserProfile:
        """Build UserProfile for candidate."""
        profile_metadata = candidate.profile_metadata or {}
        return UserProfile(
            user_id=user.id,
            email=user.email,
            user_type='candidate',
            user_status=user.status,
            candidate_id=candidate.id,
            full_name=profile_metadata.get('full_name'),
            candidate_status=candidate.status,
            candidate_plan=candidate.plan,
            last_login_at=user.last_login_at,
            created_at=user.created_at
        )
    
    def _build_identity_context(self, claims: dict) -> IdentityContext:
        """Build IdentityContext from JWT claims."""
        user_type = UserType(claims['type'])
        admin_role = AdminRole(claims['role']) if claims.get('role') else None
        
        return IdentityContext(
            user_id=claims['sub'],
            user_type=user_type,
            organization_id=claims.get('organization_id'),
            admin_role=admin_role,
            token_version=claims.get('token_version', 1),
            issued_at=claims['iat'],
            expires_at=claims['exp']
        )
    
    def _log_audit_event(
        self,
        event_type: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> None:
        """Log audit event to auth_audit_log table."""
        from app.auth.persistence import AuthAuditLog
        
        audit_log = AuthAuditLog(
            user_id=user_id,
            event_type=event_type,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata=metadata
        )
        self.session.add(audit_log)
    
    def _log_failed_login(
        self,
        email: str,
        reason: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> None:
        """Log failed login attempt."""
        self._log_audit_event(
            user_id=user_id,
            event_type='login_failure',
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                'email': email,
                'reason': reason
            }
        )
        
        logger.warning(
            "Login failed",
            event_type="auth.login.failed",
            metadata={
                "email": email,
                "reason": reason,
                "ip_address": ip_address
            }
        )
