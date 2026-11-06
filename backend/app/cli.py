"""Administrative CLI utility for the AI Voice Assistant SaaS platform.

Provides secure bootstrapping commands (e.g. creating initial Super Admin).
Usage:
    python -m app.cli create-super-admin --email admin@example.com --name "Super Admin" --password "StrongPass123!"
    or interactively:
    python -m app.cli create-super-admin
"""

import argparse
import getpass
import os
import sys
from app.core.logging import get_logger, setup_logging
from app.core.security import get_password_hash, validate_password_strength
from app.database.connection import SessionLocal
from app.models.user import User, UserRole

setup_logging()
logger = get_logger("app.cli")


def create_super_admin(
    email: str | None = None,
    full_name: str | None = None,
    password: str | None = None,
    db: SessionLocal = None,
) -> User | None:
    """Create a platform Super Admin user with no tenant association."""
    # Read from environment variables if not provided as arguments
    email = email or os.getenv("SUPER_ADMIN_EMAIL")
    full_name = full_name or os.getenv("SUPER_ADMIN_NAME")
    password = password or os.getenv("SUPER_ADMIN_PASSWORD")

    # Interactive prompts if still missing
    if not email:
        email = input("Enter Super Admin Email: ").strip()
    if not full_name:
        full_name = input("Enter Super Admin Full Name: ").strip()
    if not password:
        password = getpass.getpass("Enter Super Admin Password: ")
        confirm_password = getpass.getpass("Confirm Super Admin Password: ")
        if password != confirm_password:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    # Validate password complexity
    is_strong, reason = validate_password_strength(password)
    if not is_strong:
        print(f"Error: Weak password - {reason}", file=sys.stderr)
        sys.exit(1)

    should_close = False
    session = db
    if session is None:
        session = SessionLocal()
        should_close = True

    try:
        # Check if user already exists
        existing_user = session.query(User).filter(User.email == email.lower().strip()).first()
        if existing_user:
            if existing_user.role == UserRole.SUPER_ADMIN.value:
                print(f"User '{email}' is already a Super Admin.", file=sys.stderr)
                return existing_user
            else:
                existing_user.role = UserRole.SUPER_ADMIN.value
                existing_user.business_id = None
                existing_user.is_active = True
                existing_user.password_hash = get_password_hash(password)
                session.commit()
                print(f"Updated existing user '{email}' to Super Admin role successfully.")
                return existing_user

        # Create new platform Super Admin
        super_admin = User(
            business_id=None,
            full_name=full_name.strip(),
            email=email.lower().strip(),
            password_hash=get_password_hash(password),
            role=UserRole.SUPER_ADMIN.value,
            is_active=True,
        )
        session.add(super_admin)
        session.commit()
        session.refresh(super_admin)

        print(f"Super Admin '{super_admin.email}' (ID {super_admin.id}) created successfully.")
        return super_admin
    except Exception as exc:
        session.rollback()
        print(f"Failed to create Super Admin: {exc}", file=sys.stderr)
        raise
    finally:
        if should_close:
            session.close()


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="AI Voice Assistant Administrative CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: create-super-admin
    admin_parser = subparsers.add_parser("create-super-admin", help="Bootstrap a platform Super Admin user")
    admin_parser.add_argument("--email", help="Super Admin Email address")
    admin_parser.add_argument("--name", help="Super Admin Full Name")
    admin_parser.add_argument("--password", help="Super Admin Password")

    args = parser.parse_args()

    if args.command == "create-super-admin":
        create_super_admin(email=args.email, full_name=args.name, password=args.password)


if __name__ == "__main__":
    main()
