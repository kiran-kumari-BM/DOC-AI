import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "dev-only-secret-change-me"
    )

    SQLALCHEMY_DATABASE_URI = "postgresql:///cmti_docs"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
    OUTPUT_FOLDER = os.path.join(os.getcwd(), "outputs")

import os
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"