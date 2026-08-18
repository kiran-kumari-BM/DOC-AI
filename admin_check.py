from app import app
from models import db, User

with app.app_context():

    user = User.query.filter_by(
        email="kirankumari767618@gmail.com"
    ).first()

    if user is None:
        print("❌ User not found.")
    else:
        user.role = "admin"
        db.session.commit()

        print("✅ Account is now ADMIN")
        print()
        print("ID:", user.id)
        print("Name:", user.name)
        print("Email:", user.email)
        print("Role:", user.role)