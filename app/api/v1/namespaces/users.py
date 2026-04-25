"""/users namespace — tenant-scoped user listing (owner + admin only)."""
from __future__ import annotations

from flask import g
from flask_restx import Namespace, Resource, fields

from app.api.v1.security import login_required, role_required
from app.models.user import User, UserRole

ns = Namespace("users", description="User administration within a tenant", path="/users")

user_output = ns.model("UserDetail", {
    "id": fields.String,
    "email": fields.String(example="owner@demo.nichebrains.ai"),
    "full_name": fields.String(example="Demo Owner"),
    "role": fields.String(enum=[r.value for r in UserRole], example="owner"),
    "tenant_id": fields.String,
    "is_active": fields.Boolean(example=True),
})


@ns.route("/")
class UserList(Resource):
    @ns.doc("list_users", tags=["Users"])
    @ns.response(200, "Users within the caller tenant", [user_output])
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(403, "Caller lacks OWNER or ADMIN role")
    @role_required(UserRole.OWNER, UserRole.ADMIN)
    @ns.marshal_list_with(user_output)
    def get(self):
        """List users within the caller tenant."""
        return [dict(id=u.id, email=u.email, full_name=u.full_name,
                     role=u.role.value, tenant_id=u.tenant_id,
                     is_active=u.is_active)
                for u in User.query.filter_by(tenant_id=g.tenant_id).all()]


@ns.route("/<string:user_id>")
@ns.param("user_id", "UUID of the user within the caller tenant")
class UserDetail(Resource):
    @ns.doc("get_user", tags=["Users"])
    @ns.response(200, "User detail", user_output)
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(404, "User not found in caller tenant")
    @login_required
    @ns.marshal_with(user_output)
    def get(self, user_id):
        """Return a single user from the caller tenant."""
        u = User.query.filter_by(id=user_id, tenant_id=g.tenant_id).first_or_404()
        return dict(id=u.id, email=u.email, full_name=u.full_name,
                    role=u.role.value, tenant_id=u.tenant_id,
                    is_active=u.is_active)
