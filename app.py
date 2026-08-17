import os
import threading
import zipfile
import logging
import uuid
from io import BytesIO
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_file,
    flash
)

from flask_login import (
    LoginManager,
    login_required,
    current_user
)

from werkzeug.utils import secure_filename

from docx import Document as WordDocument

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph
)

from reportlab.lib.styles import (
    getSampleStyleSheet
)

from reportlab.lib.pagesizes import A4

from config import Config
from models import (
    db,
    User,
    Document,
    ChatHistory
)

from auth import auth
from ocr_pipeline import run_ocr
from rag_engine import ask_question


# ============================================================
# APP SETUP
# ============================================================

app = Flask(__name__)

app.config.from_object(Config)


# ============================================================
# UPLOAD FOLDER
# ============================================================

app.config["UPLOAD_FOLDER"] = os.path.join(
    os.getcwd(),
    "uploads"
)

os.makedirs(
    app.config["UPLOAD_FOLDER"],
    exist_ok=True
)


# ============================================================
# OUTPUT FOLDER
# ============================================================

app.config["OUTPUT_FOLDER"] = os.path.join(
    os.getcwd(),
    "outputs"
)

os.makedirs(
    app.config["OUTPUT_FOLDER"],
    exist_ok=True
)


# ============================================================
# DATABASE
# ============================================================

db.init_app(app)


# ============================================================
# LOGIN MANAGER
# ============================================================

login_manager = LoginManager()

login_manager.login_view = "auth.login"

login_manager.init_app(app)


# ============================================================
# AUTH BLUEPRINT
# ============================================================

app.register_blueprint(auth)


# ============================================================
# LOAD USER
# ============================================================

@login_manager.user_loader
def load_user(user_id):

    return User.query.get(
        int(user_id)
    )


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    filename="system.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)


# ============================================================
# ROLE DECORATOR
# ============================================================

def role_required(role):

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            if current_user.role != role:

                flash(
                    "Access denied."
                )

                return redirect(
                    url_for("dashboard")
                )

            return func(
                *args,
                **kwargs
            )

        return wrapper

    return decorator


# ============================================================
# BACKGROUND OCR
# ============================================================

def process_ocr_background(
    app,
    doc_id,
    path
):

    with app.app_context():

        doc = Document.query.get(
            doc_id
        )

        if not doc:

            logging.error(
                f"Document {doc_id} not found."
            )

            return

        try:

            logging.info(
                f"Starting OCR for document {doc_id}"
            )

            # Run OCR
            text = run_ocr(path)

            # Save result
            doc.extracted_text = text

            doc.status = "completed"

            logging.info(
                f"OCR completed for document {doc_id}"
            )

        except Exception as e:

            doc.status = "failed"

            doc.extracted_text = (
                f"OCR Error: {str(e)}"
            )

            logging.exception(
                f"OCR failed for document {doc_id}"
            )

        db.session.commit()


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
@login_required
def dashboard():

    # ========================================================
    # ADMIN DASHBOARD
    # ========================================================

    if current_user.role == "admin":

        users = User.query.order_by(
            User.id.desc()
        ).all()

        documents = Document.query.order_by(
            Document.id.desc()
        ).all()

        return render_template(

            "admin_dashboard.html",

            users=users,

            documents=documents,

            total_users=User.query.count(),

            total_docs=Document.query.count(),

            total_completed=
                Document.query.filter_by(
                    status="completed"
                ).count(),

            total_failed=
                Document.query.filter_by(
                    status="failed"
                ).count()

        )


    # ========================================================
    # NORMAL USER DASHBOARD
    # ========================================================

    documents = Document.query.filter_by(

        user_id=current_user.id

    ).order_by(

        Document.id.desc()

    ).all()


    return render_template(

        "dashboard.html",

        user=current_user,

        documents=documents

    )


# ============================================================
# UPLOAD DOCUMENTS
# ============================================================

@app.route(
    "/upload",
    methods=["POST"]
)
@login_required
def upload():

    files = request.files.getlist(
        "documents"
    )


    if not files:

        flash(
            "No files selected."
        )

        return redirect(
            url_for("dashboard")
        )


    upload_folder = app.config[
        "UPLOAD_FOLDER"
    ]


    os.makedirs(
        upload_folder,
        exist_ok=True
    )


    uploaded_count = 0


    for file in files:

        if not file:
            continue

        if not file.filename:
            continue


        # ----------------------------------------------------
        # Secure filename
        # ----------------------------------------------------

        original_filename = secure_filename(
            file.filename
        )


        if not original_filename:
            continue


        # ----------------------------------------------------
        # Create unique filename
        # ----------------------------------------------------

        unique_name = (
            f"{uuid.uuid4()}_"
            f"{original_filename}"
        )


        save_path = os.path.join(

            upload_folder,

            unique_name

        )


        # ----------------------------------------------------
        # Save file
        # ----------------------------------------------------

        file.save(
            save_path
        )


        # ----------------------------------------------------
        # Create database record
        # ----------------------------------------------------

        doc = Document(

            filename=unique_name,

            stored_path=save_path,

            user_id=current_user.id,

            status="processing"

        )


        db.session.add(
            doc
        )

        db.session.commit()


        uploaded_count += 1


        # ----------------------------------------------------
        # Start OCR thread
        # ----------------------------------------------------

        thread = threading.Thread(

            target=process_ocr_background,

            args=(
                app,
                doc.id,
                save_path
            )

        )

        thread.daemon = True

        thread.start()


    flash(

        f"{uploaded_count} document(s) uploaded. "
        "OCR processing started."

    )


    return redirect(
        url_for("dashboard")
    )


