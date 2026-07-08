def validate_report(report_data: dict) -> dict:
    """
    Validates the generated report data to ensure it meets requirements:
    - No duplicate observation IDs
    - Confidence scores are present
    - Non-empty recommendations
    """
    validation_results = {
        "is_valid": True,
        "errors": []
    }
    
    seen_ids = set()
    for obs in report_data.get("observations", []):
        obs_id = obs.get("observation_id")
        if not obs_id:
            validation_results["errors"].append("Missing observation_id")
            validation_results["is_valid"] = False
        elif obs_id in seen_ids:
            validation_results["errors"].append(f"Duplicate observation_id: {obs_id}")
            validation_results["is_valid"] = False
        seen_ids.add(obs_id)
        
        if obs.get("confidence_score") is None:
            validation_results["errors"].append(f"Missing confidence score in {obs_id}")
            validation_results["is_valid"] = False
            
        if not obs.get("root_cause"):
            validation_results["errors"].append(f"Missing root cause in {obs_id}")
            # we might not want to make it totally invalid just for this, but let's log it
            
    if not report_data.get("recommendations"):
        validation_results["errors"].append("Empty recommendations list")
        validation_results["is_valid"] = False
        
    if not report_data.get("property_summary"):
        validation_results["errors"].append("Empty property summary")
        validation_results["is_valid"] = False

    return validation_results
