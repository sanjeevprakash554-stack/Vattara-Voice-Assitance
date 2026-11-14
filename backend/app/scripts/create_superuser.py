"""CLI command to securely provision or reset a Super Admin account.

Usage:
    python -m app.scripts.create_superuser --email superadmin@vattara.com --password "StrongPassword!2026"
    or interactively:
    python -m app.scripts.create_superuser
"""

import argparse
import getpass
import sys
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.logging import get_logger
from app.core.security import get_password_hash
from app.database.connection import SessionLocal
from app.models.business import Business
from app.models.user import User

logger = get_logger(__name__)


def validate_password_strength(password: str) -> None:
    """Ensure password meets production security criteria."""
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters in length.")
    if password in {"SuperAdmin@123", "Admin@123", "password123", "admin123"}:
        raise ValueError("Cannot use default or widely known development passwords.")


def _do_provision(
    db: Session,
    email: str,
    password: str,
    full_name: str,
    business_id: str | None,
) -> User:
    if not business_id:
        first_biz = db.scalar(select(Business).limit(1))
        if not first_biz:
            first_biz = Business(
                id="vattara-platform-admin",
                name="Vattara Voice AI Platform",
                vertical="platform",
                phone="+91 44 2828 9000",
                email="admin@vattara.com",
                is_active=True,
            )
            db.add(first_biz)
            db.flush()
        business_id = first_biz.id

    user = db.scalar(select(User).where(User.email == email))
    if user:
        print(f"Existing user found for '{email}'. Updating to Super Admin role and resetting credentials...")
        user.hashed_password = get_password_hash(password)
        user.role = "super_admin"
        user.is_active = True
        user.full_name = full_name
    else:
        print(f"Provisioning new Super Admin account for '{email}'...")
        user = User(
            business_id=business_id,
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            role="super_admin",
            is_active=True,
        )
        db.add(user)

    db.commit()
    print(f"Super Admin '{email}' successfully provisioned with role 'super_admin'.")
    return user


def create_or_update_superuser(
    email: str,
    password: str,
    full_name: str = "Platform Super Admin",
    business_id: str | None = None,
    db: Session | None = None,
) -> User:
    """Provision new superadmin or reset existing account credentials."""
    validate_password_strength(password)

    if db is not None:
        return _do_provision(db, email, password, full_name, business_id)

    with SessionLocal() as session:
        return _do_provision(session, email, password, full_name, business_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Vattara Voice Assistance - Super Admin Bootstrap CLI")
    parser.add_argument("--email", type=str, default=None, help="Super Admin email address")
    parser.add_argument("--password", type=str, default=None, help="Super Admin password (min 12 chars)")
    parser.add_argument("--name", type=str, default="Platform Super Admin", help="Full name")
    parser.add_argument("--business-id", type=str, default=None, help="Optional Business ID")

    args = parser.parse_args()

    email = args.email
    if not email:
        email = input("Enter Super Admin Email: ").strip()

    password = args.password
    if not password:
        password = getpass.getpass("Enter Super Admin Password (min 12 characters): ").strip()
        confirm = getpass.getpass("Confirm Super Admin Password: ").strip()
        if password != confirm:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    try:
        create_or_update_superuser(
            email=email,
            password=password,
            full_name=args.name,
            business_id=args.business_id,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
