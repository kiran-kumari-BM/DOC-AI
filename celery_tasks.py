import os
import sys
import base64
import traceback
import importlib.util
import tempfile

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


if PROJECT_DIR not in sys.path:

    sys.path.insert(
        0,
        PROJECT_DIR
    )


# ============================================================
# CREATE LIGHTWEIGHT FLASK APP
# ============================================================

def create_celery_flask_app():

    """
    Creates a lightweight Flask application for the Celery
    worker.

    We intentionally do NOT import app.py.

    This prevents:
        - circular imports
        - loading the complete web application
        - unnecessary Flask routes
        - unnecessary application startup
    """

    flask_app = Flask(
        __name__
    )

    # --------------------------------------------------------
    # Load project configuration
    # --------------------------------------------------------

    flask_app.config.from_object(
        Config
    )

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

    db.init_app(
        flask_app
    )

    return flask_app


# ============================================================
# LOAD OCR PIPELINE
# ============================================================

def load_ocr_pipeline():

    """
    Dynamically loads ocr_pipeline.py.

    The OCR model is loaded INSIDE the Celery worker,
    not inside the Flask web process.
    """

    ocr_path = os.path.join(
        PROJECT_DIR,
        "ocr_pipeline.py"
    )

    print("=" * 70, flush=True)

    print(
        f"📂 Looking for OCR pipeline:"
        f" {ocr_path}",
        flush=True
    )

    print("=" * 70, flush=True)

    # --------------------------------------------------------
    # Check file
    # --------------------------------------------------------

    if not os.path.isfile(
        ocr_path
    ):

        raise FileNotFoundError(
            f"OCR pipeline not found: {ocr_path}"
        )

    # --------------------------------------------------------
    # Create module specification
    # --------------------------------------------------------

    spec = importlib.util.spec_from_file_location(
        "ocr_pipeline",
        ocr_path
    )

    if (
        spec is None
        or spec.loader is None
    ):

        raise ImportError(
            "Could not create OCR pipeline module specification."
        )

    # --------------------------------------------------------
    # Create module
    # --------------------------------------------------------

    ocr_module = importlib.util.module_from_spec(
        spec
    )

    # --------------------------------------------------------
    # Register module
    # --------------------------------------------------------

    sys.modules[
        "ocr_pipeline"
    ] = ocr_module

    # --------------------------------------------------------
    # Execute module
    # --------------------------------------------------------

    print(
        "🧠 Loading OCR pipeline...",
        flush=True
    )

    spec.loader.exec_module(
        ocr_module
    )

    print(
        "✅ OCR pipeline loaded successfully.",
        flush=True
    )

    # --------------------------------------------------------
    # Verify run_ocr
    # --------------------------------------------------------

    if not hasattr(
        ocr_module,
        "run_ocr"
    ):

        raise AttributeError(
            "ocr_pipeline.py does not contain run_ocr()."
        )

    return ocr_module.run_ocr


# ============================================================
# CELERY OCR TASK
# ============================================================

