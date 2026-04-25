"""/admin namespace — module-wise user permissions.

Admin (and Owner) operations to:
    GET  /admin/modules                 — list the module catalogue
    GET  /admin/users                   — list tenant users + their modules
    GET  /admin/users/{id}/modules      — modules currently held by user
    PUT  /admin/users/{id}/modules      — replace user's module set
"""
from __future__ import annotations

from datetime import datetime

from flask import g, request
from flask_restx import Namespace, Resource, fields

from app.api.v1.security import login_required, role_required
from app.extensions import db
from app.models.permission import UserModulePermission
from app.models.user import User, UserRole
from app.services.modules import BY_CODE, CATALOGUE, default_modules_for_role

ns = Namespace("admin",
    description="Tenant administration: module-wise user permissions",
    path="/admin")


# ---- Models --------------------------------------------------------

module_out = ns.model("ModuleCatalogueItem", {
    "code": fields.String(example="sme.nra"),
    "label": fields.String(example="NRA Assessment"),
    "group": fields.String(enum=["SME journey", "Expert", "Partner",
                                  "Platform", "Admin"]),
    "description": fields.String,
})

user_with_modules = ns.model("UserWithModules", {
    "id": fields.String,
    "email": fields.String,
    "full_name": fields.String,
    "role": fields.String(enum=[r.value for r in UserRole]),
    "is_active": fields.Boolean,
    "module_codes": fields.List(fields.String,
        description="Modules currently held. OWNER/ADMIN implicitly hold all."),
    "implicit_all": fields.Boolean(
        description="True for OWNER/ADMIN — they hold every module by role"),
})

modules_input = ns.model("UserModulesInput", {
    "module_codes": fields.List(fields.String, required=True,
        example=["sme.snapshot", "sme.nra", "sme.driver_tree"]),
})


# ---- Endpoints ----------------------------------------------------

@ns.route("/modules")
class ModuleCatalogue(Resource):
    @ns.doc("list_modules", tags=["Admin"])
    @ns.response(200, "Module catalogue", [module_out])
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(403, "Caller is not OWNER or ADMIN")
    @role_required(UserRole.OWNER, UserRole.ADMIN)
    @ns.marshal_list_with(module_out)
    def get(self):
        """Return the platform's module catalogue.

        Static in v5.0; the v6 plan moves it to a DB table so modules can be
        added without a code deploy.
        """
        return [{"code": m.code, "label": m.label,
                 "group": m.group, "description": m.description}
                for m in CATALOGUE]


def _user_modules(u: User) -> list[str]:
    if u.role in (UserRole.OWNER, UserRole.ADMIN):
        return [m.code for m in CATALOGUE]
    rows = (UserModulePermission.query
            .filter_by(user_id=u.id, tenant_id=u.tenant_id).all())
    return sorted({r.module_code for r in rows})


def _serialize_user(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name,
        "role": u.role.value, "is_active": u.is_active,
        "module_codes": _user_modules(u),
        "implicit_all": u.role in (UserRole.OWNER, UserRole.ADMIN),
    }


@ns.route("/users")
class AdminUserList(Resource):
    @ns.doc("admin_list_users", tags=["Admin"])
    @ns.response(200, "Tenant users with their module sets", [user_with_modules])
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(403, "Caller is not OWNER or ADMIN")
    @role_required(UserRole.OWNER, UserRole.ADMIN)
    @ns.marshal_list_with(user_with_modules)
    def get(self):
        """List users in the caller's tenant with their module assignments."""
        rows = User.query.filter_by(tenant_id=g.tenant_id).all()
        return [_serialize_user(u) for u in rows]


@ns.route("/users/<string:user_id>/modules")
@ns.param("user_id", "UUID of the user within caller tenant")
class AdminUserModules(Resource):
    @ns.doc("admin_get_user_modules", tags=["Admin"])
    @ns.response(200, "Modules held by the user", user_with_modules)
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(403, "Caller is not OWNER or ADMIN")
    @ns.response(404, "User not found in caller tenant")
    @role_required(UserRole.OWNER, UserRole.ADMIN)
    @ns.marshal_with(user_with_modules)
    def get(self, user_id):
        """Return the module set held by a specific user."""
        u = User.query.filter_by(id=user_id, tenant_id=g.tenant_id).first_or_404()
        return _serialize_user(u)

    @ns.doc("admin_set_user_modules", tags=["Admin"])
    @ns.expect(modules_input, validate=True)
    @ns.response(200, "Module set replaced", user_with_modules)
    @ns.response(400, "Unknown module code in payload")
    @ns.response(401, "Missing or invalid bearer token")
    @ns.response(403, "Caller is not OWNER or ADMIN, or target is OWNER/ADMIN")
    @ns.response(404, "User not found in caller tenant")
    @role_required(UserRole.OWNER, UserRole.ADMIN)
    @ns.marshal_with(user_with_modules)
    def put(self, user_id):
        """Replace a user's module assignments.

        Atomic — drops every existing grant for the user and inserts the
        new set. OWNER/ADMIN cannot have their modules trimmed (they
        implicitly hold all). Each grant carries provenance: the caller's
        user_id is stamped as ``granted_by_user_id``.
        """
        u = User.query.filter_by(id=user_id, tenant_id=g.tenant_id).first_or_404()
        if u.role in (UserRole.OWNER, UserRole.ADMIN):
            ns.abort(403,
                "Cannot edit modules for OWNER/ADMIN — they implicitly hold all.")

        body = request.get_json()
        codes = list(dict.fromkeys(body["module_codes"]))   # de-dupe, preserve order
        unknown = [c for c in codes if c not in BY_CODE]
        if unknown:
            ns.abort(400, f"Unknown module codes: {unknown}")

        # Replace atomically.
        UserModulePermission.query.filter_by(
            user_id=u.id, tenant_id=u.tenant_id).delete()
        db.session.flush()

        for code in codes:
            db.session.add(UserModulePermission(
                tenant_id=u.tenant_id,
                user_id=u.id,
                module_code=code,
                granted_by_user_id=g.current_user.id,
            ))
        db.session.commit()
        return _serialize_user(u)


def grant_default_modules_for(user: User) -> int:
    """Grant the role-default module set to a freshly-created user.

    Called by /auth/register. Returns the count of grants written.
    OWNER/ADMIN don't need any rows — they hold everything implicitly.
    """
    if user.role in (UserRole.OWNER, UserRole.ADMIN):
        return 0
    codes = default_modules_for_role(user.role)
    for code in codes:
        db.session.add(UserModulePermission(
            tenant_id=user.tenant_id,
            user_id=user.id,
            module_code=code,
            granted_by_user_id=user.id,   # self-grant on signup
        ))
    return len(codes)
