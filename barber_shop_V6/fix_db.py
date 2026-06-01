from app import app, db
from sqlalchemy import text

def fix_barber_dashboard_db():
    with app.app_context():
        # 1. Add linked_barber_id to the user table
        try:
            db.session.execute(text("ALTER TABLE 'user' ADD COLUMN linked_barber_id INTEGER REFERENCES barber(id)"))
            print("✅ Successfully added 'linked_barber_id' column to 'user' table!")
        except Exception as e:
            print("⚠️ User column exists or error occurred:", e)

        # 2. Add photo_filename to the transaction table
        try:
            db.session.execute(text("ALTER TABLE 'transaction' ADD COLUMN photo_filename VARCHAR(255)"))
            print("✅ Successfully added 'photo_filename' column to 'transaction' table!")
        except Exception as e:
            print("⚠️ Transaction column exists or error occurred:", e)
            
        db.session.commit()

if __name__ == '__main__':
    fix_barber_dashboard_db()