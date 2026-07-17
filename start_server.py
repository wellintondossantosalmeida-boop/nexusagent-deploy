#!/usr/bin/env python3
import uvicorn
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from main import app

if __name__ == "__main__":
    print("Starting NexusAgent AI on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
