import os
import json
import logging
import traceback
from fastapi import APIRouter, HTTPException
from schemas.ddr import DDROutput
from config import settings

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
from services.pdf_parser import parse_pdf
from services.image_extractor import extract_images_from_pdf
from services.engine import (
    extract_observations,
    extract_thermal_findings,
    merge_reports,
    detect_conflicts,
    process_severity_and_recommendations,
    generate_property_summary,
    detect_missing_information,
    link_images_to_observations
)
from services.validation import validate_report

router = APIRouter()

# Global memory to store the last generated report so /report can serve it.
# In production, use a database.
latest_report_data = {}

@router.post("/process", response_model=DDROutput)
async def process_reports():
    """
    Runs the complete AI pipeline.
    """
    inspection_path = os.path.join(settings.OUTPUT_DIR, "inspection_report.pdf")
    thermal_path = os.path.join(settings.OUTPUT_DIR, "thermal_report.pdf")
    
    if not os.path.exists(inspection_path) or not os.path.exists(thermal_path):
        raise HTTPException(status_code=400, detail="Missing uploaded reports. Please upload them first.")

    try:
        # 1. Parse PDFs
        insp_pages = parse_pdf(inspection_path)
        therm_pages = parse_pdf(thermal_path)
        
        # 2. Extract Images
        insp_images = extract_images_from_pdf(inspection_path, "inspection")
        therm_images = extract_images_from_pdf(thermal_path, "thermal")
        
        # 3. Extract Observations via Gemini
        insp_obs = extract_observations(insp_pages)
        therm_obs = extract_thermal_findings(therm_pages)
        
        # 4. Merge
        merged_obs = merge_reports(insp_obs, therm_obs)
        
        # 5. Severity and Recommendations
        sev_rec = process_severity_and_recommendations(merged_obs)
        final_observations = sev_rec.get("observations", merged_obs)
        recommendations = sev_rec.get("recommendations", [])
        
        # 6. Detect Conflicts & Missing Info
        conflicts = detect_conflicts(final_observations)
        missing_info = detect_missing_information(final_observations)
        
        # 7. Generate Property Summary
        property_summary = generate_property_summary(insp_pages, therm_pages)
        
        # 8. Link Images
        final_observations = link_images_to_observations(
            final_observations, insp_images, therm_images, insp_pages, therm_pages
        )
        
        # Assemble DDR Output
        report_data = {
            "property_summary": property_summary,
            "observations": final_observations,
            "conflicts": conflicts,
            "missing_information": missing_info,
            "recommendations": recommendations,
            "statistics": {
                "total_observations": len(final_observations),
                "total_images": len(insp_images) + len(therm_images)
            }
        }
        
        # 9. Validation
        validation = validate_report(report_data)
        report_data["validation"] = validation
        
        if not validation["is_valid"]:
            # Depending on strictness, we could raise error or just flag it
            pass
            
        global latest_report_data
        latest_report_data = report_data
        
        return DDROutput(**report_data)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report", response_model=DDROutput)
async def get_report():
    if not latest_report_data:
        raise HTTPException(status_code=404, detail="No report has been processed yet.")
    return DDROutput(**latest_report_data)
