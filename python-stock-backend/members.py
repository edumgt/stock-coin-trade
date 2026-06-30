import bcrypt
from flask import Blueprint, jsonify, request, session

from db import session_scope
from models import Member

member_bp = Blueprint("member", __name__, url_prefix="/api/member")


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


@member_bp.get("/me")
def me():
    member_id = session.get("member_id")
    if not member_id:
        return jsonify({"loggedIn": False})
    with session_scope() as db:
        member = db.get(Member, member_id)
        if not member:
            return jsonify({"loggedIn": False})
        return jsonify({"loggedIn": True, "username": member.username, "asset": member.asset})


@member_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify({"error": "이메일과 비밀번호를 입력해주세요."}), 400

    with session_scope() as db:
        member = db.query(Member).filter(Member.email == email).first()
        if not member or not _check_password(password, member.password):
            return jsonify({"error": "아이디 또는 비밀번호가 맞지 않습니다."}), 401

        session.clear()
        session["member_id"] = member.member_id
        session.permanent = True
        return jsonify({"username": member.username, "asset": member.asset})


@member_bp.post("/register")
def register():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    password2 = body.get("password2") or ""

    if not username:
        return jsonify({"field": "username", "error": "이름을 입력해주세요."}), 400
    if not email or "@" not in email:
        return jsonify({"field": "email", "error": "올바른 이메일을 입력해주세요."}), 400
    if not password:
        return jsonify({"field": "password", "error": "비밀번호를 입력해주세요."}), 400
    if not password2:
        return jsonify({"field": "password2", "error": "비밀번호 확인을 입력해주세요."}), 400
    if password != password2:
        return jsonify({"field": "password2", "error": "패스워드가 일치하지 않습니다."}), 400

    with session_scope() as db:
        if db.query(Member).filter(Member.email == email).first():
            return jsonify({"field": "email", "error": "이미 존재하는 회원입니다."}), 400

        member = Member(username=username, email=email, password=_hash_password(password), asset=10_000_000)
        db.add(member)
        db.flush()
        session.clear()
        session["member_id"] = member.member_id
        session.permanent = True
        return jsonify({"username": username})


@member_bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"success": True})
