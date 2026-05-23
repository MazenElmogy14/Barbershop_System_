from app import app, db
from sqlalchemy import text

def fix_barber_db():
    with app.app_context():
        try:
            db.session.execute(text("ALTER TABLE 'barber' ADD COLUMN balance FLOAT DEFAULT 0.0"))
            db.session.commit()
            print("✅ تم إضافة عمود 'balance' بنجاح لجدول الحلاقين!")
        except Exception as e:
            print("⚠️ العمود موجود بالفعل أو حدث خطأ:", e)

if __name__ == '__main__':
    fix_barber_db()