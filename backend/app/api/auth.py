import logging

from sqlalchemy import select

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_csrf
from app.models import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.auth.email_service import (
    EmailDeliveryError,
    send_password_reset_email,
    send_verification_email,
)
from app.services.auth.email_verification_service import (
    InvalidVerificationTokenError,
    verify_email,
)
from app.services.auth.login_service import (
    AuthenticationError,
    login_user,
)
from app.services.auth.logout_service import revoke_session
from app.services.auth.password_reset_service import (
    InvalidPasswordResetTokenError,
    request_password_reset,
    reset_password,
)
from app.services.auth.registration_service import (
    EmailAlreadyRegisteredError,
    register_user,
)
from app.services.auth.resend_verification_service import (
    resend_verification_email,
)
from app.utils.security import generate_secure_token


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=f"{settings.api_prefix}/auth",
    tags=["Authentication"],
)


GENERIC_REGISTRATION_MESSAGE = (
    "If registration can proceed, verification instructions will be sent."
)

GENERIC_VERIFICATION_MESSAGE = (
    "If the account is eligible, verification instructions will be sent."
)

GENERIC_PASSWORD_RESET_MESSAGE = (
    "If an eligible account exists, password-reset instructions will be sent."
)


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        email_verified=user.email_verified_at is not None,
        created_at=user.created_at,
    )


def _set_session_cookie(
    response: Response,
    *,
    session_token: str,
    max_age: int,
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path=settings.session_cookie_path,
    )


def _set_csrf_cookie(
    response: Response,
    *,
    csrf_token: str,
) -> None:
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=settings.session_lifetime_hours * 60 * 60,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path=settings.session_cookie_path,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path=settings.session_cookie_path,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )

    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path=settings.session_cookie_path,
        secure=settings.session_cookie_secure,
        httponly=False,
        samesite=settings.session_cookie_samesite,
    )


@router.get("/csrf")
def get_csrf_token(response: Response) -> dict[str, str]:
    """
    Issue a CSRF token.

    The token is returned to the frontend for in-memory use and
    also stored in a separate cookie for double-submit validation.

    Responses containing CSRF tokens must not be cached.
    """

    csrf_token = generate_secure_token()

    _set_csrf_cookie(
        response,
        csrf_token=csrf_token,
    )

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    return {"csrf_token": csrf_token}


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf)],
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """
    Register an account and send email verification instructions.

    The public response is intentionally identical for duplicate
    and newly registered email addresses.
    """

    try:
        result = register_user(
            db,
            email=str(payload.email),
            password=payload.password,
            display_name=payload.display_name,
        )
    except EmailAlreadyRegisteredError:
        return MessageResponse(message=GENERIC_REGISTRATION_MESSAGE)

    try:
        send_verification_email(
            recipient=result.user.email,
            token=result.verification_token,
        )
    except EmailDeliveryError:
        # The account and hashed token have already been committed.
        # Never log the raw token or disclose account existence.
        logger.warning(
            "Registration verification email delivery failed"
        )

    return MessageResponse(message=GENERIC_REGISTRATION_MESSAGE)


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
def verify_email_address(
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    try:
        verify_email(
            db,
            raw_token=payload.token,
        )
    except InvalidVerificationTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification link is invalid or has expired",
        ) from None

    return MessageResponse(
        message="Your email address has been verified successfully."
    )


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf)],
)
def resend_verification(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    result = resend_verification_email(
        db,
        email=str(payload.email),
    )

    if result is not None:
        try:
            user = db.scalar(
                select(User).where(
                    User.email_normalized == str(payload.email).strip().casefold()
                )
            )

            if user is not None:
                send_verification_email(
                    recipient=user.email,
                    token=result.verification_token,
                )
        except EmailDeliveryError:
            logger.warning(
                "Verification email resend delivery failed"
            )

    return MessageResponse(message=GENERIC_VERIFICATION_MESSAGE)


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(require_csrf)],
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    try:
        result = login_user(
            db,
            email=str(payload.email),
            password=payload.password,
        )
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from None

    _set_session_cookie(
        response,
        session_token=result.session_token,
        max_age=settings.session_lifetime_hours * 60 * 60,
    )

    return AuthResponse(user=_user_response(result.user))


@router.post(
    "/logout",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
def logout(
    response: Response,
    session_token: str | None = Cookie(
        default=None,
        alias=settings.session_cookie_name,
    ),
    db: Session = Depends(get_db),
) -> MessageResponse:
    if session_token:
        try:
            revoke_session(
                db,
                raw_token=session_token,
            )
        except Exception:
            logger.exception("Session revocation failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to complete logout",
            ) from None

    _clear_auth_cookies(response)

    return MessageResponse(message="You have been logged out.")


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return _user_response(current_user)


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf)],
)
def password_reset_request(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    result = request_password_reset(
        db,
        email=str(payload.email),
    )

    if result is not None:
        try:
            user = db.scalar(
                select(User).where(
                    User.email_normalized == str(payload.email).strip().casefold()
                )
            )

            if user is not None:
                send_password_reset_email(
                    recipient=user.email,
                    token=result.reset_token,
                )
        except EmailDeliveryError:
            logger.warning(
                "Password-reset email delivery failed"
            )

    return MessageResponse(message=GENERIC_PASSWORD_RESET_MESSAGE)


@router.post(
    "/password-reset/confirm",
    response_model=MessageResponse,
    dependencies=[Depends(require_csrf)],
)
def password_reset_confirm(
    payload: PasswordResetConfirmRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> MessageResponse:
    try:
        reset_password(
            db,
            raw_token=payload.token,
            new_password=payload.new_password,
        )
    except InvalidPasswordResetTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The password-reset link is invalid or has expired",
        ) from None

    # The reset service revokes all existing sessions.
    _clear_auth_cookies(response)

    return MessageResponse(
        message="Your password has been reset. Please log in again."
    )
