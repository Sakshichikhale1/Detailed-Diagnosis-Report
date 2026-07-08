import pdfplumber
from pypdf import PdfReader
from PIL import Image
import io
import os
import base64
import logging

logger = logging.getLogger(__name__)

MIN_IMAGE_DIMENSION = 60
MIN_IMAGE_BYTES = 1024


def parse_pdf(file_path: str) -> list:
    """
    Parses a PDF file and extracts text page by page using pdfplumber,
    and extracts images (as base64, for multimodal AI calls) using pypdf.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    pages_data = []

    try:
        reader = PdfReader(file_path)
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""

                # Extract images using pypdf, decoding through PIL so the
                # actual image format is known (not assumed) and the bytes
                # are always a valid, standalone image regardless of the
                # PDF's internal filter/encoding.
                page_images = []
                if i < len(reader.pages):
                    pypdf_page = reader.pages[i]
                    count = 0
                    for image_file_object in pypdf_page.images:
                        try:
                            pil_img = image_file_object.image
                            if pil_img is None:
                                continue

                            width, height = pil_img.size
                            if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
                                continue

                            save_format = "PNG"
                            if pil_img.mode in ("CMYK", "YCbCr"):
                                pil_img = pil_img.convert("RGB")
                                save_format = "JPEG"
                            elif pil_img.mode in ("P", "1"):
                                pil_img = pil_img.convert("RGB")

                            buf = io.BytesIO()
                            save_kwargs = {"quality": 90} if save_format == "JPEG" else {}
                            pil_img.save(buf, format=save_format, **save_kwargs)
                            img_bytes = buf.getvalue()

                            if len(img_bytes) < MIN_IMAGE_BYTES:
                                continue

                            b64_str = base64.b64encode(img_bytes).decode("utf-8")
                            page_images.append({
                                "image_index": count,
                                "base64": b64_str,
                                "ext": "jpg" if save_format == "JPEG" else "png",
                                "width": width,
                                "height": height,
                            })
                            count += 1
                        except Exception as img_err:
                            logger.warning(
                                f"Skipping unreadable image on page {i + 1} of {file_path}: {img_err}"
                            )
                            continue

                pages_data.append({
                    "page_number": i + 1,
                    "text": text.strip(),
                    "images": page_images,
                })
    except Exception as e:
        logger.exception(f"Failed to parse PDF {file_path}: {e}")
        raise

    return pages_data
