import os
import smtplib
from dotenv import load_dotenv

load_dotenv()

email = os.getenv("MAIL_USERNAME")
password = os.getenv("MAIL_PASSWORD")

print(email)
print("Password configured:", bool(password))

server = smtplib.SMTP("smtp.gmail.com", 587)

server.starttls()

server.login(email, password)

print("SMTP LOGIN SUCCESS")

server.quit()