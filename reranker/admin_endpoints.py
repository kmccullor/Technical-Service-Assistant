#!/usr/bin/env python3
"""Administrative management endpoints (users & roles).

Provides secure CRUD-lite operations for managing users and roles.
Only accessible to admin users (role 'admin').

Endpoints:
- GET /api/admin/users : list users with pagination & search
- PATCH /api/admin/users/{id} : update user status or role
- GET /api/admin/roles : list roles with permissions & user counts
- PATCH /api/admin/roles/{id} : update non-system role's description or permissions

Security:
- Requires a valid JWT and admin role enforced via simple role check query.
- Permission minimization: only exposes limited update fields.
- Input validation handled via Pydantic models.
"""
from typing import Any, List, Optional

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
from rbac_models import User  # type: ignore

from config import get_settings
from utils.auth_system import AuthManager, get_auth_manager, get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Pydantic models
class UserListItem(BaseModel):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    role_id: int
    role_name: str
    status: str
    verified: bool
    created_at: str
    updated_at: str


class UserListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[UserListItem]


class UserUpdateRequest(BaseModel):
    role_id: Optional[int] = Field(None, gt=0)
    status: Optional[str] = Field(None, pattern=r"^(active|inactive|suspended|pending_verification)$")


class RoleListItem(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_system: bool
    permissions: List[str]
    user_count: int


class RoleListResponse(BaseModel):
    items: List[RoleListItem]


class RoleUpdateRequest(BaseModel):
    description: Optional[str] = Field(None, max_length=255)
    permissions: Optional[List[str]] = None


# Helpers


def get_db():
    settings = get_settings()
    return psycopg2.connect(
        host=settings.db_host,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        port=settings.db_port,
        cursor_factory=RealDictCursor,
    )


async def assert_admin(user: User = Depends(get_current_user), auth: AuthManager = Depends(get_auth_manager)) -> User:
    """Ensure the current user is an admin. Raises 403 otherwise."""
    # Quick role name lookup
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT r.name FROM users u JOIN roles r ON u.role_id = r.id WHERE u.id = %s", (user.id,))
        row = cur.fetchone()
        if not row or row["name"] != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    finally:
        cur.close()
        conn.close()
    return user


# Endpoints
@router.get("/users", response_model=UserListResponse)
async def list_users(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Search by email or name"),
    current_admin: User = Depends(assert_admin),
):
    conn = get_db()
    cur = conn.cursor()
    try:
        where = []
        params: List[Any] = []
        if search:
            where.append("(u.email ILIKE %s OR COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'') ILIKE %s)")
            pattern = f"%{search}%"
            params.extend([pattern, pattern])
        where_clause = " AND ".join(where)
        if where_clause:
            where_clause = "WHERE " + where_clause
        cur.execute(f"SELECT COUNT(*) as total FROM users u {where_clause}", params)
        total = cur.fetchone()["total"] if cur.rowcount else 0
        cur.execute(
            f"""
            SELECT u.id, u.email, u.first_name, u.last_name, u.role_id, r.name as role_name,
                   u.status, u.verified, u.created_at, u.updated_at
            FROM users u
            JOIN roles r ON u.role_id = r.id
            {where_clause}
            ORDER BY u.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()
        items = []
        for row in rows:
            row_dict = dict(row)
            # Convert datetime objects to strings
            if row_dict.get("created_at"):
                row_dict["created_at"] = row_dict["created_at"].isoformat()
            if row_dict.get("updated_at"):
                row_dict["updated_at"] = row_dict["updated_at"].isoformat()
            items.append(UserListItem(**row_dict))
        return UserListResponse(total=total, limit=limit, offset=offset, items=items)
    finally:
        cur.close()
        conn.close()


@router.patch("/users/{user_id}", response_model=UserListItem)
async def update_user(
    user_id: int = Path(..., gt=0),
    payload: Optional[UserUpdateRequest] = None,
    current_admin: User = Depends(assert_admin),
):
    if not payload or (payload.role_id is None and payload.status is None):
        raise HTTPException(status_code=400, detail="No update fields provided")
    conn = get_db()
    cur = conn.cursor()
    try:
        sets = []
        params: List[Any] = []
        if payload.role_id is not None:
            # Validate role exists
            cur.execute("SELECT id FROM roles WHERE id=%s", (payload.role_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail="Invalid role_id")
            sets.append("role_id=%s")
            params.append(payload.role_id)
        if payload.status is not None:
            sets.append("status=%s")
            params.append(payload.status)
        if not sets:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        params.extend([user_id])
        cur.execute(f"UPDATE users SET {', '.join(sets)}, updated_at=NOW() WHERE id=%s RETURNING id", params)
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        conn.commit()
        # Return updated user
        cur.execute(
            """
            SELECT u.id, u.email, u.first_name, u.last_name, u.role_id, r.name as role_name,
                   u.status, u.verified, u.created_at, u.updated_at
            FROM users u JOIN roles r ON u.role_id = r.id WHERE u.id=%s
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found post-update")
        row_dict = dict(row)
        # Convert datetime objects to strings
        if row_dict.get("created_at"):
            row_dict["created_at"] = row_dict["created_at"].isoformat()
        if row_dict.get("updated_at"):
            row_dict["updated_at"] = row_dict["updated_at"].isoformat()
        return UserListItem(**row_dict)
    finally:
        cur.close()
        conn.close()


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int = Path(..., gt=0),
    current_admin: User = Depends(assert_admin),
    auth: AuthManager = Depends(get_auth_manager),
):
    """Delete a user account.

    Safeguards:
    - Cannot delete self (current admin)
    - Cannot delete the last remaining admin user
    - Returns 204 on success, 404 if not found
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        # Prevent self-deletion to avoid accidental lockout
        if user_id == current_admin.id:
            raise HTTPException(status_code=400, detail="You cannot delete your own account")

        # Check target user
        cur.execute(
            """
            SELECT u.id, r.name as role_name
            FROM users u JOIN roles r ON u.role_id = r.id
            WHERE u.id = %s
        """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        row_dict = dict(row)
        target_role = row_dict.get("role_name")
        if target_role == "admin":
            # Count other admins
            cur.execute(
                """
                SELECT COUNT(*) AS admin_count
                FROM users u JOIN roles r ON u.role_id = r.id
                WHERE r.name = 'admin' AND u.id <> %s
            """,
                (user_id,),
            )
            admin_row = cur.fetchone()
            admin_row_dict = dict(admin_row) if admin_row else {"admin_count": 0}
            admin_count = admin_row_dict.get("admin_count", 0)
            if admin_count == 0:
                raise HTTPException(status_code=400, detail="Cannot delete the last remaining admin user")

        # Perform deletion
        cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
        conn.commit()
        # Audit log (non-blocking best-effort)
        try:  # pragma: no cover - defensive
            await auth.log_audit_event(
                user_id=current_admin.id,
                action="user_deleted",
                resource_type="user",
                resource_id=str(user_id),
                details={"deleted_user_id": user_id},
            )
        except Exception:
            pass
        return Response(status_code=204)
    finally:
        cur.close()
        conn.close()


@router.get("/roles", response_model=RoleListResponse)
async def list_roles(current_admin: User = Depends(assert_admin)):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT r.id, r.name, r.description, r.is_system,
                   COALESCE(array_agg(p.name ORDER BY p.name) FILTER (WHERE p.name IS NOT NULL), '{}') as permissions,
                   (SELECT COUNT(*) FROM users u WHERE u.role_id = r.id) as user_count
            FROM roles r
            LEFT JOIN role_permissions rp ON r.id = rp.role_id
            LEFT JOIN permissions p ON rp.permission_id = p.id
            GROUP BY r.id
            ORDER BY r.name
            """
        )
        rows = cur.fetchall()
        items = []
        for row in rows:
            row_d = dict(row)
            if row_d.get("permissions") is None:
                row_d["permissions"] = []
            items.append(RoleListItem(**row_d))
        return RoleListResponse(items=items)
    finally:
        cur.close()
        conn.close()


