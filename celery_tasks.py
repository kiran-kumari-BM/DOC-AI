import os
import sys
import importlib.util

from flask import Flask

from celery_app import celery
from config import Config
from models import db, Document


# ============================================================
# PROJECT DIRECTORY
# ============================================================

PROJECT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

# Make sure the DOC-AI project directory is available
# to Python when Celery is running.
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)


# ============================================================
# CREATE LIGHTWEIGHT FLASK APP FOR CELERY
# ============================================================

def create_celery_flask_app():

    """
    Create a lightweight Flask application for Celery.

    We intentionally do NOT import app.py here.
    This prevents circular imports and avoids loading
    the complete Flask application inside the worker.
    """

    flask_app = Flask(__name__)

    # Load the same configuration used by the main app
    flask_app.config.from_object(Config)

    # --------------------------------------------------------
    # Upload folder
    # --------------------------------------------------------

    flask_app.config["UPLOAD_FOLDER"] = os.path.join(
        PROJECT_DIR,
        "uploads"
    )

    os.makedirs(
        flask_app.config["UPLOAD_FOLDER"],
        exist_ok=True
    )

    # --------------------------------------------------------
    # Output folder
    # --------------------------------------------------------

    flask_app.config["OUTPUT_FOLDER"] = os.path.join(
        PROJECT_DIR,
        "outputs"
    )

    os.makedirs(
        flask_app.config["OUTPUT_FOLDER"],
        exist_ok=True
    )

    # --------------------------------------------------------
    # Initialize database
    # --------------------------------------------------------

    db.init_app(flask_app)

    return flask_app


# ============================================================
# LOAD OCR PIPELINE
# ============================================================

def load_ocr_pipeline():

    """
    Load ocr_pipeline.py directly from the project directory.

    Using the absolute file path avoids the
    'No module named ocr_pipeline' problem that was occurring
    inside the Celery worker.
    """

    ocr_path = os.path.join(
        PROJECT_DIR,
        "ocr_pipeline.py"
    )

    print(
        f"📂 Loading OCR pipeline from: {ocr_path}"
    )

    # Make sure the file actually exists
    if not os.path.isfile(ocr_path):

        raise FileNotFoundError(
            f"OCR pipeline not found: {ocr_path}"
        )

    # Create module specification
    spec = importlib.util.spec_from_file_location(
        "ocr_pipeline",
        ocr_path
    )

    if spec is None or spec.loader is None:

        raise ImportError(
            f"Could not create module specification "
            f"for {ocr_path}"
        )

    # Create module
    ocr_module = importlib.util.module_from_spec(
        spec
    )

    # Register module
    sys.modules["ocr_pipeline"] = ocr_module

    # Execute ocr_pipeline.py
    spec.loader.exec_module(
        ocr_module
    )

    print(
        "✅ OCR pipeline loaded successfully"
    )

    # Make sure run_ocr exists
    if not hasattr(
        ocr_module,
        "run_ocr"
    ):

        raise AttributeError(
            "ocr_pipeline.py does not contain run_ocr()"
        )

    return ocr_module.run_ocr


# ============================================================
# CELERY OCR TASK
# ============================================================

@celery.task(bind=True)
def process_ocr_task(
    self,
    doc_id,
    path
):

    print(
        f"🔄 Starting OCR for document {doc_id}"
    )

    # --------------------------------------------------------
    # Create Flask application
    # --------------------------------------------------------

    flask_app = create_celery_flask_app()

    # --------------------------------------------------------
    # Flask application context
    # --------------------------------------------------------

    try:

        with flask_app.app_context():

            # ------------------------------------------------
            # Find document
            # ------------------------------------------------

            doc = Document.query.get(
                doc_id
            )

            if not doc:

                print(
                    f"❌ Document {doc_id} not found"
                )

                return {
                    "status": "failed",
                    "doc_id": doc_id,
                    "error": "Document not found"
                }

            # ------------------------------------------------
            # Run OCR
            # ------------------------------------------------

            try:

                print(
                    f"🧠 Running OCR for document {doc_id}"
                )

                # Load OCR pipeline
                run_ocr = load_ocr_pipeline()

                # Verify input file
                if not os.path.isfile(path):

                    raise FileNotFoundError(
                        f"Uploaded file not found: {path}"
                    )

                print(
                    f"📄 Processing file: {path}"
                )

                # ------------------------------------------------
                # Execute OCR
                # ------------------------------------------------

                text = run_ocr(
                    path
                )

                # ------------------------------------------------
                # Save OCR result
                # ------------------------------------------------

                doc.extracted_text = text

                doc.status = "completed"

                db.session.commit()

                print(
                    f"✅ OCR completed for document {doc_id}"
                )

                return {
                    "status": "completed",
                    "doc_id": doc_id
                }

            # ----------------------------------------------------
            # OCR ERROR
            # ----------------------------------------------------

            except Exception as e:

                doc.status = "failed"

                doc.extracted_text = (
                    f"OCR Error: {str(e)}"
                )

                db.session.commit()

                print(
                    f"❌ OCR failed for document "
                    f"{doc_id}: {e}"
                )

                return {
                    "status": "failed",
                    "doc_id": doc_id,
                    "error": str(e)
                }

    # ------------------------------------------------------------
    # CELERY TASK ERROR
    # ------------------------------------------------------------

    except Exception as e:

        import traceback

        print(
            f"❌ Celery task failed for document "
            f"{doc_id}: {e}"
        )

        traceback.print_exc()

        return {
            "status": "failed",
            "doc_id": doc_id,
            "error": str(e)
        }

    finally:

        # --------------------------------------------------------
        # Remove SQLAlchemy session safely
        # --------------------------------------------------------

        try:

            with flask_app.app_context():

                db.session.remove()

        except Exception:

            pass