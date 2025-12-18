from app import models, database, auth
from sqlalchemy.orm import Session

def seed():
    models.Base.metadata.create_all(bind=database.engine)
    db = database.SessionLocal()
    
    # 1. MWO Admin
    admin = db.query(models.User).filter(models.User.username == "mwo_admin").first()
    if not admin:
        print("Creating MWO Admin...")
        admin_user = models.User(
            username="mwo_admin",
            password_hash=auth.get_password_hash("admin123"), # Admin generic password? Or different?
            password_encrypted=auth.encrypt_password("admin123"),
            # Prompt implied "give them all a default password" - usually applies to new users.
            # Keeping existing admin logic but ensuring it matches roles.
            role=models.UserRole.MWO_ADMIN,
            airport_code="VABB_MWO"
        )
        db.add(admin_user)

    # 2. Regional Airports List
    # Format: Code, Name
    airports = [
        ("VASD", "SHIRDI AIRPORT"),
        ("VAJJ", "JUHU AIRPORT"),
        ("VAJL", "JALGAON AIRPORT"),
        ("VAAU", "AURANGABAD AIRPORT"),
        ("VOND", "NANDED AIRPORT"),
        ("VAKP", "KOLHAPUR AIRPORT"),
        ("VOSR", "SINDHUDURG AIRPORT"),
        ("VASL", "SOLAPUR AIRPORT"),
        ("VOLT", "LATUR AIRPORT"),
        ("VOGA", "MOPA AIRPORT"),
        ("VANM", "NAVI MUMBAI AIRPORT"),
    ]

    default_password = "Airport@123"

    for code, name in airports:
        email_username = f"{code.lower()}@gmail.com"
        # Check if exists
        user = db.query(models.User).filter(models.User.username == email_username).first()
        if not user:
            print(f"Creating {name} ({code})...")
            new_user = models.User(
                username=email_username,
                password_hash=auth.get_password_hash(default_password),
                password_encrypted=auth.encrypt_password(default_password),
                role=models.UserRole.REGIONAL,
                airport_code=code
            )
            db.add(new_user)
        else:
             print(f"User {email_username} already exists.")

    db.commit()
    db.close()
    print("Database seeded successfully.")

if __name__ == "__main__":
    seed()
