"""
Simple static file server for the frontend
Serves the frontend files alongside the API
"""
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn

# Import the existing API app
from polymarket_mm_bot.control_tower.api_server import app as api_app

# Create main app
app = FastAPI(title="Polymarket MM Bot Control Tower with Frontend")

# Add all the routes from the API app directly to the main app
# This copies all routes from api_app to app
for route in api_app.routes:
    app.routes.append(route)

# Serve static files from frontend directory
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")
if os.path.exists(frontend_dir):
    # Mount static files at /static path to avoid conflicts
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    # Serve the main index.html at root
    @app.get("/")
    async def read_root():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

    # Handle other frontend routes by serving index.html (for SPA)
    @app.get("/{full_path:path}")
    async def read_frontend(full_path: str):
        # Check if it's an API route first
        if full_path.startswith("stats") or full_path.startswith("history") or \
           full_path.startswith("control") or full_path.startswith("config") or \
           full_path.startswith("api/") or full_path.startswith("api-orders") or \
           full_path.startswith("api-transactions") or full_path.startswith("api-market") or \
           full_path.startswith("api-pnl") or full_path.startswith("api-analytics"):
            # This should be handled by the existing API routes
            # Return 404 to let the API handle it properly
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")

        # For all other paths, serve the frontend
        return FileResponse(os.path.join(frontend_dir, "index.html"))
else:
    @app.get("/")
    def read_root():
        return {"message": "Polymarket MM Bot Control Tower API is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)