# ============================================================
# VIEW DOCUMENT
# ============================================================

@app.route(
    "/document/<int:doc_id>",
    methods=["GET", "POST"]
)
@login_required
def view_document(doc_id):

    doc = Document.query.get_or_404(
        doc_id
    )


    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------

    if (
        doc.user_id != current_user.id
        and current_user.role != "admin"
    ):

        return "Unauthorized", 403


    # --------------------------------------------------------
    # CHAT HISTORY
    # --------------------------------------------------------

    chat_history = ChatHistory.query.filter_by(

        document_id=doc.id

    ).order_by(

        ChatHistory.id.asc()

    ).all()


    # --------------------------------------------------------
    # SAVE EDITED OCR TEXT
    # --------------------------------------------------------

    if request.method == "POST":

        edited_text = request.form.get(
            "edited_text",
            ""
        )


        doc.extracted_text = edited_text


        db.session.commit()


        flash(
            "Document updated successfully."
        )


        return redirect(

            url_for(
                "view_document",
                doc_id=doc.id
            )

        )


    return render_template(

        "view_document.html",

        doc=doc,

        chat_history=chat_history

    )


# ============================================================
# SERVE ORIGINAL DOCUMENT
# ============================================================

@app.route(
    "/document/file/<int:doc_id>"
)
@login_required
def document_file(doc_id):

    doc = Document.query.get_or_404(
        doc_id
    )


    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------

    if (
        doc.user_id != current_user.id
        and current_user.role != "admin"
    ):

        return "Unauthorized", 403


    # --------------------------------------------------------
    # CHECK FILE PATH
    # --------------------------------------------------------

    if not doc.stored_path:

        return "File not found", 404


    if not os.path.exists(
        doc.stored_path
    ):

        return "File not found", 404


    # --------------------------------------------------------
    # SEND FILE
    # --------------------------------------------------------

    return send_file(
        doc.stored_path
    )


# ============================================================
# DELETE DOCUMENT
# ============================================================

@app.route(
    "/document/delete/<int:doc_id>",
    methods=["GET"]
)
@login_required
def delete_document_user(doc_id):

    doc = Document.query.get_or_404(
        doc_id
    )


    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------

    if (
        doc.user_id != current_user.id
        and current_user.role != "admin"
    ):

        return "Unauthorized", 403


    # --------------------------------------------------------
    # DELETE ORIGINAL FILE
    # --------------------------------------------------------

    if doc.stored_path:

        try:

            if os.path.exists(
                doc.stored_path
            ):

                os.remove(
                    doc.stored_path
                )

                logging.info(
                    f"Deleted file: "
                    f"{doc.stored_path}"
                )

        except Exception as e:

            logging.error(
                f"Could not delete file: {e}"
            )


    # --------------------------------------------------------
    # DELETE CHAT HISTORY
    # --------------------------------------------------------

    ChatHistory.query.filter_by(

        document_id=doc.id

    ).delete(

        synchronize_session=False

    )


    # --------------------------------------------------------
    # DELETE DOCUMENT DATABASE RECORD
    # --------------------------------------------------------

    db.session.delete(
        doc
    )

    db.session.commit()


    logging.info(
        f"Document {doc_id} deleted by "
        f"user {current_user.id}"
    )


    flash(
        "Document deleted successfully."
    )


    return redirect(
        url_for("dashboard")
    )


# ============================================================
# ASK DOC AI
# ============================================================

