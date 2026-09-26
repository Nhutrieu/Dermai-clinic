import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header

from .errors import DomainError


@dataclass(frozen=True)
class PharmacistIdentity:
    user_id: uuid.UUID
    role: str


async def require_pharmacist(
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> PharmacistIdentity:
    if x_user_role != "PHARMACIST":
        raise DomainError(403, "ACCESS_DENIED", "Chỉ Dược sĩ mới có quyền thực hiện thao tác này.")
    try:
        return PharmacistIdentity(user_id=uuid.UUID(x_user_id or ""), role=x_user_role)
    except ValueError as exc:
        raise DomainError(401, "UNAUTHORIZED", "Phiên đăng nhập không hợp lệ.") from exc


async def require_inventory_viewer(
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> PharmacistIdentity:
    if x_user_role not in {"PHARMACIST", "ADMIN"}:
        raise DomainError(403, "ACCESS_DENIED", "Chỉ Dược sĩ hoặc Quản trị viên mới có quyền xem kho.")
    try:
        return PharmacistIdentity(user_id=uuid.UUID(x_user_id or ""), role=x_user_role)
    except ValueError as exc:
        raise DomainError(401, "UNAUTHORIZED", "Phiên đăng nhập không hợp lệ.") from exc
