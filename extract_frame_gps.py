#!/usr/bin/env python3
"""
Extract GPS position data for every frame from DJI drone videos
Uses exiftool to parse embedded frame metadata
"""

import subprocess
import re
import json
from pathlib import Path
import sys
import pandas as pd
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def parse_frame_metadata(text_line: str) -> Optional[Dict]:
    """Parse a single frame metadata line from exiftool output"""
    
    # Extract frame number
    frame_match = re.search(r'FrameCnt:\s*(\d+)', text_line)
    if not frame_match:
        return None
    
    frame_num = int(frame_match.group(1))
    
    # Extract timestamp
    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)', text_line)
    timestamp = timestamp_match.group(1) if timestamp_match else None
    
    # Extract GPS coordinates
    lat_match = re.search(r'\[latitude:\s*([-\d.]+)\]', text_line)
    lon_match = re.search(r'\[longitude:\s*([-\d.]+)\]', text_line)
    
    if not lat_match or not lon_match:
        return None
    
    latitude = float(lat_match.group(1))
    longitude = float(lon_match.group(1))
    
    # Extract altitudes
    rel_alt_match = re.search(r'\[rel_alt:\s*([-\d.]+)', text_line)
    abs_alt_match = re.search(r'abs_alt:\s*([-\d.]+)\]', text_line)
    
    rel_altitude = float(rel_alt_match.group(1)) if rel_alt_match else None
    abs_altitude = float(abs_alt_match.group(1)) if abs_alt_match else None
    
    # Extract gimbal angles
    yaw_match = re.search(r'\[gb_yaw:\s*([-\d.]+)', text_line)
    pitch_match = re.search(r'gb_pitch:\s*([-\d.]+)', text_line)
    roll_match = re.search(r'gb_roll:\s*([-\d.]+)\]', text_line)
    
    gb_yaw = float(yaw_match.group(1)) if yaw_match else None
    gb_pitch = float(pitch_match.group(1)) if pitch_match else None
    gb_roll = float(roll_match.group(1)) if roll_match else None
    
    # Extract camera settings
    iso_match = re.search(r'\[iso:\s*(\d+)\]', text_line)
    shutter_match = re.search(r'\[shutter:\s*([\d/.]+)\]', text_line)
    fnum_match = re.search(r'\[fnum:\s*([\d.]+)\]', text_line)
    focal_len_match = re.search(r'\[focal_len:\s*([\d.]+)\]', text_line)
    
    iso = int(iso_match.group(1)) if iso_match else None
    shutter = shutter_match.group(1) if shutter_match else None
    fnum = float(fnum_match.group(1)) if fnum_match else None
    focal_length = float(focal_len_match.group(1)) if focal_len_match else None
    
    return {
        'frame': frame_num,
        'timestamp': timestamp,
        'latitude': latitude,
        'longitude': longitude,
        'rel_altitude': rel_altitude,
        'abs_altitude': abs_altitude,
        'gb_yaw': gb_yaw,
        'gb_pitch': gb_pitch,
        'gb_roll': gb_roll,
        'iso': iso,
        'shutter': shutter,
        'fnum': fnum,
        'focal_length': focal_length
    }


def extract_all_frame_gps(video_path: Path) -> List[Dict]:
    """Extract GPS data for all frames from a video file"""
    
    logger.info(f"Extracting frame GPS data from: {video_path}")
    
    # Run exiftool with -ee flag to extract embedded data
    cmd = ['exiftool', '-ee', '-G', '-a', str(video_path)]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            logger.error(f"exiftool failed: {result.stderr}")
            return []
        
        # Parse all Text fields containing frame data
        frames_data = []
        for line in result.stdout.split('\n'):
            if '[QuickTime]     Text' in line and 'FrameCnt:' in line:
                frame_data = parse_frame_metadata(line)
                if frame_data:
                    frames_data.append(frame_data)
        
        logger.info(f"Extracted GPS data for {len(frames_data)} frames")
        return frames_data
        
    except subprocess.TimeoutExpired:
        logger.error("exiftool timed out")
        return []
    except Exception as e:
        logger.error(f"Error extracting GPS data: {e}")
        return []


