import json
import logging
from services.groq_service import call_gemini, call_gemini_multimodal
from prompts.ddr_prompts import (
    OBSERVATION_EXTRACTION_PROMPT,
    THERMAL_EXTRACTION_PROMPT,
    MERGE_OBSERVATIONS_PROMPT,
    CONFLICT_DETECTION_PROMPT,
    SEVERITY_AND_RECOMMENDATION_PROMPT,
    PROPERTY_SUMMARY_PROMPT,
    MISSING_INFO_PROMPT,
    IMAGE_ANALYSIS_PROMPT,
)

logger = logging.getLogger(__name__)

# Max images per multimodal call (to avoid token limits)
MAX_IMAGES_PER_CALL = 5


def extract_observations(pages_data: list) -> list:
    """
    Extracts observations from inspection report pages.
    Uses multimodal Gemini if images are available on the page.
    """
    full_text = "\n".join([f"Page {p['page_number']}:\n{p['text']}" for p in pages_data])
    prompt = OBSERVATION_EXTRACTION_PROMPT.format(text=full_text)

    # Gather page images for multimodal analysis
    all_images = []
    for p in pages_data:
        for img in p.get("images", []):
            all_images.append(img)

    if all_images:
        # Use multimodal call with up to MAX_IMAGES_PER_CALL images
        imgs_to_use = all_images[:MAX_IMAGES_PER_CALL]
        result = call_gemini_multimodal(prompt, imgs_to_use)
    else:
        result = call_gemini(prompt)

    return result if isinstance(result, list) else []


def extract_thermal_findings(pages_data: list) -> list:
    """
    Extracts thermal findings from thermal report pages.
    Uses multimodal Gemini if images are available.
    """
    full_text = "\n".join([f"Page {p['page_number']}:\n{p['text']}" for p in pages_data])
    prompt = THERMAL_EXTRACTION_PROMPT.format(text=full_text)

    all_images = []
    for p in pages_data:
        for img in p.get("images", []):
            all_images.append(img)

    if all_images:
        imgs_to_use = all_images[:MAX_IMAGES_PER_CALL]
        result = call_gemini_multimodal(prompt, imgs_to_use)
    else:
        result = call_gemini(prompt)

    return result if isinstance(result, list) else []


def merge_reports(inspection_obs: list, thermal_obs: list) -> list:
    """Merges inspection and thermal observations, deduplicating by location+issue."""
    prompt = MERGE_OBSERVATIONS_PROMPT.format(
        inspection_obs=json.dumps(inspection_obs),
        thermal_obs=json.dumps(thermal_obs)
    )
    result = call_gemini(prompt)
    return result if isinstance(result, list) else []


def detect_conflicts(merged_obs: list) -> list:
    """Detects conflicting information between inspection and thermal data."""
    prompt = CONFLICT_DETECTION_PROMPT.format(observations=json.dumps(merged_obs))
    result = call_gemini(prompt)
    return result if isinstance(result, list) else []


def process_severity_and_recommendations(merged_obs: list) -> dict:
    """Assigns severity levels and generates actionable recommendations."""
    prompt = SEVERITY_AND_RECOMMENDATION_PROMPT.format(observations=json.dumps(merged_obs))
    result = call_gemini(prompt)
    return result if isinstance(result, dict) else {"observations": merged_obs, "recommendations": []}


def generate_property_summary(insp_pages: list, therm_pages: list) -> dict:
    """
    Uses Gemini to generate a structured property issue summary from both reports.
    """
    insp_text = "\n".join([f"Page {p['page_number']}:\n{p['text']}" for p in insp_pages])
    therm_text = "\n".join([f"Page {p['page_number']}:\n{p['text']}" for p in therm_pages])

    prompt = PROPERTY_SUMMARY_PROMPT.format(
        inspection_text=insp_text[:6000],  # Limit to avoid token overflow
        thermal_text=therm_text[:3000],
    )
    result = call_gemini(prompt)
    if isinstance(result, dict):
        return result
    return {"status": "Processed", "overall_condition": "Not Available"}


def detect_missing_information(merged_obs: list) -> list:
    """
    Uses Gemini to identify missing, unclear, or unavailable information in the report.
    """
    prompt = MISSING_INFO_PROMPT.format(observations=json.dumps(merged_obs))
    result = call_gemini(prompt)
    return result if isinstance(result, list) else []


