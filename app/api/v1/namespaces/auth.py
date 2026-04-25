"""/auth namespace — register, login, refresh, me."""
from __future__ import annotations

from flask import g, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from flask_restx import Namespace, Resource, fields

from app.api.v1.security import login_required
from app.extensions import db
from app.models.tenant import Tenant
from app.api.v1.namespaces.admin import grant_default_modules_for
from app.models.user import User, UserRole

ns = Namespace("auth", description="Authentication and token management", path="/auth")

register_input = ns.model("RegisterInput", {
    "email": fields.String(required=True, example="owner@myfirm.com",
        description="Unique email, case-insensitive"),
    "password": fields.String(required=True, min_length=8,
        example="a-long-random-string", description="Min 8 chars; stored as bcrypt hash"),
    "full_name": fields.String(required=True, example="Anita Rao"),
    "tenant_name": fields.String(required=True, example="Rao Textiles Pvt Ltd",
        description="Becomes the root Tenant row"),
    "tenant_kind": fields.String(required=False, default="sme",
        enum=["sme", "expert", "partner"],
        description="Drives default UI skin and feature gating"),
    "role": fields.String(required=False, default="owner",
        enum=[r.value for r in UserRole],
        description="Role of the new user within the new tenant"),
})

login_input = ns.model("LoginInput", {
    "email": fields.String(required=True, example="owner@demo.nichebrains.ai"),
    "password": fields.String(required=True, example="demo1234"),
})

user_output = ns.model("User", {
    "id": fields.String(example="6f4a28f0a9b24c32af7a7d0f3ce40cf1"),
    "email": fields.String(example="owner@demo.nichebrains.ai"),
    "full_name": fields.String(example="Demo Owner"),
    "role": fields.String(enum=[r.value for r in UserRole]),
    "tenant_id": fields.String,
})

token_output = ns.model("TokenOutput", {
    "access_token": fields.String(required=True,
        description="JWT — pass as Authorization: Bearer <token>"),
    "refresh_token": fields.String(required=False,
        description="Exchange via /auth/refresh when access_token expires"),
    "user": fields.Nested(user_output, required=False, allow_null=True),
})


def _slugify(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")[:120]


def _serialize_user(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name,
            "role": u.role.value, "tenant_id": u.tenant_id}


@ns.route("/register")
class Register(Resource):
    @ns.doc("auth_register", security=[], tags=["Auth"])
    @ns.expect(register_input, validate=True)
    @ns.response(201, "Tenant and user created; tokens returned", token_output)
    @ns.response(400, "Validation error")
    @ns.response(409, "Email already registered")
    def post(self):
        """Create a new tenant and owner user."""
        body = request.get_json()
        if User.query.filter_by(email=body["email"].lower()).first():
            ns.abort(409, "Email already registered")

        tenant = Tenant(name=body["tenant_name"], slug=_slugify(body["tenant_name"]),
                        tenant_kind=body.get("tenant_kind", "sme"))
        db.session.add(tenant)
        db.session.flush()

        user = User(email=body["email"].lower(), full_name=body["full_name"],
                    role=UserRole(body.get("role", "owner")), tenant_id=tenant.id)
        user.set_password(body["password"])
        db.session.add(user)
        db.session.flush()
        grant_default_modules_for(user)
        db.session.commit()

        return {
            "access_token": create_access_token(identity=user.id),
            "refresh_token": create_refresh_token(identity=user.id),
            "user": _serialize_user(user),
        }, 201


@ns.route("/login")
class Login(Resource):
    @ns.doc("auth_login", security=[], tags=["Auth"])
    @ns.expect(login_input, validate=True)
    @ns.response(200, "Success", token_output)
    @ns.response(401, "Invalid credentials")
    @ns.response(403, "Account disabled")
    def post(self):
        """Exchange email + password for JWT access + refresh tokens."""
        body = request.get_json()
        user = User.query.filter_by(email=body["email"].lower()).first()
        if not user or not user.check_password(body["password"]):
            ns.abort(401, "Invalid credentials")
        if not user.is_active:
            ns.abort(403, "Account disabled")
        user.touch_login()
        db.session.commit()
        return {
            "access_token": create_access_token(identity=user.id),
            "refresh_token": create_refresh_token(identity=user.id),
            "user": _serialize_user(user),
        }


@ns.route("/refresh")
class Refresh(Resource):
    @ns.doc("auth_refresh", tags=["Auth"],
        description="Pass the refresh_token in Authorization: Bearer header.")
    @ns.response(200, "New access token", token_output)
    @ns.response(401, "Invalid or expired refresh token")
    @jwt_required(refresh=True)
    def post(self):
        """Mint a new access token from a valid refresh token."""
        identity = get_jwt_identity()
        return {"access_token": create_access_token(identity=identity),
                "refresh_token": None, "user": None}


@ns.route("/me")
class Me(Resource):
    @ns.doc("auth_me", tags=["Auth"])
    @ns.response(200, "Authenticated user", user_output)
    @ns.response(401, "Missing or invalid bearer token")
    @login_required
    def get(self):
        """Return the currently authenticated user."""
        return _serialize_user(g.current_user)
