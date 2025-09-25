#!/bin/bash

# ============================================================================
# Airport Light Detection Analysis Pipeline
# ============================================================================
# This script analyzes videos for airport lights (PAPI, runway lights, etc.)
# It processes EVERY FRAME by default for maximum accuracy
# Extracts GPS position data from drone videos when available
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VIDEOS_DIR="videos"
REPORTS_DIR="reports"
VENV_DIR="venv_lights"

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Airport Light Detection Analysis Pipeline         ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: Python 3 is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python: $(python3 --version)"

# Check videos directory
if [ ! -d "$VIDEOS_DIR" ]; then
    echo -e "${YELLOW}Creating videos directory...${NC}"
    mkdir -p "$VIDEOS_DIR"
    echo -e "${YELLOW}⚠️  Please place your video files in the '$VIDEOS_DIR' directory${NC}"
    echo "   Supported formats: .mp4, .MP4, .avi, .mov"
    exit 0
fi

# Count videos
VIDEO_COUNT=$(find "$VIDEOS_DIR" -type f \( -iname "*.mp4" -o -iname "*.avi" -o -iname "*.mov" \) | wc -l)
if [ "$VIDEO_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No video files found in '$VIDEOS_DIR' directory${NC}"
    exit 0
fi

echo -e "${GREEN}✓${NC} Videos: Found $VIDEO_COUNT video file(s)"

# Check/create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
fi

echo -e "${GREEN}✓${NC} Virtual environment: Ready"

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Install/upgrade dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

# Create reports directory
mkdir -p "$REPORTS_DIR"

# Check for GPS extraction capability
GPS_STATUS="${RED}Disabled${NC}"
GPS_FLAG="--no-gps"

if command -v exiftool &> /dev/null; then
    GPS_STATUS="${GREEN}Enabled${NC}"
    GPS_FLAG=""
    echo -e "${GREEN}✓${NC} GPS: exiftool found - will extract drone positions"
else
    echo -e "${YELLOW}⚠️${NC}  GPS: exiftool not found - install with: brew install exiftool"
fi

echo ""
echo -e "${BLUE}Configuration:${NC}"
echo -e "  • Analysis mode: ${GREEN}EVERY FRAME${NC} (best quality)"
echo -e "  • GPS extraction: $GPS_STATUS"
echo -e "  • Input folder: $VIDEOS_DIR/"
echo -e "  • Output folder: $REPORTS_DIR/"
echo ""
echo -e "${BLUE}This will:${NC}"
echo "  1. Analyze every single frame of each video"
echo "  2. Detect and track all lights (PAPI, runway, taxiway)"
echo "  3. Identify color changes with exact timing"
echo "  4. Extract GPS position for each frame (if available)"
echo "  5. Generate detailed HTML reports with charts"
echo ""

# Show estimated time
if [ "$VIDEO_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⏱️  Estimated time: 30 seconds to 3 minutes per video${NC}"
    echo ""
fi

# Confirm
read -p "Press ENTER to start analysis or Ctrl+C to cancel... "

# Run the analysis
echo ""
echo -e "${BLUE}════════════════════════════════════════════${NC}"
echo -e "${BLUE} Starting Analysis...${NC}"
echo -e "${BLUE}════════════════════════════════════════════${NC}"
echo ""

# Process videos with Python script
python3 analyze_lights.py \
    --videos-dir "$VIDEOS_DIR" \
    --output-dir "$REPORTS_DIR" \
    $GPS_FLAG

# Check results
REPORT_COUNT=$(find "$REPORTS_DIR" -name "*light_report*.html" 2>/dev/null | wc -l)

echo ""
if [ "$REPORT_COUNT" -gt 0 ]; then
    echo -e "${GREEN}════════════════════════════════════════════${NC}"
    echo -e "${GREEN} ✅ Analysis Complete!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${GREEN}Generated $REPORT_COUNT report(s) in '$REPORTS_DIR/'${NC}"
    echo ""
    
    # List reports
    echo "Reports created:"
    for report in "$REPORTS_DIR"/*light_report*.html; do
        if [ -f "$report" ]; then
            echo "  • $(basename "$report")"
        fi
    done
    
    # Open latest report
    LATEST=$(ls -t "$REPORTS_DIR"/*light_report*.html 2>/dev/null | head -1)
    if [ -n "$LATEST" ] && [ -f "$LATEST" ]; then
        echo ""
        echo -e "${YELLOW}Opening latest report...${NC}"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            open "$LATEST"
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            xdg-open "$LATEST" 2>/dev/null || true
        fi
    fi
else
    echo -e "${RED}❌ No reports generated. Check errors above.${NC}"
fi

# Deactivate virtual environment
deactivate

echo ""
echo "Done!"
echo ""