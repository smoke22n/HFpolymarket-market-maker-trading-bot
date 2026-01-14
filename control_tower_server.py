"""
Main entry point for the Control Tower API Server
Starts the FastAPI server with the background trading bot
"""
import argparse
import uvicorn
import threading
import time
import logging
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from polymarket_mm_bot.control_tower.api_server import app, background_runner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def start_background_bot():
    """Start the trading bot in the background"""
    logger.info("Starting background trading bot...")
    # In a real implementation, you would start the actual trading bot here
    # For now, we'll just ensure the background runner is initialized
    logger.info("Background trading bot initialized")


def main():
    parser = argparse.ArgumentParser(description="Control Tower API Server for Polymarket MM Bot")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (development)")

    args = parser.parse_args()

    logger.info(f"Starting Control Tower API Server on {args.host}:{args.port}")

    # Start the background bot
    start_background_bot()

    # Run the FastAPI server with uvicorn
    uvicorn.run(
        "polymarket_mm_bot.control_tower.api_server_with_frontend:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()