def save_gps_data(frames_data: List[Dict], output_path: Path):
    """Save GPS data to CSV and JSON files"""
    
    if not frames_data:
        logger.warning("No data to save")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(frames_data)
    
    # Save as CSV
    csv_path = output_path.with_suffix('.csv')
    df.to_csv(csv_path, index=False)
    logger.info(f"Saved CSV: {csv_path}")
    
    # Save as JSON
    json_path = output_path.with_suffix('.json')
    with open(json_path, 'w') as f:
        json.dump(frames_data, f, indent=2)
    logger.info(f"Saved JSON: {json_path}")
    
    # Print summary
    print("\n" + "="*60)
    print("GPS DATA SUMMARY")
    print("="*60)
    print(f"Total frames with GPS: {len(frames_data)}")
    
    if frames_data:
        first = frames_data[0]
        last = frames_data[-1]
        
        print(f"\nFirst frame (#{first['frame']}):")
        print(f"  Timestamp: {first['timestamp']}")
        print(f"  Position: {first['latitude']:.6f}, {first['longitude']:.6f}")
        print(f"  Altitude: {first['rel_altitude']:.1f}m (relative), {first['abs_altitude']:.1f}m (absolute)")
        
        print(f"\nLast frame (#{last['frame']}):")
        print(f"  Timestamp: {last['timestamp']}")
        print(f"  Position: {last['latitude']:.6f}, {last['longitude']:.6f}")
        print(f"  Altitude: {last['rel_altitude']:.1f}m (relative), {last['abs_altitude']:.1f}m (absolute)")
        
        # Calculate movement
        lat_change = last['latitude'] - first['latitude']
        lon_change = last['longitude'] - first['longitude']
        alt_change = last['rel_altitude'] - first['rel_altitude']
        
        print(f"\nMovement during video:")
        print(f"  Latitude change: {lat_change:.6f}° ({lat_change * 111320:.1f}m approx)")
        print(f"  Longitude change: {lon_change:.6f}° ({lon_change * 111320 * 0.7:.1f}m approx at 48° lat)")
        print(f"  Altitude change: {alt_change:.1f}m")
        
        # Show unique positions
        unique_positions = df[['latitude', 'longitude']].drop_duplicates()
        print(f"\nUnique GPS positions: {len(unique_positions)}")
        
        if len(unique_positions) < len(frames_data):
            print(f"Note: Drone was hovering or moving slowly (many frames share same GPS position)")


def create_flight_path_kml(frames_data: List[Dict], output_path: Path):
    """Create a KML file for viewing the flight path in Google Earth"""
    
    if not frames_data:
        return
    
    kml_path = output_path.with_suffix('.kml')
    
    # Create KML content
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Drone Flight Path</name>
    <Style id="flightPath">
      <LineStyle>
        <color>ff0000ff</color>
        <width>3</width>
      </LineStyle>
    </Style>
    <Placemark>
      <name>Flight Path</name>
      <styleUrl>#flightPath</styleUrl>
      <LineString>
        <altitudeMode>absolute</altitudeMode>
        <coordinates>
"""
    
    # Add coordinates
    for frame in frames_data:
        kml_content += f"          {frame['longitude']},{frame['latitude']},{frame['abs_altitude']}\n"
    
    kml_content += """        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>"""
    
    with open(kml_path, 'w') as f:
        f.write(kml_content)
    
    logger.info(f"Saved KML file: {kml_path}")
    print(f"\nYou can open {kml_path} in Google Earth to view the flight path")


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_frame_gps.py <video_file> [output_name]")
        print("\nExtracts GPS position for every frame from DJI drone videos")
        print("Creates CSV, JSON, and KML output files")
        sys.exit(1)
    
    video_path = Path(sys.argv[1])
    
    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        sys.exit(1)
    
    # Determine output path
    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])
    else:
        output_path = video_path.with_name(f"{video_path.stem}_gps_data")
    
    # Extract GPS data
    frames_data = extract_all_frame_gps(video_path)
    
    if frames_data:
        # Save data
        save_gps_data(frames_data, output_path)
        
        # Create KML file
        create_flight_path_kml(frames_data, output_path)
        
        print("\n✅ GPS extraction complete!")
    else:
        print("\n❌ No GPS data found in video")


if __name__ == "__main__":
    main()