@celery.task(
    bind=True,
    name="process_ocr_task"
)
def process_ocr_task(
    self,
    doc_id,
    file_data_b64,
    original_filename
):

    """
    Process one uploaded document.

    IMPORTANT:

    We receive the file as Base64 data instead of relying on
    the web service's local filesystem.

    This is important on Render because the Flask Web Service
    and Celery Background Worker are separate services.
    """

    flask_app = None

    temporary_path = None

    print("=" * 70, flush=True)

    print(
        f"🔄 CELERY OCR TASK STARTED",
        flush=True
    )

    print(
        f"Document ID: {doc_id}",
        flush=True
    )

    print(
        f"Filename: {original_filename}",
        flush=True
    )

    print("=" * 70, flush=True)

    try:

        # ====================================================
        # CREATE FLASK APP
        # ====================================================

        flask_app = create_celery_flask_app()

        # ====================================================
        # FLASK APPLICATION CONTEXT
        # ====================================================

        with flask_app.app_context():

            # =================================================
            # FIND DOCUMENT
            # =================================================

            doc = Document.query.get(
                doc_id
            )

            if not doc:

                print(
                    f"❌ Document {doc_id} not found.",
                    flush=True
                )

                return {
                    "status": "failed",
                    "doc_id": doc_id,
                    "error": "Document not found"
                }

            # =================================================
            # MARK PROCESSING
            # =================================================

            doc.status = "processing"

            db.session.commit()

            # =================================================
            # DECODE FILE
            # =================================================

            try:

                print(
                    "📦 Decoding uploaded file...",
                    flush=True
                )

                file_bytes = base64.b64decode(
                    file_data_b64
                )

            except Exception as e:

                raise RuntimeError(
                    f"Could not decode uploaded file: {e}"
                )

            # =================================================
            # CHECK FILE
            # =================================================

            if not file_bytes:

                raise RuntimeError(
                    "Uploaded file is empty."
                )

            print(
                f"📄 File size: "
                f"{len(file_bytes)} bytes",
                flush=True
            )

            # =================================================
            # CREATE WORKER TEMP FILE
            # =================================================

            worker_upload_folder = os.path.join(
                PROJECT_DIR,
                "uploads"
            )

            os.makedirs(
                worker_upload_folder,
                exist_ok=True
            )

            # -------------------------------------------------
            # Make filename safe
            # -------------------------------------------------

            safe_filename = os.path.basename(
                original_filename
            )

            temporary_filename = (
                f"celery_{doc_id}_"
                f"{safe_filename}"
            )

            temporary_path = os.path.join(
                worker_upload_folder,
                temporary_filename
            )

            # =================================================
            # WRITE FILE
            # =================================================

            print(
                f"💾 Writing temporary file:"
                f" {temporary_path}",
                flush=True
            )

            with open(
                temporary_path,
                "wb"
            ) as f:

                f.write(
                    file_bytes
                )

            # =================================================
            # VERIFY FILE
            # =================================================

            if not os.path.isfile(
                temporary_path
            ):

                raise FileNotFoundError(
                    f"Worker could not create file:"
                    f" {temporary_path}"
                )

            print(
                "✅ Temporary file created.",
                flush=True
            )

            # =================================================
            # LOAD OCR
            # =================================================

            print(
                "🧠 Loading OCR model/pipeline...",
                flush=True
            )

            run_ocr = load_ocr_pipeline()

            print(
                "✅ OCR model/pipeline ready.",
                flush=True
            )

            # =================================================
            # UPDATE CELERY STATE
            # =================================================

            self.update_state(
                state="STARTED",
                meta={
                    "doc_id": doc_id,
                    "stage": "OCR processing"
                }
            )

            # =================================================
            # RUN OCR
            # =================================================

            print("=" * 70, flush=True)

            print(
                f"🔍 RUNNING OCR FOR DOCUMENT {doc_id}",
                flush=True
            )

            print(
                f"Input: {temporary_path}",
                flush=True
            )

            print("=" * 70, flush=True)

            text = run_ocr(
                temporary_path
            )

            # =================================================
            # VALIDATE RESULT
            # =================================================

            if text is None:

                text = ""

            elif not isinstance(
                text,
                str
            ):

                text = str(
                    text
                )

            # =================================================
            # SAVE OCR RESULT
            # =================================================

            doc.extracted_text = text

            doc.status = "completed"

            db.session.commit()

            # =================================================
            # SUCCESS
            # =================================================

            print("=" * 70, flush=True)

            print(
                f"✅ OCR COMPLETED"
                f" — DOCUMENT {doc_id}",
                flush=True
            )

            print(
                f"Extracted characters: {len(text)}",
                flush=True
            )

            print("=" * 70, flush=True)

            return {
                "status": "completed",
                "doc_id": doc_id,
                "characters": len(text)
            }

    # ========================================================
    # EXPECTED TASK ERROR
    # ========================================================

    except Exception as e:

        print("=" * 70, flush=True)

        print(
            f"❌ OCR TASK FAILED"
            f" — DOCUMENT {doc_id}",
            flush=True
        )

        print(
            f"ERROR TYPE: {type(e).__name__}",
            flush=True
        )

        print(
            f"ERROR: {str(e)}",
            flush=True
        )

        print(
            "FULL TRACEBACK:",
            flush=True
        )

        traceback.print_exc()

        print("=" * 70, flush=True)

        # ----------------------------------------------------
        # Update database
        # ----------------------------------------------------

        try:

            if flask_app is not None:

                with flask_app.app_context():

                    doc = Document.query.get(
                        doc_id
                    )

                    if doc:

                        doc.status = "failed"

                        doc.extracted_text = (
                            f"OCR Error: {str(e)}"
                        )

                        db.session.commit()

        except Exception as db_error:

            print(
                "❌ Could not update failed task "
                f"in database: {db_error}",
                flush=True
            )

            traceback.print_exc()

        # ----------------------------------------------------
        # Return failure
        # ----------------------------------------------------

        return {
            "status": "failed",
            "doc_id": doc_id,
            "error": str(e)
        }

    # ========================================================
    # FINALLY
    # ========================================================

    finally:

        # ----------------------------------------------------
        # Remove temporary worker file
        # ----------------------------------------------------

        if temporary_path:

            try:

                if os.path.exists(
                    temporary_path
                ):

                    os.remove(
                        temporary_path
                    )

                    print(
                        f"🗑️ Removed temporary file:"
                        f" {temporary_path}",
                        flush=True
                    )

            except Exception as cleanup_error:

                print(
                    f"⚠️ Could not remove temporary "
                    f"file: {cleanup_error}",
                    flush=True
                )

        # ----------------------------------------------------
        # Remove SQLAlchemy session
        # ----------------------------------------------------

        try:

            if flask_app is not None:

                with flask_app.app_context():

                    db.session.remove()

        except Exception:

            pass

        print(
            f"🏁 Celery task finished for "
            f"document {doc_id}",
            flush=True
        )