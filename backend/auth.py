import os
import re
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from database import db

router = APIRouter(prefix="/api/auth")
ALGO = "HS256"
ACCESS_MIN = 60
REFRESH_DAYS = 7
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    email: str
    password: str = Field(min_length=8, max_length=128)
    device_id: str = Field(min_length=16, max_length=128)


class LoginIn(BaseModel):
    email: str
    password: str
    device_id: str = Field(min_length=16, max_length=128)


def now():
    return datetime.now(timezone.utc)


def client_ip(request: Request) -> str:
    parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    hops = int(os.environ["TRUSTED_PROXY_HOPS"])
    if len(parts) > hops:
        return parts[-(hops + 1)]
    return parts[0] if parts else (request.client.host if request.client else "unknown")


def hash_pw(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_pw(p, h):
    return bcrypt.checkpw(p.encode(), h.encode())


def make_token(uid, sid, kind, delta):
    return jwt.encode({"sub": uid, "sid": sid, "type": kind, "exp": now() + delta}, os.environ["JWT_SECRET"], algorithm=ALGO)


def set_cookies(resp: Response, uid: str, sid: str):
    resp.set_cookie("access_token", make_token(uid, sid, "access", timedelta(minutes=ACCESS_MIN)), httponly=True,
                    secure=True, samesite="none", max_age=ACCESS_MIN * 60, path="/")
    resp.set_cookie("refresh_token", make_token(uid, sid, "refresh", timedelta(days=REFRESH_DAYS)), httponly=True,
                    secure=True, samesite="none", max_age=REFRESH_DAYS * 86400, path="/")


def public_user(u):
    return {"id": u["id"], "name": u["name"], "email": u["email"], "created_at": u["created_at"], "role": u.get("role", "user")}


async def is_banned(device_id: str, ip: str) -> bool:
    q = [{"device_id": device_id}]
    if os.environ.get("IP_BAN_ENABLED") == "true":
        q.append({"ip": ip})
    return await db.bans.find_one({"$or": q, "active": {"$ne": False}}) is not None


BAN_MSG = "Access from this device/network is permanently banned due to a multiple-account violation."


@router.post("/register")
async def register(body: RegisterIn, request: Request, response: Response):
    ip = client_ip(request)
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Please enter a valid email address.")
    if await is_banned(body.device_id, ip):
        raise HTTPException(403, BAN_MSG)
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "An account with this email already exists. Please log in.")
    owner = await db.devices.find_one({"device_id": body.device_id})
    if owner:
        ts = now().isoformat()
        await db.bans.insert_one({"id": str(uuid.uuid4()), "active": True, "device_id": body.device_id, "ip": ip, "user_id": owner["user_id"],
                                  "attempted_email": email, "reason": "multiple_accounts", "created_at": ts})
        await db.users.update_one({"id": owner["user_id"]}, {"$set": {"banned": True, "banned_at": ts, "active_session_id": None}})
        raise HTTPException(403, "Only one account is allowed per device. Creating multiple accounts is a violation: "
                                 "this device, network and the linked account have been permanently banned.")
    uid, sid = str(uuid.uuid4()), str(uuid.uuid4())
    user = {"id": uid, "name": body.name.strip(), "email": email, "password_hash": hash_pw(body.password),
            "created_at": now().isoformat(), "banned": False, "active_session_id": sid,
            "register_ip": ip, "register_device": body.device_id, "last_login_at": now().isoformat()}
    await db.users.insert_one(user)
    await db.devices.insert_one({"device_id": body.device_id, "user_id": uid, "ip": ip, "created_at": now().isoformat()})
    set_cookies(response, uid, sid)
    return public_user(user)


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response):
    ip = client_ip(request)
    email = body.email.strip().lower()
    user = await db.users.find_one({"email": email})
    is_admin = bool(user and user.get("role") == "admin")
    if not is_admin and await is_banned(body.device_id, ip):
        raise HTTPException(403, BAN_MSG)
    ident = f"{ip}:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("count", 0) >= 5 and att.get("locked_until", "") > now().isoformat():
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    if not user or not verify_pw(body.password, user["password_hash"]):
        cnt = (att or {}).get("count", 0) + 1
        await db.login_attempts.update_one({"identifier": ident}, {"$set": {
            "count": cnt, "locked_until": (now() + timedelta(minutes=15)).isoformat() if cnt >= 5 else ""}}, upsert=True)
        raise HTTPException(401, "Invalid email or password.")
    if user.get("banned"):
        raise HTTPException(403, f"This account has been banned: {user['ban_reason']}." if user.get("ban_reason") else "This account has been permanently banned for a multiple-account violation.")
    await db.login_attempts.delete_one({"identifier": ident})
    sid = str(uuid.uuid4())
    await db.users.update_one({"id": user["id"]}, {"$set": {"active_session_id": sid, "last_login_at": now().isoformat(),
                                                           "last_login_ip": ip, "last_login_device": body.device_id}})
    set_cookies(response, user["id"], sid)
    return public_user(user)


def _decode(token, kind):
    try:
        p = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    if p.get("type") != kind:
        raise HTTPException(401, "Invalid token type")
    return p


async def _session_user(p):
    user = await db.users.find_one({"id": p["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "User not found")
    if user.get("banned"):
        raise HTTPException(403, f"This account has been banned: {user['ban_reason']}." if user.get("ban_reason") else "This account has been permanently banned for a multiple-account violation.")
    if user.get("active_session_id") != p.get("sid"):
        raise HTTPException(401, "SESSION_REPLACED")
    return user


async def current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        h = request.headers.get("Authorization", "")
        token = h[7:] if h.startswith("Bearer ") else None
    if not token:
        raise HTTPException(401, "Not authenticated")
    user = await _session_user(_decode(token, "access"))
    user.pop("password_hash", None)
    return user


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    user = await _session_user(_decode(token, "refresh"))
    set_cookies(response, user["id"], user["active_session_id"])
    return public_user(user)


@router.get("/me")
async def me(request: Request):
    return public_user(await current_user(request))


@router.post("/logout")
async def logout(request: Request, response: Response):
    try:
        user = await current_user(request)
        await db.users.update_one({"id": user["id"]}, {"$set": {"active_session_id": None}})
    except HTTPException:
        pass
    response.delete_cookie("access_token", path="/", secure=True, samesite="none")
    response.delete_cookie("refresh_token", path="/", secure=True, samesite="none")
    return {"ok": True}


async def require_admin(user=Depends(current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required.")
    return user


async def seed_admin():
    email, pw = os.environ["ADMIN_EMAIL"].strip().lower(), os.environ["ADMIN_PASSWORD"]
    u = await db.users.find_one({"email": email})
    if not u:
        await db.users.insert_one({"id": str(uuid.uuid4()), "name": "Admin", "email": email, "password_hash": hash_pw(pw),
                                   "role": "admin", "created_at": now().isoformat(), "banned": False, "active_session_id": None})
    else:
        upd = {"role": "admin", "banned": False}
        if not verify_pw(pw, u["password_hash"]):
            upd["password_hash"] = hash_pw(pw)
        await db.users.update_one({"email": email}, {"$set": upd})
    async for b in db.bans.find({"id": {"$exists": False}}):
        await db.bans.update_one({"_id": b["_id"]}, {"$set": {"id": str(uuid.uuid4()), "active": True}})
