"""
IVACS V-TRACE Server Runner
Convenient entrypoint to run the FastAPI server directly via Python:
    python run_server.py
"""

import uvicorn

if __name__ == "__main__":
    print("Starting IVACS V-TRACE Backend Server on http://0.0.0.0:8000 ...")
    print("API Documentation: http://localhost:8000/docs")
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=False)
