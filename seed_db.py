import models, database, auth
from sqlalchemy.orm import Session

def seed():
    models.Base.metadata.create_all(bind=database.engine)
    db = database.SessionLocal()
    
    # 1. MWO Admin (Generic)
    # User requested not to remove mwo_admin.
    mwo_admin = db.query(models.User).filter(models.User.username == "mwo_admin").first()
    if not mwo_admin:
        print("Creating MWO Admin (Generic)...")
        mwo_admin = models.User(
            username="mwo_admin",
            password_hash=auth.get_password_hash("admin123"),
            password_encrypted=auth.encrypt_password("admin123"),
            role=models.UserRole.MWO_ADMIN,
            airport_code="VABB_MWO"
        )
        db.add(mwo_admin)

    # 1. MWO Admin (Generic)
    mwo_admin = db.query(models.User).filter(models.User.username == "mwo_admin").first()
    if not mwo_admin:
        print("Creating MWO Admin (Generic)...")
        mwo_admin = models.User(
            username="mwo_admin",
            password_hash=auth.get_password_hash("admin123"),
            password_encrypted=auth.encrypt_password("admin123"),
            role=models.UserRole.MWO_ADMIN,
            airport_code="VABB_MWO"
        )
        db.add(mwo_admin)
    
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
        ("VABB", "MUMBAI AIRPORT"),
    ]

    # Explicitly Demote/Fix VABB if it was Admin
    vabb_admin = db.query(models.User).filter(models.User.username == "vabb@gmail.com", models.User.role == models.UserRole.MWO_ADMIN).first()
    if vabb_admin:
        print("Demoting VABB from Admin to Regional...")
        vabb_admin.role = models.UserRole.REGIONAL
        vabb_admin.full_name = "MUMBAI AIRPORT" # Revert name from "MUMBAI AIRPORT / MWO"

    # Cleanup erroneously created users if any
    garbage_emails = ["vanew@gmail.com"]
    for g_email in garbage_emails:
        g_user = db.query(models.User).filter(models.User.username == g_email).first()
        if g_user:
            print(f"Removing garbage user: {g_email}")
            db.delete(g_user)
            db.commit()

    default_password = "Airport@123"

    for code, name in airports:
        email_username = f"{code.lower()}@gmail.com"
        # Check if exists
        user = db.query(models.User).filter(models.User.username == email_username).first()
        if not user:
            print(f"Creating {name} ({code})...")
            new_user = models.User(
                username=email_username,
                full_name=name,
                password_hash=auth.get_password_hash(default_password),
                password_encrypted=auth.encrypt_password(default_password),
                role=models.UserRole.REGIONAL,
                airport_code=code
            )
            db.add(new_user)
        else:
             print(f"User {email_username} already exists. Updating name.")
             user.full_name = name

    db.commit()
    db.close()
    print("Database seeded successfully.")

if __name__ == "__main__":
    seed()
