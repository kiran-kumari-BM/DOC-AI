import os
import cv2
import numpy as np
from PIL import Image


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "outputs"
)

CROP_DIR = os.path.join(
    OUTPUT_DIR,
    "crops"
)

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)

os.makedirs(
    CROP_DIR,
    exist_ok=True
)


# ============================================================
# GLOBAL MODEL VARIABLES
# ============================================================

ocr = None
processor = None
model = None
device = None

_models_loaded = False


# ============================================================
# LOAD MODELS ONCE
# ============================================================

def load_ocr_models():

    global ocr
    global processor
    global model
    global device
    global _models_loaded

    if _models_loaded:

        print(
            "✅ OCR models already loaded.",
            flush=True
        )

        return

    print(
        "=" * 70,
        flush=True
    )

    print(
        "🧠 LOADING OCR MODELS",
        flush=True
    )

    print(
        "=" * 70,
        flush=True
    )

    # ========================================================
    # PADDLEOCR
    # ========================================================

    if ocr is None:

        print(
            "🔄 Loading PaddleOCR...",
            flush=True
        )

        from paddleocr import PaddleOCR

        ocr = PaddleOCR(
            lang="en",
            use_textline_orientation=True
        )

        print(
            "✅ PaddleOCR loaded.",
            flush=True
        )

    # ========================================================
    # TROCR
    # ========================================================

    if processor is None or model is None:

        print(
            "🔄 Loading TrOCR base handwritten model...",
            flush=True
        )

        import torch

        from transformers import (
            TrOCRProcessor,
            VisionEncoderDecoderModel
        )

        MODEL_NAME = (
            "microsoft/trocr-base-handwritten"
        )

        processor = TrOCRProcessor.from_pretrained(
            MODEL_NAME
        )

        model = VisionEncoderDecoderModel.from_pretrained(
            MODEL_NAME
        )

        device = (
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        model.to(device)

        model.eval()

        print(
            f"✅ TrOCR loaded on {device}.",
            flush=True
        )

    _models_loaded = True

    print(
        "=" * 70,
        flush=True
    )

    print(
        "✅ ALL OCR MODELS LOADED",
        flush=True
    )

    print(
        "=" * 70,
        flush=True
    )


# ============================================================
# VALIDATE CROP
# ============================================================

def is_valid_crop(crop):

    if crop is None:

        return False

    h, w = crop.shape[:2]

    return (
        h > 15
        and
        w > 15
    )


# ============================================================
# MAIN OCR
# ============================================================

def main(
    image_path,
    save_debug=True
):

    # ========================================================
    # LOAD MODELS
    # ========================================================

    load_ocr_models()

    # ========================================================
    # ABSOLUTE PATH
    # ========================================================

    image_path = os.path.abspath(
        image_path
    )

    print(
        f"🧠 OCR reading: {image_path}",
        flush=True
    )

    # ========================================================
    # CHECK FILE
    # ========================================================

    if not os.path.exists(
        image_path
    ):

        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    # ========================================================
    # READ IMAGE
    # ========================================================

    img = cv2.imread(
        image_path
    )

    if img is None:

        raise ValueError(
            f"OpenCV failed to read: {image_path}"
        )

    debug_img = img.copy()

    # ========================================================
    # PADDLEOCR DETECTION
    # ========================================================

    print(
        "🔍 Running PaddleOCR text detection...",
        flush=True
    )

    results = ocr.predict(
        img
    )

    boxes = []

    for page in results:

        if "dt_polys" not in page:

            continue

        for poly in page["dt_polys"]:

            boxes.append(
                poly
            )

    print(
        f"📦 Detected {len(boxes)} text regions.",
        flush=True
    )

    # ========================================================
    # NO TEXT
    # ========================================================

    if not boxes:

        return "⚠️ No text detected"

    # ========================================================
    # OCR EACH REGION
    # ========================================================

    lines = []

    crop_id = 0

    import torch

    for index, poly in enumerate(boxes):

        print(
            f"📝 Processing region "
            f"{index + 1}/{len(boxes)}...",
            flush=True
        )

        pts = np.array(
            poly,
            np.int32
        )

        x, y, w, h = cv2.boundingRect(
            pts
        )

        # ----------------------------------------------------
        # Keep coordinates inside image
        # ----------------------------------------------------

        x = max(
            0,
            x
        )

        y = max(
            0,
            y
        )

        w = min(
            w,
            img.shape[1] - x
        )

        h = min(
            h,
            img.shape[0] - y
        )

        crop = img[
            y:y+h,
            x:x+w
        ]

        if not is_valid_crop(
            crop
        ):

            continue

        # ====================================================
        # SAVE CROP
        # ====================================================

        crop_path = os.path.join(
            CROP_DIR,
            f"crop_{crop_id}.jpg"
        )

        cv2.imwrite(
            crop_path,
            crop
        )

        crop_id += 1

        # ====================================================
        # CONVERT TO PIL
        # ====================================================

        pil_img = Image.fromarray(
            cv2.cvtColor(
                crop,
                cv2.COLOR_BGR2RGB
            )
        ).convert(
            "RGB"
        )

        # ====================================================
        # PROCESS IMAGE
        # ====================================================

        pixel_values = processor(
            images=pil_img,
            return_tensors="pt"
        ).pixel_values.to(
            device
        )

        # ====================================================
        # TROCR
        # ====================================================

        with torch.no_grad():

            ids = model.generate(
                pixel_values,
                max_length=128
            )

        text = processor.batch_decode(
            ids,
            skip_special_tokens=True
        )[0].strip()

        # ====================================================
        # SAVE TEXT
        # ====================================================

        if text:

            lines.append(
                text
            )

            print(
                f"   ✓ {text}",
                flush=True
            )

        # ====================================================
        # DEBUG BOX
        # ====================================================

        cv2.rectangle(
            debug_img,
            (x, y),
            (x + w, y + h),
            (0, 255, 0),
            2
        )

    # ========================================================
    # SAVE DEBUG IMAGE
    # ========================================================

    if save_debug:

        debug_path = os.path.join(
            OUTPUT_DIR,
            "debug_boxes.jpg"
        )

        cv2.imwrite(
            debug_path,
            debug_img
        )

        print(
            f"🖼 Debug image saved: {debug_path}",
            flush=True
        )

    # ========================================================
    # RESULT
    # ========================================================

    if not lines:

        return "⚠️ No readable text detected"

    return "\n".join(
        lines
    )


# ============================================================
# FLASK WRAPPER
# ============================================================

def run_ocr(image_path):

    return main(
        image_path,
        save_debug=True
    )


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    result = run_ocr(
        "uploads/test.jpg"
    )

    print(
        "\n========== OCR RESULT ==========\n"
    )

    print(
        result
    )