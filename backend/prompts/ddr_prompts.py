OBSERVATION_EXTRACTION_PROMPT = """
You are an expert building/property inspector. Extract ALL observations from the following text parsed from an inspection report.
For each observation, extract:
- observation_id: A unique ID (e.g. "INS-001", "INS-002", etc.)
- location: Where exactly the issue is (e.g. "North Wall, Ground Floor", "Terrace Slab")
- issue: A short client-friendly description of the problem (1-2 sentences)
- engineering_finding: Detailed technical finding as observed by the inspector
- root_cause: The probable cause of this issue (e.g. "Water seepage from defective waterproofing", "Settlement cracks due to soil movement")
- measurements: Any measurements mentioned (crack width, area, depth, etc.)
- moisture: Moisture level if mentioned (None, Mild, Moderate, Severe)
- crack_width: Crack width if mentioned (e.g. "0.3mm", "hairline")
- temperatures: Any temperature data mentioned
- inspector_notes: Any additional notes from the inspector
- reasoning: Why this is considered an issue and what risks it poses
- severity: Your assessment of severity (critical, high, medium, low) based on the finding
- severity_reason: Why you assigned this severity level
- confidence_score: Your confidence in the extraction (0.0 to 1.0)
- supporting_documents: ["Inspection Report"]
- page_numbers: List of page numbers this finding is from

Rules:
- Do NOT invent facts not present in the text
- If a field is not available in the text, use null
- Do not create duplicate observations for the same issue at the same location
- Use simple, client-friendly language for the "issue" field

Return a JSON array of these observation objects. Do NOT include markdown blocks.
Text: {text}
"""

THERMAL_EXTRACTION_PROMPT = """
You are an expert thermographer/thermal imaging analyst. Extract ALL findings from the following thermal inspection report.
For each finding, extract:
- observation_id: A unique ID (e.g. "THR-001", "THR-002", etc.)
- location: Where exactly the thermal anomaly is
- issue: A short client-friendly description of the thermal finding
- engineering_finding: Detailed technical thermal finding
- root_cause: The probable cause indicated by the thermal data (e.g. "Active moisture infiltration causing thermal bridging", "Electrical hotspot due to loose connection")
- temperatures: Temperature readings (e.g. "Surface temp: 45°C, Ambient: 28°C, Delta: 17°C")
- moisture: Moisture presence if indicated by thermal (None, Mild, Moderate, Severe)
- inspector_notes: Any additional notes
- reasoning: Why this thermal anomaly is significant
- severity: Your assessment of severity (critical, high, medium, low)
- severity_reason: Why you assigned this severity level
- confidence_score: Your confidence in the extraction (0.0 to 1.0)
- supporting_documents: ["Thermal Report"]
- page_numbers: List of page numbers this finding is from

Rules:
- Do NOT invent facts not present in the text
- If a field is not available in the text, use null

Return a JSON array of these objects. Do NOT include markdown blocks.
Text: {text}
"""

IMAGE_ANALYSIS_PROMPT = """
You are an expert building inspector analyzing images from an inspection or thermal report.
The following images come from page {page_num} of a {doc_type}.

For each image visible, describe:
1. What the image shows (location, the type of defect or condition visible)
2. Whether it appears to be a visible-light photograph or a thermal/infrared image
3. Any notable defects, cracks, staining, discoloration, hotspots, or cold anomalies visible
4. Which observation (if any from the list below) this image best supports

Observations to match against:
{observations_json}

Return a JSON array of objects, one per image, with keys:
- image_description: What the image shows
- image_type: "photograph" or "thermal"
- visible_defects: List of defects visible
- matched_observation_id: The observation_id this image best matches, or null if no match
- confidence: 0.0 to 1.0

Do NOT include markdown blocks.
"""

MERGE_OBSERVATIONS_PROMPT = """
You are an expert data merger for building inspection reports. You have two lists of observations:
1. From a general visual inspection report
2. From a thermal imaging report

Your task:
- Merge observations that refer to the SAME issue at the SAME location
- When merging, combine: temperatures from thermal, measurements from inspection, notes from both
- Preserve the root_cause from both (combine if different perspectives)
- Do NOT create duplicates for the same location+issue
- Keep observations that only appear in one report (they are still valid)
- For merged items: set supporting_documents to include BOTH source documents

Return a single JSON array of merged observation objects with all fields from both sources.
Each object must have: observation_id, location, issue, engineering_finding, root_cause, measurements, moisture, crack_width, temperatures, inspector_notes, reasoning, severity, severity_reason, confidence_score, supporting_documents, page_numbers

Inspection Observations: {inspection_obs}
Thermal Observations: {thermal_obs}
"""

