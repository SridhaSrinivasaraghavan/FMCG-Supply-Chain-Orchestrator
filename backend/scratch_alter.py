from sqlalchemy import text
from app.database import sync_engine

def main():
    with sync_engine.begin() as conn:
        conn.execute(text("ALTER TABLE disruption_logs ALTER COLUMN source_event TYPE TEXT;"))
        conn.execute(text("ALTER TABLE vendor_communications ALTER COLUMN subject TYPE TEXT;"))
        print("Columns altered successfully")

if __name__ == "__main__":
    main()
