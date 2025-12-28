import sys
import os
sys.path.append(os.getcwd())
import database
from sqlalchemy import text

def migrate():
    engine = database.engine
    with engine.connect() as conn:
        print("Adding transmet_status column...")
        try:
            conn.execute(text("ALTER TABLE alerts ADD COLUMN transmet_status VARCHAR"))
            conn.commit()
        except Exception as e:
            print(f"transmet_status: {e}")
            
        print("Adding transmet_response column...")
        try:
            conn.execute(text("ALTER TABLE alerts ADD COLUMN transmet_response VARCHAR"))
            conn.commit()
        except Exception as e:
            print(f"transmet_response: {e}")
            
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
