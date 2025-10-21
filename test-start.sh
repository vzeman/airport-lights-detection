#!/bin/bash
# Quick test to see if we can install dependencies
cd /Users/viktorzeman/work/airport-lights-detection/backend
source venv/bin/activate
echo "Testing pip install..."
pip install --upgrade pip
echo "Installing requirements..."
pip install -r requirements.txt
echo "Success!"
