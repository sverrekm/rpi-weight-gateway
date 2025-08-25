#!/bin/bash
# Build script for the React frontend
# Run this on your development machine before deploying to Raspberry Pi

set -e

echo "Building React frontend..."
cd services/webui
npm install
npm run build
echo "Frontend build complete! The dist/ folder is ready for deployment."
