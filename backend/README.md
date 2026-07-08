# DDR Intelligence Portal - Backend

The complete backend architecture is implemented in the `backend/` directory using FastAPI.

## Structure
- `backend/app.py`: Main FastAPI entrypoint
- `backend/config.py`: Configuration and Environment variables
- `backend/api/`: Contains route definitions (`upload.py`, `process.py`, `export.py`)
- `backend/schemas/ddr.py`: Pydantic models for structured output
- `backend/prompts/ddr_prompts.py`: Prompts used for Gemini
- `backend/services/`: 
  - `pdf_parser.py`: PDF extraction
  - `image_extractor.py`: Image extraction
  - `gemini_service.py`: Calling Gemini API with JSON structure
  - `engine.py`: Core AI logic (observation extraction, merging, conflict detection, etc.)
  - `validation.py`: Result validation
  - `report_generator.py`: Exporting to PDF/DOCX

## How to run
1. Navigate to the `backend/` directory.
2. Ensure you have `GEMINI_API_KEY` set in your environment variables.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the server:
   ```bash
   uvicorn app:app --reload --port 8000
   ```

The frontend `vite.config.ts` has been configured to proxy `/api` requests to `http://localhost:8000`. You can now replace the mocked data imports with `fetch("/api/process", ...)` calls in your React components.
