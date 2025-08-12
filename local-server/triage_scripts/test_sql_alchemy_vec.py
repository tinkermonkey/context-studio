import sqlite3
import sqlite_vec
from sqlalchemy import event, create_engine, text

print("SQLite Version:", sqlite3.sqlite_version)
print("SQLite File:", sqlite3.__file__)

def main():
    print("Creating in-memory SQLite database...")
    engine = create_engine("sqlite:///:memory:")

    print("Registering event listener to load SQLite extensions...")
    @event.listens_for(engine, "connect")
    def receive_connect(connection, _):
        print("Enabling SQLite extensions...")
        connection.enable_load_extension(True)
        sqlite_vec.load(connection)
        connection.enable_load_extension(False)
        print("Extension loaded successfully!")

    print("Calling connect to create the database and trigger the event...")
    with engine.connect() as connection:
        print("Creating virtual table using vec0...")
        connection.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS test_vec USING vec0(
                id TEXT PRIMARY KEY,
                embedding FLOAT[384]
            );
        """))
        print("Virtual table created successfully!")

        vec_version, = connection.execute(text("select vec_version()")).fetchone()
        print(f"vec_version={vec_version}")


if __name__ == "__main__":
    main()
