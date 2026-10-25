from sqlalchemy import text

from db.database import SessionLocal, engine

try:
    # Verify the database connection and authenticated user.
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT current_database(), current_user")
        )
        database_name, username = result.one()

        print("Shared database connection successful!")
        print(f"Database: {database_name}")
        print(f"User: {username}")

    # Verify the database session and authenticated user.
    with SessionLocal() as session:
        result = session.execute(
            text("SELECT current_database(), current_user")
        )
        database_name, username = result.one()

        print("SessionLocal database session successful!")
        print(f"Database: {database_name}")
        print(f"User: {username}")
finally:
    engine.dispose()
