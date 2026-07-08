from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any

class ImageMetadata(BaseModel):
    image_id: str
    source_document: str
    page: int
    filename: str
    width: float
    height: float

class ObservationBase(BaseModel):
    observation_id: str
    location: str
    issue: str
    engineering_finding: Optional[str] = ""
    measurements: Optional[str] = None
    moisture: Optional[str] = None
    crack_width: Optional[str] = None
    temperatures: Optional[str] = None
    inspector_notes: Optional[str] = None
    supporting_images: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None
    root_cause: Optional[str] = None
    severity: Optional[str] = None
    severity_reason: Optional[str] = None
    supporting_documents: List[str] = Field(default_factory=list)
    page_numbers: List[int] = Field(default_factory=list)
    confidence_score: Optional[float] = None

class Conflict(BaseModel):
    conflict: bool = True
    reason: str
    documents_involved: List[str]
    recommended_manual_verification: str

class Recommendation(BaseModel):
    issue: str
    recommendation: str
    severity: str
    confidence: str

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence_to_str(cls, v):
        """Gemini sometimes returns confidence as a float (0.0-1.0). Convert to label."""
        if isinstance(v, (float, int)):
            if v >= 0.8:
                return "High"
            elif v >= 0.5:
                return "Medium"
            else:
                return "Low"
        return str(v)

class SeverityInfo(BaseModel):
    severity: str # Critical, High, Medium, Low
    reason: str
    confidence: str

class DDROutput(BaseModel):
    property_summary: Dict[str, Any] = Field(default_factory=dict)
    observations: List[ObservationBase] = Field(default_factory=list)
    conflicts: List[Conflict] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    validation: Dict[str, Any] = Field(default_factory=dict)
