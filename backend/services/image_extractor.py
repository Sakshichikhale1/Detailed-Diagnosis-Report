import os
import uuid
import logging
from pypdf import PdfReader
from PIL import Image
from schemas.ddr import ImageMetadata
from config import settings

logger = logging.getLogger(__name__)

# Ignore tiny images (logos, bullets, icons) that add noise but no diagnostic value.
MIN_IMAGE_DIMENSION = 60
MIN_IMAGE_BYTES = 1024


def extract_images_from_pdf(file_path: str, doc_type: str) -> list:
    """
    Extracts all significant images from a PDF and saves them as standalone
    files in the static directory.

    Uses pypdf's decoded PIL representation (`ImageFile.image`) rather than the
    raw stream bytes (`ImageFile.data`), because raw bytes are only a valid
    standalone image file for a subset of PDF filters (plain DCT/Flate RGB).
    Images encoded with other filters (CCITT, indexed color, JPX, CMYK, etc.)
    are not directly viewable/openable if written as-is. Going through PIL
    guarantees every extracted file is a valid, viewable PNG/JPEG regardless
    of how the source PDF encoded it — this is what makes the pipeline work
    on arbitrary inspection/thermal reports, not just one sample file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    extracted_images = []
    os.makedirs(settings.STATIC_DIR, exist_ok=True)

    try:
        reader = PdfReader(file_path)
        for page_num, page in enumerate(reader.pages):
            for image_file_object in page.images:
                try:
                    pil_img = image_file_object.image
                    if pil_img is None:
                        continue

                    width, height = pil_img.size
                    if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
                        continue  # skip icons/bullets/decorative artifacts

                    # Normalize mode for saving (CMYK/paletted -> RGB) and pick format.
                    save_format = "PNG"
                    if pil_img.mode in ("CMYK", "YCbCr"):
                        pil_img = pil_img.convert("RGB")
                        save_format = "JPEG"
                    elif pil_img.mode == "P":
                        pil_img = pil_img.convert("RGB")
                    elif pil_img.mode == "1":
                        pil_img = pil_img.convert("L")

                    ext = "jpg" if save_format == "JPEG" else "png"
                    image_id = str(uuid.uuid4())
                    filename = f"{doc_type}_page{page_num + 1}_{image_id}.{ext}"
                    filepath = os.path.join(settings.STATIC_DIR, filename)

                    save_kwargs = {"quality": 90} if save_format == "JPEG" else {}
                    pil_img.save(filepath, format=save_format, **save_kwargs)

                    if os.path.getsize(filepath) < MIN_IMAGE_BYTES:
                        os.remove(filepath)
                        continue

                    metadata = ImageMetadata(
                        image_id=image_id,
                        source_document=doc_type,
                        page=page_num + 1,
                        filename=filename,
                        width=float(width),
                        height=float(height),
                    )
                    extracted_images.append(metadata)

                except Exception as img_err:
                    # A single unreadable/corrupt image should never fail the
                    # whole extraction pass — skip it and keep going.
                    logger.warning(
                        f"Skipping unreadable image on page {page_num + 1} of {file_path}: {img_err}"
                    )
                    continue

    except Exception as e:
        logger.exception(f"Failed to extract images from {file_path}: {e}")
        raise

    return extracted_images
