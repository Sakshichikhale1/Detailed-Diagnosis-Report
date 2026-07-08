from fastapi import APIRouter, UploadFile, File
import os
from config import settings

router = APIRouter()

@router.post("/upload")
async def upload_files(
    inspection_report: UploadFile = File(...),
    thermal_report: UploadFile = File(...)
):
    """
    Accepts inspection_report.pdf and thermal_report.pdf
    Saves them to disk for processing.
    """
    inspection_path = os.path.join(settings.OUTPUT_DIR, "inspection_report.pdf")
    thermal_path = os.path.join(settings.OUTPUT_DIR, "thermal_report.pdf")
    
    with open(inspection_path, "wb") as buffer:
        buffer.write(await inspection_report.read())
        
    with open(thermal_path, "wb") as buffer:
        buffer.write(await thermal_report.read())
        
    return {"status": "success", "message": "Files uploaded successfully"}
