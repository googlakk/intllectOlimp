"""Create the single beta organization/admin. Safe to run repeatedly."""

from __future__ import annotations

import asyncio
import os
from uuid import UUID

from sqlalchemy import select

from database import AsyncSessionLocal
from models import AccountEvent, Organization, Profile
from services.supabase_auth import admin_create_auth_user, admin_delete_auth_user, normalize_login


async def bootstrap() -> None:
    login = normalize_login(os.getenv("BETA_ADMIN_LOGIN", "admin"))
    password = os.getenv("BETA_ADMIN_PASSWORD", "")
    display_name = os.getenv("BETA_ADMIN_NAME", "Администратор").strip()
    organization_name = os.getenv("BETA_ORGANIZATION_NAME", "Интеллект").strip()
    organization_slug = os.getenv("BETA_ORGANIZATION_SLUG", "intellect").strip()
    if len(password) < 12:
        raise RuntimeError("BETA_ADMIN_PASSWORD должен содержать не менее 12 символов")

    async with AsyncSessionLocal() as db:
        organization = await db.scalar(select(Organization).where(Organization.slug == organization_slug))
        if organization is None:
            organization = Organization(name=organization_name, slug=organization_slug)
            db.add(organization)
            await db.flush()
        existing = await db.scalar(select(Profile).where(
            Profile.organization_id == organization.id,
            Profile.login_name == login,
        ))
        if existing is not None:
            print(f"Beta admin already exists: {login}")
            await db.rollback()
            return

        auth_user = await admin_create_auth_user(
            login=login,
            password=password,
            display_name=display_name,
            role="admin",
        )
        auth_user_id = str(auth_user.get("id") or (auth_user.get("user") or {}).get("id") or "")
        try:
            profile = Profile(
                auth_user_id=UUID(auth_user_id),
                organization_id=organization.id,
                role="admin",
                login_name=login,
                display_name=display_name,
                status="active",
                must_change_password=False,
            )
            db.add(profile)
            await db.flush()
            db.add(AccountEvent(
                organization_id=organization.id,
                actor_profile_id=profile.id,
                target_profile_id=profile.id,
                event_type="account_created",
                metadata_json={"role": "admin", "bootstrap": True},
            ))
            await db.commit()
        except Exception:
            await db.rollback()
            if auth_user_id:
                await admin_delete_auth_user(auth_user_id)
            raise
        print(f"Beta admin created: {login}")


if __name__ == "__main__":
    asyncio.run(bootstrap())
