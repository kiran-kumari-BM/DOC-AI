import os
import sys
import base64
import traceback
import importlib.util

from flask import Flask

from celery_app import celery

from config import Config

from models import (
    db,
    Document
)


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
# GLOBAL OCR PIPELINE
# ============================================================

OCR_RUNNER = None


# ============================================================
# CREATE LIGHTWEIGHT FLASK APP
# ============================================================

def create_celery_flask_app():

    """
    Creates a lightweight Flask application for the Celery
    worker.

    We intentionally DO NOT import app.py.

    This prevents:

        - circular imports
        - loading Flask routes
        - loading the complete web application
        - unnecessary startup work
    """

    flask_app = Flask(
        __name__
    )

    # --------------------------------------------------------
    # Load configuration
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
    # Database
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
    Loads ocr_pipeline.py once.

    The result is cached in OCR_RUNNER.

    This is extremely important because the OCR model may be
    large and expensive to load.
    """

    global OCR_RUNNER

    # --------------------------------------------------------
    # Already loaded
    # --------------------------------------------------------

    if OCR_RUNNER is not None:

        print(
            "♻️ Reusing already loaded OCR pipeline.",
            flush=True
        )

        return OCR_RUNNER

    # --------------------------------------------------------
    # OCR path
    # --------------------------------------------------------

    ocr_path = os.path.join(

        PROJECT_DIR,

        "ocr_pipeline.py"

    )

    print(
        "=" * 70,
        flush=True
    )

    print(
        "🧠 LOADING OCR PIPELINE",
        flush=True
    )

    print(
        f"Path: {ocr_path}",
        flush=True
    )

    print(
        "=" * 70,
        flush=True
    )

    # --------------------------------------------------------
    # Check file
    # --------------------------------------------------------

    if not os.path.isfile(
        ocr_path
    ):

        raise FileNotFoundError(

            f"OCR pipeline not found: "
            f"{ocr_path}"

        )

    # --------------------------------------------------------
    # Module specification
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

            "Could not create OCR pipeline "
            "module specification."

        )

    # --------------------------------------------------------
    # Create module
    # --------------------------------------------------------

    ocr_module = (
        importlib.util.module_from_spec(
            spec
        )
    )

    # --------------------------------------------------------
    # Register module
    # --------------------------------------------------------

    sys.modules[
        "ocr_pipeline"
    ] = ocr_module

    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    print(
        "⏳ Importing OCR pipeline and loading models...",
        flush=True
    )

    spec.loader.exec_module(
        ocr_module
    )

    # --------------------------------------------------------
    # Check run_ocr
    # --------------------------------------------------------

    if not hasattr(
        ocr_module,
        "run_ocr"
    ):

        raise AttributeError(

            "ocr_pipeline.py does not contain "
            "run_ocr()."

        )

    # --------------------------------------------------------
    # Cache
    # --------------------------------------------------------

    OCR_RUNNER = (
        ocr_module.run_ocr
    )

    print(
        "=" * 70,
        flush=True
    )

    print(
        "✅ OCR PIPELINE LOADED",
        flush=True
    )

    print(
        "The model will be reused for future tasks.",
        flush=True
    )

    print(
        "=" * 70,
        flush=True
    )

    return OCR_RUNNER


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

    Arguments:

        doc_id
            Database document ID.

        file_data_b64
            Base64 encoded uploaded file.

        original_filename
            Original uploaded filename.

    The file is transferred through Redis/Celery.

    The worker then writes it to its own local temporary
    filesystem and runs OCR.
    """

    flask_app = None

    temporary_path = None

    print(
        "=" * 70,
        flush=True
    )

    print(
        "🔄 CELERY OCR TASK STARTED",
        flush=True
    )

    print(
        f"DOCUMENT ID: {doc_id}",
        flush=True
    )

    print(
        f"FILENAME: {original_filename}",
        flush=True
    )

    print(
        f"CELERY TASK ID: {self.request.id}",
        flush=True
    )

    print(
        "=" * 70,
        flush=True
    )

    try:

        # ====================================================
        # CREATE FLASK APP
        # ====================================================

        flask_app = (
            create_celery_flask_app()
        )

        # ====================================================
        # APPLICATION CONTEXT
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
                    f"❌ Document {doc_id} "
                    f"does not exist.",
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

            print(
                "📦 Decoding uploaded file...",
                flush=True
            )

            try:

                file_bytes = (
                    base64.b64decode(
                        file_data_b64
                    )
                )

            except Exception as e:

                raise RuntimeError(

                    f"Could not decode uploaded "
                    f"file: {e}"

                )

            # =================================================
            # CHECK FILE
            # =================================================

            if not file_bytes:

                raise RuntimeError(
                    "Uploaded file is empty."
                )

            print(

                f"📄 Received "
                f"{len(file_bytes)} bytes.",

                flush=True

            )

            # =================================================
            # CREATE WORKER UPLOAD DIRECTORY
            # =================================================

            worker_upload_folder = os.path.join(

                PROJECT_DIR,

                "uploads"

            )

            os.makedirs(

                worker_upload_folder,

                exist_ok=True

            )

            # =================================================
            # SAFE FILENAME
            # =================================================

            safe_filename = os.path.basename(

                original_filename

            )

            # Prevent weird/empty names

            if not safe_filename:

                safe_filename = (
                    f"document_{doc_id}"
                )

            # =================================================
            # TEMPORARY PATH
            # =================================================

            temporary_filename = (

                f"celery_"
                f"{doc_id}_"
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

                f"💾 Writing worker file: "
                f"{temporary_path}",

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
            # VERIFY
            # =================================================

            if not os.path.isfile(
                temporary_path
            ):

                raise FileNotFoundError(

                    f"Worker could not create: "
                    f"{temporary_path}"

                )

            print(
                "✅ Worker file created.",
                flush=True
            )

            # =================================================
            # CELERY STATE
            # =================================================

            self.update_state(

                state="STARTED",

                meta={

                    "doc_id": doc_id,

                    "stage": "Loading OCR model"

                }

            )

            # =================================================
            # LOAD OCR
            # =================================================

            print(
                "🧠 Preparing OCR pipeline...",
                flush=True
            )

            run_ocr = (
                load_ocr_pipeline()
            )

            print(
                "✅ OCR pipeline ready.",
                flush=True
            )

            # =================================================
            # UPDATE STATE
            # =================================================

            self.update_state(

                state="STARTED",

                meta={

                    "doc_id": doc_id,

                    "stage": "Running OCR"

                }

            )

            # =================================================
            # RUN OCR
            # =================================================

            print(
                "=" * 70,
                flush=True
            )

            print(
                f"🔍 RUNNING OCR "
                f"FOR DOCUMENT {doc_id}",
                flush=True
            )

            print(
                f"INPUT: {temporary_path}",
                flush=True
            )

            print(
                "=" * 70,
                flush=True
            )

            text = run_ocr(
                temporary_path
            )

            # =================================================
            # NORMALIZE RESULT
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
            # SAVE RESULT
            # =================================================

            doc.extracted_text = text

            doc.status = "completed"

            db.session.commit()

            # =================================================
            # SUCCESS
            # =================================================

            print(
                "=" * 70,
                flush=True
            )

            print(
                "✅ OCR COMPLETED",
                flush=True
            )

            print(
                f"DOCUMENT ID: {doc_id}",
                flush=True
            )

            print(
                f"EXTRACTED CHARACTERS: "
                f"{len(text)}",
                flush=True
            )

            print(
                "=" * 70,
                flush=True
            )

            return {

                "status": "completed",

                "doc_id": doc_id,

                "characters": len(text)

            }

    # ========================================================
    # ERROR
    # ========================================================

    except Exception as e:

        print(
            "=" * 70,
            flush=True
        )

        print(
            "❌ CELERY OCR TASK FAILED",
            flush=True
        )

        print(
            f"DOCUMENT ID: {doc_id}",
            flush=True
        )

        print(
            f"ERROR TYPE: "
            f"{type(e).__name__}",
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

        print(
            "=" * 70,
            flush=True
        )

        # ----------------------------------------------------
        # UPDATE DATABASE
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

                            "OCR Error: "

                            + str(e)

                        )

                        db.session.commit()

        except Exception as db_error:

            print(

                "❌ DATABASE UPDATE FAILED:",
                str(db_error),

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
    # CLEANUP
    # ========================================================

    finally:

        # ----------------------------------------------------
        # Remove temporary file
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

                        f"🗑️ Removed temporary "
                        f"file: {temporary_path}",

                        flush=True

                    )

            except Exception as cleanup_error:

                print(

                    "⚠️ Could not remove "
                    f"temporary file: "
                    f"{cleanup_error}",

                    flush=True

                )

        # ----------------------------------------------------
        # Remove database session
        # ----------------------------------------------------

        try:

            if flask_app is not None:

                with flask_app.app_context():

                    db.session.remove()

        except Exception:

            pass

        print(

            f"🏁 Celery task finished "
            f"for document {doc_id}",

            flush=True

        )