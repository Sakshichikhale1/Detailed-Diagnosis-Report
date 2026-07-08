# Detailed Diagnosis Report (DDR) Intelligence Portal

The DDR Intelligence Portal is an AI-powered full-stack application that analyzes and compares inspection and thermal reports (PDFs) to automatically extract observations, identify conflicts, and generate actionable recommendations.

## Project Architecture

This project is built using:
- **Frontend:** Vanilla HTML, CSS, and JavaScript.
- **Backend:** Python FastAPI for efficient and scalable API endpoints.
- **AI Integration:** Google Gemini API for PDF parsing, image extraction, and intelligent analysis.

### Directory Structure

- `frontend/`: Contains the static frontend files (`index.html`, `app.js`, `style.css`).
- `backend/`: Contains the FastAPI application.
  - `backend/app.py`: Main FastAPI entrypoint.
  - `backend/api/`: API route definitions (`upload.py`, `process.py`, `export.py`).
  - `backend/services/`: Core logic including PDF extraction, Gemini API interaction, and report generation.
- `vercel.json`: Configuration for deploying to Vercel.
- `requirements.txt`: Python dependencies.

## Local Setup

### Prerequisites
- Python 3.9+
- A Google Gemini API Key

### Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd "Detailed Diagnosis Report"
   ```

2. **Set up environment variables:**
   Create a `.env` file in the `backend/` directory and add your API keys:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   GROQ_API_KEY=your_groq_api_key_here  # If applicable
   ```

3. **Install backend dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the backend server:**
   Start the FastAPI server from the root directory:
   ```bash
   python -m uvicorn backend.app:app --reload --port 8000
   ```

5. **Run the frontend:**
   Serve the `frontend/` directory using any local web server. For example, using Python:
   ```bash
   python -m http.server 8080 --directory frontend
   ```
   Then open `http://localhost:8080` in your browser.

## Deployment (Vercel)

This project is fully configured for deployment on [Vercel](https://vercel.com).

1. Push your code to a GitHub repository.
2. Import the repository in Vercel.
3. Vercel will automatically detect the `vercel.json` configuration and build both the frontend and the Python serverless backend.
4. **Important:** Add your `GEMINI_API_KEY` (and `GROQ_API_KEY`) to the **Environment Variables** section in your Vercel Project Settings.

The `vercel.json` file automatically handles routing `/api/*` to the FastAPI backend and serving the static frontend for all other routes.
