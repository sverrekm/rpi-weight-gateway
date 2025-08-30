#!/usr/bin/env python3
import os
import sys
import traceback

# Set environment variables for demo mode
os.environ['DEMO_MODE'] = 'true'
os.environ['MQTT_HOST'] = 'localhost'
os.environ['MQTT_PORT'] = '1883'

print("Testing weightd service startup...")
print(f"Python version: {sys.version}")
print(f"DEMO_MODE: {os.environ.get('DEMO_MODE')}")

try:
    # Change to the weightd directory
    weightd_path = os.path.join(os.path.dirname(__file__), 'services', 'weightd')
    sys.path.insert(0, weightd_path)
    
    print(f"Adding to path: {weightd_path}")
    
    # Try to import the app
    from app.main import app
    print("✓ Successfully imported app")
    
    # Try to start uvicorn
    import uvicorn
    print("✓ Uvicorn imported")
    
    print("Starting server on http://0.0.0.0:8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    
except Exception as e:
    print(f"✗ Error: {e}")
    print("Full traceback:")
    traceback.print_exc()