def link_images_to_observations(
    observations: list,
    insp_images: list,
    therm_images: list,
    insp_pages: list,
    therm_pages: list,
) -> list:
    """
    Links extracted images to their most relevant observations.
    Strategy:
    1. For each observation, find images on the same page from its supporting documents
    2. Use AI (multimodal) to confirm the match if images are available
    3. Fall back to page-proximity matching if no AI match found
    Returns the observations list with supporting_images populated.
    """
    # Build page → images maps
    insp_page_map: dict[int, list] = {}
    for img_meta in insp_images:
        page = img_meta.page
        insp_page_map.setdefault(page, []).append(img_meta)

    therm_page_map: dict[int, list] = {}
    for img_meta in therm_images:
        page = img_meta.page
        therm_page_map.setdefault(page, []).append(img_meta)

    # Build page → base64 images maps (for AI analysis)
    insp_b64_map: dict[int, list] = {}
    for p in insp_pages:
        if p.get("images"):
            insp_b64_map[p["page_number"]] = p["images"]

    therm_b64_map: dict[int, list] = {}
    for p in therm_pages:
        if p.get("images"):
            therm_b64_map[p["page_number"]] = p["images"]

    # Simple page-proximity linking (primary strategy)
    for obs in observations:
        supporting_imgs = []
        page_nums = obs.get("page_numbers", [])
        supporting_docs = obs.get("supporting_documents", [])

        for page_num in page_nums:
            # Link inspection images if observation is from inspection report
            if any("inspection" in d.lower() for d in supporting_docs):
                if page_num in insp_page_map:
                    for img_meta in insp_page_map[page_num]:
                        if img_meta.filename not in supporting_imgs:
                            supporting_imgs.append(img_meta.filename)

            # Link thermal images if observation is from thermal report
            if any("thermal" in d.lower() for d in supporting_docs):
                if page_num in therm_page_map:
                    for img_meta in therm_page_map[page_num]:
                        if img_meta.filename not in supporting_imgs:
                            supporting_imgs.append(img_meta.filename)

        obs["supporting_images"] = supporting_imgs[:4]  # Cap at 4 images per observation

    # AI-based refinement: for pages with images, use multimodal Gemini to verify matches
    try:
        _ai_refine_image_links(observations, insp_b64_map, therm_b64_map, insp_page_map, therm_page_map)
    except Exception as e:
        logger.warning(f"AI image linking refinement failed (using page-proximity fallback): {e}")

    return observations


def _ai_refine_image_links(
    observations: list,
    insp_b64_map: dict,
    therm_b64_map: dict,
    insp_page_map: dict,
    therm_page_map: dict,
):
    """
    Uses Gemini vision to verify or correct image-to-observation links.
    Only runs if there are images to analyze.
    """
    # Collect all pages that have images
    pages_with_images = list(set(list(insp_b64_map.keys()) + list(therm_b64_map.keys())))

    if not pages_with_images or not observations:
        return

    obs_summary = [{"observation_id": o.get("observation_id"), "location": o.get("location"), "issue": o.get("issue")} for o in observations]

    for page_num in pages_with_images[:3]:  # Limit to 3 pages for performance
        images_on_page = []
        doc_type = "inspection report"
        page_map = insp_page_map

        if page_num in insp_b64_map:
            images_on_page = insp_b64_map[page_num][:3]
            doc_type = "inspection report"
            page_map = insp_page_map
        elif page_num in therm_b64_map:
            images_on_page = therm_b64_map[page_num][:3]
            doc_type = "thermal report"
            page_map = therm_page_map

        if not images_on_page:
            continue

        prompt = IMAGE_ANALYSIS_PROMPT.format(
            page_num=page_num,
            doc_type=doc_type,
            observations_json=json.dumps(obs_summary)
        )

        try:
            ai_result = call_gemini_multimodal(prompt, images_on_page)
            if not isinstance(ai_result, list):
                continue

            # Get image filenames for this page
            page_img_metas = page_map.get(page_num, [])

            for i, match in enumerate(ai_result):
                matched_obs_id = match.get("matched_observation_id")
                if not matched_obs_id or i >= len(page_img_metas):
                    continue

                # Find the matched observation and assign image
                for obs in observations:
                    if obs.get("observation_id") == matched_obs_id:
                        img_filename = page_img_metas[i].filename
                        if img_filename not in obs.get("supporting_images", []):
                            obs.setdefault("supporting_images", []).append(img_filename)
                        break

        except Exception as e:
            logger.warning(f"AI image analysis for page {page_num} failed: {e}")