@router.patch("/roles/{role_id}", response_model=RoleListItem)
async def update_role(
    role_id: int = Path(..., gt=0),
    payload: Optional[RoleUpdateRequest] = None,
    current_admin: User = Depends(assert_admin),
):
    if not payload or (payload.description is None and (payload.permissions is None or len(payload.permissions) == 0)):
        raise HTTPException(status_code=400, detail="No update fields provided")

    conn = get_db()
    cur = conn.cursor()
    try:
        # Fetch role
        cur.execute("SELECT id, name, description, is_system FROM roles WHERE id=%s", (role_id,))
        role_row = cur.fetchone()
        if not role_row:
            raise HTTPException(status_code=404, detail="Role not found")
        role_row_d = dict(role_row)
        if role_row_d.get("is_system"):
            raise HTTPException(status_code=400, detail="System role cannot be modified")

        if payload.description is not None:
            cur.execute("UPDATE roles SET description=%s WHERE id=%s", (payload.description, role_id))

        if payload.permissions is not None:
            # Validate permissions exist
            if payload.permissions:
                cur.execute("SELECT name FROM permissions WHERE name = ANY(%s)", (payload.permissions,))
                found = {dict(r).get("name") for r in cur.fetchall()}
                missing = set(payload.permissions) - found
                if missing:
                    raise HTTPException(status_code=400, detail=f"Unknown permissions: {', '.join(sorted(missing))}")
            # Replace assignments
            cur.execute("DELETE FROM role_permissions WHERE role_id=%s", (role_id,))
            if payload.permissions:
                cur.execute(
                    "INSERT INTO role_permissions (role_id, permission_id) SELECT %s, p.id FROM permissions p WHERE p.name = ANY(%s)",
                    (role_id, payload.permissions),
                )
        conn.commit()
        # Return updated role
        cur.execute(
            """
            SELECT r.id, r.name, r.description, r.is_system,
                   COALESCE(array_agg(p.name ORDER BY p.name) FILTER (WHERE p.name IS NOT NULL), '{}') as permissions,
                   (SELECT COUNT(*) FROM users u WHERE u.role_id = r.id) as user_count
            FROM roles r
            LEFT JOIN role_permissions rp ON r.id = rp.role_id
            LEFT JOIN permissions p ON rp.permission_id = p.id
            WHERE r.id=%s
            GROUP BY r.id
            """,
            (role_id,),
        )
        updated = cur.fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="Role not found after update")
        updated_d = dict(updated)
        return RoleListItem(**updated_d)
    finally:
        cur.close()
        conn.close()
