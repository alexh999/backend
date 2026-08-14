from __future__ import annotations

import argparse
import getpass

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.users.models import UserRole
from app.modules.users.service import (
    UserAlreadyExistsError,
    UserServiceError,
    create_user,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local admin account.")
    parser.add_argument("--username", required=True)
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.")
        return 1

    settings = get_settings()
    session = get_session_factory(settings)()
    try:
        create_user(
            session,
            username=args.username,
            password=password,
            role=UserRole.ADMIN,
        )
    except UserAlreadyExistsError as exc:
        print(exc)
        return 1
    except UserServiceError as exc:
        print(exc)
        return 1
    except SQLAlchemyError:
        session.rollback()
        print("Unable to access the users table. Run alembic upgrade head first.")
        return 1
    finally:
        session.close()

    print("Admin account created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
