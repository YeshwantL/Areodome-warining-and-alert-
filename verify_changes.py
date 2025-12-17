from app import models, database, auth
from sqlalchemy.orm import Session

def verify():
    db = database.SessionLocal()
    print("--- Current Users ---")
    users = db.query(models.User).all()
    for u in users:
        print(f"User: {u.username}, Role: {u.role}, Airport: {u.airport_code}")
    
    print("\n--- Simulating Admin Adding Airport 'VANEW' ---")
    new_code = "VANEW"
    email = f"{new_code.lower()}@gmail.com"
    
    existing = db.query(models.User).filter(models.User.username == email).first()
    if existing:
        print(f"User {email} already exists (Clean up previous run?)")
        db.delete(existing)
        db.commit()
    
    # Simulate logic from admin.py
    new_user = models.User(
        username=email,
        password_hash=auth.get_password_hash("Airport@123"),
        role=models.UserRole.REGIONAL,
        airport_code=new_code
    )
    db.add(new_user)
    db.commit()
    
    # Verify addition
    check = db.query(models.User).filter(models.User.username == email).first()
    if check:
        print(f"SUCCESS: Added {check.username} with code {check.airport_code}")
    else:
        print("FAILURE: Could not find new user.")

    db.close()

if __name__ == "__main__":
    verify()
