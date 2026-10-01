"""회원 인증·세션·HTS 메모·포트폴리오 리포트·랭킹."""

from __future__ import annotations

from fastapi import APIRouter, Body, Query, Request

from app.core.database import DbSession
from app.core.deps import MemberId, OptionalMemberId
from app.core.errors import ApiError
from app.core.parsing import clamp
from app.core.security import csrf_token
from app.models import Member
from app.services import members as member_service
from app.services.authz import can_use_kis_account, is_admin_member

from ..schemas import LoginBody, MemoBody, RegisterBody

router = APIRouter(prefix="/api/member", tags=["members"])


@router.get("/me")
def me(request: Request, member_id: OptionalMemberId, db: DbSession) -> dict:
    member = db.get(Member, member_id) if member_id else None
    if not member:
        return {"loggedIn": False, "csrfToken": csrf_token(request)}
    return {
        "loggedIn": True, "username": member.username, "asset": member.asset,
        "isAdmin": is_admin_member(member_id), "canUseKisAccount": can_use_kis_account(member_id),
        "csrfToken": csrf_token(request),
    }


@router.get("/hts-memos")
def get_hts_memos(member_id: MemberId, db: DbSession) -> dict:
    return {"memos": member_service.list_hts_memos(db, member_id)}


@router.put("/hts-memos/{symbol}")
def save_hts_memo(symbol: str, member_id: MemberId, db: DbSession, payload: MemoBody = Body(default_factory=MemoBody)) -> dict:
    symbol = symbol.strip().upper()
    if not symbol or len(symbol) > 20:
        raise ApiError(400, error="올바른 종목코드가 아닙니다.")
    memo = str(payload.memo or "").strip()
    if len(memo) > 500:
        raise ApiError(400, error="메모는 500자까지 입력할 수 있습니다.")
    return member_service.save_hts_memo(db, member_id, symbol, memo)


@router.get("/portfolio-analysis")
def portfolio_analysis(member_id: MemberId, db: DbSession) -> dict:
    member = db.get(Member, member_id)
    if not member:
        raise ApiError(401, error="UNAUTHORIZED")
    return member_service.portfolio_analysis(db, member)


@router.get("/trading-activity")
def trading_activity(member_id: MemberId, db: DbSession, days: int = Query(30)) -> dict:
    return member_service.trading_activity(db, member_id, clamp(days, 1, 365))


@router.get("/investor-rankings")
def investor_rankings(db: DbSession) -> dict:
    return member_service.investor_rankings(db)


def _login(request: Request, member: Member) -> None:
    session = request.session
    session.clear()
    session["member_id"] = member.member_id
    session.regenerate()


@router.post("/login")
def login(request: Request, db: DbSession, payload: LoginBody = Body(default_factory=LoginBody)) -> dict:
    email = (payload.email or "").strip()
    password = payload.password or ""
    if not email or not password:
        raise ApiError(400, error="이메일과 비밀번호를 입력해주세요.")
    member = member_service.authenticate(db, email, password)
    if not member:
        raise ApiError(401, error="아이디 또는 비밀번호가 맞지 않습니다.")
    _login(request, member)
    return {"username": member.username, "asset": member.asset}


@router.post("/register")
def register(request: Request, db: DbSession, payload: RegisterBody = Body(default_factory=RegisterBody)) -> dict:
    username = (payload.username or "").strip()
    email = (payload.email or "").strip()
    password = payload.password or ""
    password2 = payload.password2 or ""

    if not username:
        raise ApiError(400, field="username", error="이름을 입력해주세요.")
    if not email or "@" not in email:
        raise ApiError(400, field="email", error="올바른 이메일을 입력해주세요.")
    if not password:
        raise ApiError(400, field="password", error="비밀번호를 입력해주세요.")
    if not password2:
        raise ApiError(400, field="password2", error="비밀번호 확인을 입력해주세요.")
    if password != password2:
        raise ApiError(400, field="password2", error="패스워드가 일치하지 않습니다.")
    if member_service.find_by_email(db, email):
        raise ApiError(400, field="email", error="이미 존재하는 회원입니다.")

    member = member_service.register(db, username, email, password)
    _login(request, member)
    return {"username": username}


@router.post("/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"success": True}