@app.route(
    "/ask/<int:doc_id>",
    methods=["POST"]
)
@login_required
def ask_route(doc_id):

    doc = Document.query.get_or_404(
        doc_id
    )


    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------

    if (
        doc.user_id != current_user.id
        and current_user.role != "admin"
    ):

        return "Unauthorized", 403


    # --------------------------------------------------------
    # GET QUESTION
    # --------------------------------------------------------

    question = request.form.get(
        "question",
        ""
    ).strip()


    if not question:

        flash(
            "Please enter a question."
        )

        return redirect(

            url_for(
                "view_document",
                doc_id=doc.id
            )

        )


    # --------------------------------------------------------
    # CHECK OCR RESULT
    # --------------------------------------------------------

    if not doc.extracted_text:

        flash(
            "No extracted text is available."
        )

        return redirect(

            url_for(
                "view_document",
                doc_id=doc.id
            )

        )


    # --------------------------------------------------------
    # RAG
    # --------------------------------------------------------

    try:

        answer, citation = ask_question(

            doc.extracted_text,

            question

        )


        # ----------------------------------------------------
        # SAVE CHAT
        # ----------------------------------------------------

        chat = ChatHistory(

            document_id=doc.id,

            question=question,

            answer=answer,

            citation=citation

        )


        db.session.add(
            chat
        )

        db.session.commit()


    except Exception as e:

        logging.exception(
            "RAG processing failed"
        )


        print(
            "RAG ERROR:",
            e
        )


        flash(
            "Error processing your question."
        )


    return redirect(

        url_for(
            "view_document",
            doc_id=doc.id
        )

    )


# ============================================================
# DOWNLOAD PDF
# ============================================================

@app.route(
    "/download/pdf/<int:doc_id>"
)
@login_required
def download_pdf(doc_id):

    doc = Document.query.get_or_404(
        doc_id
    )


    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------

    if (
        doc.user_id != current_user.id
        and current_user.role != "admin"
    ):

        return "Unauthorized", 403


    # --------------------------------------------------------
    # OUTPUT PATH
    # --------------------------------------------------------

    output_path = os.path.join(

        app.config["OUTPUT_FOLDER"],

        f"{doc.id}.pdf"

    )


    # --------------------------------------------------------
    # CREATE PDF
    # --------------------------------------------------------

    pdf = SimpleDocTemplate(

        output_path,

        pagesize=A4

    )


    styles = getSampleStyleSheet()


    elements = []


    for line in (

        doc.extracted_text or ""

    ).split("\n"):

        elements.append(

            Paragraph(

                line,

                styles["Normal"]

            )

        )


    pdf.build(
        elements
    )


    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    return send_file(

        output_path,

        as_attachment=True,

        download_name=
            f"DOC_AI_{doc.id}.pdf"

    )


# ============================================================
# DOWNLOAD WORD
# ============================================================

@app.route(
    "/download/word/<int:doc_id>"
)
@login_required
def download_word(doc_id):

    doc = Document.query.get_or_404(
        doc_id
    )


    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------

    if (
        doc.user_id != current_user.id
        and current_user.role != "admin"
    ):

        return "Unauthorized", 403


    # --------------------------------------------------------
    # OUTPUT PATH
    # --------------------------------------------------------

    output_path = os.path.join(

        app.config["OUTPUT_FOLDER"],

        f"{doc.id}.docx"

    )


    # --------------------------------------------------------
    # CREATE WORD DOCUMENT
    # --------------------------------------------------------

    word_doc = WordDocument()


    word_doc.add_paragraph(

        doc.extracted_text or ""

    )


    word_doc.save(
        output_path
    )


    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    return send_file(

        output_path,

        as_attachment=True,

        download_name=
            f"DOC_AI_{doc.id}.docx"

    )


# ============================================================
# BULK DOWNLOAD
# ============================================================

@app.route(
    "/download/bulk",
    methods=["POST"]
)
@login_required
def bulk_download():

    selected_ids = request.form.getlist(
        "selected_docs"
    )


    if not selected_ids:

        flash(
            "No documents selected."
        )

        return redirect(
            url_for("dashboard")
        )


    memory_file = BytesIO()


    # --------------------------------------------------------
    # CREATE ZIP
    # --------------------------------------------------------

    with zipfile.ZipFile(

        memory_file,

        "w",

        zipfile.ZIP_DEFLATED

    ) as zf:


        for doc_id in selected_ids:

            try:

                doc = Document.query.get(
                    int(doc_id)
                )

            except (
                ValueError,
                TypeError
            ):

                continue


            if not doc:
                continue


            # ------------------------------------------------
            # SECURITY
            # ------------------------------------------------

            if (

                doc.user_id
                != current_user.id

                and current_user.role
                != "admin"

            ):

                continue


            # ------------------------------------------------
            # SAFE NAME
            # ------------------------------------------------

            safe_name = secure_filename(
                doc.filename
            )


            if not safe_name:

                safe_name = (
                    f"document_{doc.id}"
                )


            # ------------------------------------------------
            # ADD TO ZIP
            # ------------------------------------------------

            zf.writestr(

                f"{safe_name}.txt",

                doc.extracted_text or ""

            )


    memory_file.seek(0)


    return send_file(

        memory_file,

        download_name=
            "DOC_AI_documents.zip",

        as_attachment=True

    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    with app.app_context():

        db.create_all()


    app.run(
        debug=True
    )