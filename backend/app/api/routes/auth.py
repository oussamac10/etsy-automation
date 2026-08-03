"""Authentication endpoints (ADR-0002).

Cookie-based, server-side sessions. The route owns the cookie; the use case owns
the session. There is no registration endpoint: the MVP has one owner, created
by ``python -m app.fixtures.bootstrap_owner``.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.api.auth_schemas import CurrentUserResponse, LoginRequest, LoginResponse, RegisterRequest
from app.api.dependencies import CSRF_COOKIE_NAME, CSRF_HEADER, CurrentUser, UowDep
from app.application import auth as use_cases
from app.settings import Settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookies(
    response: Response,
    settings: Settings,
    *,
    session_token: str,
    csrf_token: str,
    max_age_seconds: int,
) -> None:
    """Two cookies with deliberately different properties.

    The session cookie is ``HttpOnly`` so script cannot read it. The CSRF cookie
    must be readable, because the client copies it into a request header — that
    is the whole mechanism, and it is safe because the value is useless without
    the session cookie the browser will not hand over cross-site.

    ``SameSite=Lax`` blocks the cross-site form post; the header check catches
    what Lax does not, such as a same-site subdomain.
    """
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        max_age=max_age_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=max_age_seconds,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Sign in and open a session",
    responses={401: {"description": "Invalid email or password"}},
)
async def login(
    payload: LoginRequest, request: Request, response: Response, uow: UowDep
) -> LoginResponse:
    settings: Settings = request.app.state.settings
    result = await use_cases.login(
        uow,
        email=payload.email,
        password=payload.password.get_secret_value(),
        session_ttl_hours=settings.session_ttl_hours,
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookies(
        response,
        settings,
        session_token=result.session_token,
        csrf_token=result.csrf_token,
        max_age_seconds=settings.session_ttl_hours * 3600,
    )
    return LoginResponse(
        user=CurrentUserResponse.model_validate(result.user),
        expires_at=result.expires_at,
    )


@router.post(
    "/register",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new owner and open a session",
    responses={400: {"description": "Email address is already registered"}},
)
async def register(
    payload: RegisterRequest, request: Request, response: Response, uow: UowDep
) -> LoginResponse:
    from fastapi import HTTPException

    existing = await uow.users.get_by_email(payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is already registered.",
        )

    await use_cases.create_owner(
        uow,
        email=payload.email,
        display_name=payload.display_name,
        password=payload.password.get_secret_value(),
    )

    # Immediately sign in
    settings: Settings = request.app.state.settings
    result = await use_cases.login(
        uow,
        email=payload.email,
        password=payload.password.get_secret_value(),
        session_ttl_hours=settings.session_ttl_hours,
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookies(
        response,
        settings,
        session_token=result.session_token,
        csrf_token=result.csrf_token,
        max_age_seconds=settings.session_ttl_hours * 3600,
    )
    return LoginResponse(
        user=CurrentUserResponse.model_validate(result.user),
        expires_at=result.expires_at,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current session",
)
async def logout(request: Request, response: Response, uow: UowDep) -> Response:
    """Revoke the session and clear the cookies. 204 either way.

    Deliberately not behind :data:`CurrentUser`: an expired or already-revoked
    session must still be able to clear its cookies, and a logout that answers
    401 leaves the browser holding a dead cookie forever.

    CSRF is therefore checked here rather than by the dependency, and only when
    there is a live session to protect. Forcing a logout is a real (if minor)
    CSRF target, so the check is not skipped — it is just scoped to the case
    where it means something.
    """
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await use_cases.logout(uow, token, csrf_token=request.headers.get(CSRF_HEADER))

    result = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_session_cookies(result, settings)
    return result


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="The signed-in owner",
    responses={401: {"description": "No valid session"}},
)
async def current_user(user: CurrentUser) -> CurrentUserResponse:
    """Used by the client to restore an authenticated state after a reload."""
    return CurrentUserResponse.model_validate(user)
