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
# LAZY MODEL VARIABLES
# ============================================================

ocr = None
processor = None
model = None
device = None


# ============================================================
# LOAD OCR MODELS ONLY WHEN NEEDED
# ============================================================

def load_ocr_models():

    global ocr
    global processor
    global model
    global device

    # --------------------------------------------------------
    # PaddleOCR
    # --------------------------------------------------------

    if ocr is None:

        print(
            "🔄 Loading PaddleOCR for the first OCR request..."
        )

        from paddleocr import PaddleOCR

        ocr = PaddleOCR(
            lang="en",
            use_textline_orientation=True
        )

        print(
            "✅ PaddleOCR loaded."
        )

    # --------------------------------------------------------
    # TrOCR
    # --------------------------------------------------------

    if processor is None or model is None:

        print(
            "🔄 Loading TrOCR for the first OCR request..."
        )

        import torch

        from transformers import (
            TrOCRProcessor,
            VisionEncoderDecoderModel
        )

        processor = TrOCRProcessor.from_pretrained(
            "microsoft/trocr-large-handwritten"
        )

        model = VisionEncoderDecoderModel.from_pretrained(
            "microsoft/trocr-large-handwritten"
        )

        device = (
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        model.to(device)
        model.eval()

        print(
            f"✅ TrOCR loaded on {device}."
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

    # --------------------------------------------------------
    # Load models ONLY now
    # --------------------------------------------------------

    load_ocr_models()

    # --------------------------------------------------------
    # Absolute path
    # --------------------------------------------------------

    image_path = os.path.abspath(
        image_path
    )

    print(
        "🧠 OCR reading:",
        image_path
    )

    # --------------------------------------------------------
    # Validate file
    # --------------------------------------------------------

    if not os.path.exists(
        image_path
    ):

        raise ValueError(
            f"❌ Image not found: {image_path}"
        )

    # --------------------------------------------------------
    # Read image
    # --------------------------------------------------------

    img = cv2.imread(
        image_path
    )

    if img is None:

        raise ValueError(
            f"❌ OpenCV failed to read: {image_path}"
        )

    debug_img = img.copy()

    # --------------------------------------------------------
    # PaddleOCR detection
    # --------------------------------------------------------

    results = ocr.predict(
        img
    )

    boxes = []

    for page in results:

        for poly in page["dt_polys"]:

            boxes.append(
                poly
            )

    if not boxes:

        return [
            "⚠️ No text detected"
        ]

    # --------------------------------------------------------
    # OCR each detected region
    # --------------------------------------------------------

    lines = []

    crop_id = 0

    for poly in boxes:

        pts = np.array(
            poly,
            np.int32
        )

        x, y, w, h = cv2.boundingRect(
            pts
        )

        crop = img[
            y:y+h,
            x:x+w
        ]

        if not is_valid_crop(
            crop
        ):

            continue

        # ----------------------------------------------------
        # Save crop
        # ----------------------------------------------------

        crop_path = os.path.join(
            CROP_DIR,
            f"crop_{crop_id}.jpg"
        )

        cv2.imwrite(
            crop_path,
            crop
        )

        crop_id += 1

        # ----------------------------------------------------
        # TrOCR
        # ----------------------------------------------------

        pil_img = Image.fromarray(
            crop
        ).convert("RGB")

        pixel_values = processor(
            images=pil_img,
            return_tensors="pt"
        ).pixel_values.to(
            device
        )

        import torch

        with torch.no_grad():

            ids = model.generate(
                pixel_values,
                max_length=128
            )

        text = processor.batch_decode(
            ids,
            skip_special_tokens=True
        )[0].strip()

        if text:

            lines.append(
                text
            )

        # ----------------------------------------------------
        # Debug box
        # ----------------------------------------------------

        cv2.rectangle(
            debug_img,
            (x, y),
            (x + w, y + h),
            (0, 255, 0),
            2
        )

    # --------------------------------------------------------
    # Save debug image
    # --------------------------------------------------------

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
            "🖼 Debug boxes saved:",
            debug_path
        )

    return lines


# ============================================================
# FLASK WRAPPER
# ============================================================

def run_ocr(image_path):

    lines = main(
        image_path,
        save_debug=True
    )

    return "\n".join(
        lines
    )


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    print(
        run_ocr(
            "uploads/test.jpg"
        )
    )