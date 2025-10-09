# Airport Light Detection System

Analyzes drone videos to detect and track airport lights (PAPI, runway lights, taxiway lights).
Processes EVERY FRAME for maximum accuracy and extracts GPS position data from DJI drones.

## 🚀 Quick Start

```bash
# Run the analysis
./analyze_videos.sh
```

That's it! The script will:
1. Check all requirements
2. Process all videos in the `videos/` folder
3. Generate HTML reports in the `reports/` folder
4. Open the results in your browser

## 📁 Project Structure

```
airport-lights-detection/
├── videos/               # Put your drone videos here
├── reports/              # HTML reports are generated here
├── analyze_videos.sh     # Main script - RUN THIS
├── analyze_lights.py     # Core Python analysis engine
├── gps_extractor.py      # GPS metadata extraction
├── extract_frame_gps.py  # Standalone GPS extraction tool
└── requirements.txt      # Python dependencies
```

## 🎥 Input Videos

Place your videos in the `videos/` folder. Supported formats:
- `.MP4` / `.mp4` (DJI and other drones)
- `.MOV` / `.mov`
- `.AVI` / `.avi`

## 📊 What Gets Analyzed

The system analyzes **EVERY FRAME** to detect:

- **PAPI Lights**: White/red approach lights with color change detection
- **Runway Lights**: Edge and centerline lights
- **Taxiway Lights**: Green centerline, blue edge lights
- **Other Lights**: High-intensity approach lights, beacons

For each light, it tracks:
- RGB color values over time
- Rate of color change (1st derivative)
- Position in frame (x, y coordinates)
- GPS position (if available in video metadata)
- Brightness and intensity

## 🗺️ GPS Data Extraction

If your videos contain GPS metadata (DJI drones), the system will:
- Extract latitude, longitude, altitude for EACH frame
- Show 3D flight path visualization
- Link color changes to exact drone positions

**Note**: GPS extraction requires `exiftool`:
```bash
brew install exiftool  # macOS
```

## 📈 Output Reports

HTML reports include:
- Video player with source footage
- Annotated snapshots showing tracked lights
- RGB color analysis charts
- Color change detection with GPS positions
- 3D drone flight path (if GPS available)
- Individual analysis for each tracked light

## ⚙️ Advanced Options

For special cases, you can run the Python script directly:

```bash
# Use sampling mode (faster but less accurate)
python3 analyze_lights.py --sample-mode --interval 100

# Disable GPS extraction
python3 analyze_lights.py --no-gps

# Custom directories
python3 analyze_lights.py --videos-dir /path/to/videos --output-dir /path/to/reports
```

## 🛠️ Standalone GPS Extraction

Extract all GPS data from a video to CSV/JSON/KML:

```bash
python3 extract_frame_gps.py videos/your_video.MP4
```

This creates:
- `your_video_gps_data.csv` - Spreadsheet with all GPS points
- `your_video_gps_data.json` - JSON format
- `your_video_gps_data.kml` - For Google Earth

## 📋 Requirements

- Python 3.7+
- OpenCV (cv2)
- NumPy, Pandas, Plotly
- exiftool (optional, for GPS extraction)

All Python dependencies are automatically installed by the main script.

## 🎯 Tips for Best Results

1. **Video Quality**: Higher resolution = better light detection
2. **Stable Flight**: Smoother drone movements = better tracking
3. **Good Lighting**: Evening/night videos show lights more clearly
4. **GPS Data**: DJI drones automatically embed GPS in videos

## 🐛 Troubleshooting

**Script hangs during GPS extraction:**
- Run with `--no-gps` flag
- Or install exiftool: `brew install exiftool`

**No lights detected:**
- Check video has visible lights
- Try adjusting brightness threshold in code

**Out of memory:**
- Use sampling mode: add `--sample-mode` flag

---

For issues or questions, check the generated HTML reports for detailed analysis logs.