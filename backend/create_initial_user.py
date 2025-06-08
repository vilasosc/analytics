import sys
import os

# This is to ensure the script can find the 'app' module when run from 'backend/'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.core.database import SessionLocal, create_db_and_tables
from app.crud.crud_user import create_user as crud_create_user_internal
from app.crud.crud_user import get_user_by_email
from app.models.user import UserRole # Depends on models.user

def create_initial_users_sync():
    print("Attempting to initialize database and create tables...")
    try:
        create_db_and_tables()
        print("Database and tables creation process initiated (if not exists).")
    except Exception as e:
        print(f"Error during table creation: {e}")
        # Optionally, re-raise or handle if critical
        return # Stop if DB setup fails

    db = SessionLocal()
    try:
        admin_email = "admin@pcsoft.com"
        analyst_email = "analyst@pcsoft.com"

        # Check and create admin user
        existing_admin = get_user_by_email(db, email=admin_email)
        if not existing_admin:
            print(f"Creating admin user: {admin_email}")
            crud_create_user_internal(db=db, email=admin_email, password="adminpassword", role=UserRole.ADMIN)
            print("Admin user created.")
        else:
            print(f"Admin user {admin_email} already exists.")

        # Check and create analyst user
        existing_analyst = get_user_by_email(db, email=analyst_email)
        if not existing_analyst:
            print(f"Creating analyst user: {analyst_email}")
            crud_create_user_internal(db=db, email=analyst_email, password="analystpassword", role=UserRole.ANALYST)
            print("Analyst user created.")
        else:
            print(f"Analyst user {analyst_email} already exists.")

    except Exception as e:
        print(f"An error occurred during user creation: {e}")
    finally:
        db.close()
        print("Initial user setup process finished.")

if __name__ == "__main__":
    print("Running script to create initial users...")
    create_initial_users_sync()
