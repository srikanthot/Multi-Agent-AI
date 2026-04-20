#!/bin/sh
# Azure App Service startup script for the FastAPI backend.
# Set as the Startup Command in App Service → Configuration → General settings.
 
cd /home/site/wwwroot
 
# Install dependencies if not already present
pip install --no-cache-dir -r requirements.txt
 
# Start the app with gunicorn + uvicorn workers
gunicorn main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile -
 
 