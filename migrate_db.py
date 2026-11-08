import sqlite3
import os

def migrate():
    db_path = 'jobs.db'
    if not os.path.exists(db_path):
        print("Database not found, nothing to migrate.")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    columns = [
        ('accuracy', 'JSON'),
        ('parent_id', 'TEXT'),
        ('version', "TEXT DEFAULT 'v1'"),
        ('username', "TEXT DEFAULT 'Anonymous'"),
        ('feedback', 'JSON')
    ]
    
    for col_name, col_type in columns:
        try:
            print(f"Adding column {col_name}...")
            c.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists.")
            else:
                print(f"Error adding {col_name}: {e}")
                
    conn.commit()
    conn.close()
    print("Migration finished.")

if __name__ == "__main__":
    migrate()