CONFLICT_DETECTION_PROMPT = """
Analyze the following merged observations which combined data from an inspection report and a thermal report.
Identify any CONFLICTING information between the two sources for the SAME location/issue. Examples of conflicts:
- Inspection says Moisture = Moderate, Thermal says Moisture = Severe
- Inspection says crack is "stable", Thermal shows active moisture infiltration suggesting ongoing movement
- Different severity assessments for the same issue

For each conflict, provide:
- location: Where the conflict is
- reason: Clear description of what conflicts (e.g. "Moisture severity conflict: Inspection Report says 'Moderate' but Thermal Report indicates 'Severe' due to large cold anomaly")
- documents_involved: ["Inspection Report", "Thermal Report"]
- recommended_manual_verification: Specific action the human reviewer should take

Return a JSON array of conflict objects. If no conflicts exist, return [].
Observations: {observations}
"""

SEVERITY_AND_RECOMMENDATION_PROMPT = """
Analyze the following merged observations. For each observation, determine or refine:
1. Severity (critical, high, medium, low) with clear reasoning
2. Specific, actionable recommendations for the client

Severity guidelines:
- critical: Immediate structural risk, safety hazard, or risk of collapse/failure
- high: Significant damage likely to worsen, requires urgent attention within weeks
- medium: Moderate issue that needs attention within months to prevent escalation
- low: Minor issue, monitor or address during routine maintenance

Return a JSON object with two arrays:
1. "observations": The input observations with updated/confirmed severity and severity_reason fields
2. "recommendations": Objects with keys:
   - issue: Short name of the issue
   - recommendation: Clear, actionable client-friendly recommendation
   - severity: Severity level
   - confidence: "High", "Medium", or "Low"
   - priority_order: Integer (1 = most urgent)

IMPORTANT: "confidence" for recommendations MUST be a string label: "High", "Medium", or "Low".
Observations: {observations}
"""

PROPERTY_SUMMARY_PROMPT = """
You are an expert building inspector creating an executive property summary.
Based on the following text from inspection and thermal reports, extract a structured property summary.

Extract:
- property_name: Name or identifier of the property (if mentioned)
- address: Full address of the property (if mentioned)
- property_type: Type of property (e.g. "Residential Apartment", "Commercial Building", "Villa")
- inspection_date: Date of inspection (if mentioned)
- inspector_name: Name of inspector (if mentioned)
- overall_condition: Overall assessment of the property condition (Poor / Fair / Good / Excellent)
- overall_condition_reason: 1-2 sentence explanation of the overall condition
- total_issues_count: Estimated total number of issues found
- critical_issues_count: Number of critical/severe issues
- areas_inspected: List of areas that were inspected (e.g. ["Terrace", "Basement", "Living Room"])
- key_concerns: List of 3-5 most important concerns in client-friendly language

If any field is not available in the text, use null.

Return a JSON object (not array). Do NOT include markdown blocks.

Inspection Report Text: {inspection_text}
Thermal Report Text: {thermal_text}
"""

MISSING_INFO_PROMPT = """
You are a quality assurance specialist reviewing a building inspection DDR (Detailed Diagnostic Report).
Based on the merged observations below, identify what information is MISSING, UNCLEAR, or UNAVAILABLE.

Look for:
- Observations that have no thermal data (temperature readings)
- Observations that have no photographic evidence
- Locations mentioned but not inspected (e.g. "basement mentioned but not assessed")
- Missing measurements (cracks without width, areas without square footage)
- Missing root cause analysis
- Time-sensitive data (e.g. "inspection date not recorded")
- Any standard inspection fields that are blank/null across all observations

For each missing item, provide a clear, client-friendly description such as:
- "Thermal data not available for Kitchen area observations"
- "Crack width measurements not recorded for the North Wall crack"
- "Inspection date not mentioned in either report"

Return a JSON array of strings (each string is one missing information item).
If nothing significant is missing, return [].

Merged Observations: {observations}
"""
