#!/usr/bin/env python
"""Test script to debug model loading"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from app.models.airport import Airport
from sqlalchemy import inspect

# Get the column types
for col in Airport.__table__.columns:
    print(f"{col.name}: {col.type}")