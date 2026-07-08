from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from api import process
from services.report_generator import generate_pdf_report
import os

router = APIRouter()

@router.get("/export/pdf")
async def export_pdf():
    if not process.latest_report_data:
        raise HTTPException(status_code=404, detail="No report generated yet.")
    
    pdf_path = generate_pdf_report(process.latest_report_data)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=500, detail="Failed to generate PDF.")
        
    return FileResponse(path=pdf_path, filename="DDR_Report.pdf", media_type="application/pdf")
