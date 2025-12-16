from app import models, database, auth
from sqlalchemy.orm import Session

def seed():
    models.Base.metadata.create_all(bind=database.engine)
    db = database.SessionLocal()
    
    # Create MWO Admin
    admin = db.query(models.User).filter(models.User.username == "mwo_admin").first()
    if not admin:
        print("Creating MWO Admin...")
        admin_user = models.User(
            username="mwo_admin",
            password_hash=auth.get_password_hash("admin123"),
            role=models.UserRole.MWO_ADMIN,
            airport_code="VABB_MWO"
        )
        db.add(admin_user)
    
    # Create Regional Airport (Example: VABB)
    regional = db.query(models.User).filter(models.User.username == "vabb_airport").first()
    if not regional:
        print("Creating Regional Airport VABB...")
        regional_user = models.User(
            username="vabb_airport",
            password_hash=auth.get_password_hash("airport123"),
            role=models.UserRole.REGIONAL,
            airport_code="VABB"
        )
        db.add(regional_user)

    db.commit()
    db.close()
    print("Database seeded successfully.")

if __name__ == "__main__":
    seed()
