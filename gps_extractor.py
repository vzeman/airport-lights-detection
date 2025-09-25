#!/usr/bin/env python3
"""
GPS Metadata Extractor for Drone Videos
Extracts GPS coordinates, altitude, and other telemetry data from video files.
Supports various drone formats including DJI, Parrot, and standard MP4 with GPS tracks.
"""

import struct
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import subprocess
import xml.etree.ElementTree as ET
import re
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GPSData:
    """Represents GPS data for a specific timestamp"""
    timestamp_ms: float
    latitude: float
    longitude: float
    altitude: float  # meters above sea level
    speed: Optional[float] = None  # m/s
    heading: Optional[float] = None  # degrees
    satellites: Optional[int] = None
    accuracy: Optional[float] = None  # meters
    frame_number: Optional[int] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'timestamp_ms': self.timestamp_ms,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude': self.altitude,
            'speed': self.speed,
            'heading': self.heading,
            'satellites': self.satellites,
            'accuracy': self.accuracy,
            'frame_number': self.frame_number
        }


class GPSExtractor:
    """Main class for extracting GPS data from video files"""
    
    def __init__(self):
        self.supported_formats = ['.mp4', '.mov', '.avi', '.mkv']
        
    def extract_gps_data(self, video_path: Path) -> List[GPSData]:
        """
        Extract GPS data from video file using multiple methods.
        Tries different extraction methods in order of reliability.
        """
        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return []
        
        logger.info(f"Extracting GPS data from: {video_path}")
        
        # Method 1: Try DJI SRT file first (most reliable for DJI drones)
        logger.debug("Trying DJI SRT extraction...")
        try:
            gps_data = self._extract_from_dji_srt(video_path)
            if gps_data:
                logger.info(f"Extracted {len(gps_data)} GPS points from DJI SRT file")
                return gps_data
        except Exception as e:
            logger.debug(f"DJI SRT extraction failed: {e}")
        
        # Method 2: Try ffprobe for standard GPS metadata
        logger.debug("Trying ffprobe extraction...")
        try:
            gps_data = self._extract_with_ffprobe(video_path)
            if gps_data:
                logger.info(f"Extracted {len(gps_data)} GPS points using ffprobe")
                return gps_data
        except Exception as e:
            logger.debug(f"ffprobe extraction failed: {e}")
        
        # Method 3: Try exiftool for embedded metadata (if available)
        logger.debug("Trying exiftool extraction...")
        try:
            gps_data = self._extract_with_exiftool(video_path)
            if gps_data:
                logger.info(f"Extracted {len(gps_data)} GPS points using exiftool")
                return gps_data
        except Exception as e:
            logger.debug(f"exiftool extraction failed: {e}")
        
        # Method 4: Parse raw MP4 atoms for GPS data
        logger.debug("Trying MP4 atom extraction...")
        try:
            gps_data = self._extract_from_mp4_atoms(video_path)
            if gps_data:
                logger.info(f"Extracted {len(gps_data)} GPS points from MP4 atoms")
                return gps_data
        except Exception as e:
            logger.debug(f"MP4 atom extraction failed: {e}")
        
        logger.info(f"No GPS data found in {video_path} - continuing without GPS")
        return []
    
    def _extract_with_ffprobe(self, video_path: Path) -> List[GPSData]:
        """Extract GPS data using ffprobe"""
        try:
            # Get metadata streams
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-show_format',
                str(video_path)
            ]
            
            logger.debug(f"Running ffprobe command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return []
            
            data = json.loads(result.stdout)
            gps_data = []
            
            # Look for GPS data in streams
            for stream in data.get('streams', []):
                if stream.get('codec_tag_string') == 'gpmd' or 'gps' in stream.get('codec_name', '').lower():
                    # Extract GPS metadata stream
                    gps_data = self._parse_gpmd_stream(video_path, stream.get('index', 0))
                    if gps_data:
                        return gps_data
            
            # Check format tags for GPS coordinates
            format_tags = data.get('format', {}).get('tags', {})
            if 'location' in format_tags or 'com.apple.quicktime.location.ISO6709' in format_tags:
                # Parse static GPS location
                location = format_tags.get('location') or format_tags.get('com.apple.quicktime.location.ISO6709')
                gps_point = self._parse_iso6709(location)
                if gps_point:
                    # For static GPS, create one point at the beginning
                    return [gps_point]
            
            return []
            
        except Exception as e:
            logger.debug(f"ffprobe extraction failed: {e}")
            return []
    
    def _extract_with_exiftool(self, video_path: Path) -> List[GPSData]:
        """Extract GPS data using exiftool - handles DJI embedded frame metadata"""
        try:
            # Check if exiftool is available
            check_cmd = ['which', 'exiftool']
            check_result = subprocess.run(check_cmd, capture_output=True)
            if check_result.returncode != 0:
                logger.debug("exiftool not found, skipping this method")
                return []
            
            # First try to extract embedded frame GPS data (DJI format)
            # Note: This can be slow for videos with many frames
            # Limit extraction to avoid hanging
            cmd = ['exiftool', '-ee', '-G', '-a', str(video_path)]
            logger.debug("Extracting embedded GPS with exiftool -ee (may take a moment)...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and result.stdout:
                # Parse DJI embedded frame GPS data
                gps_data = []
                for line in result.stdout.split('\n'):
                    if '[QuickTime]     Text' in line and 'FrameCnt:' in line:
                        # Parse frame metadata
                        gps_point = self._parse_dji_frame_metadata(line)
                        if gps_point:
                            gps_data.append(gps_point)
                
                if gps_data:
                    logger.info(f"Found {len(gps_data)} GPS points in DJI embedded metadata")
                    # Return all GPS data for frame-by-frame analysis
                    # The interpolation function will handle finding the right GPS point
                    return gps_data
            
            # If no embedded frame data, try standard JSON extraction
            cmd = ['exiftool', '-json', '-g', '-ee', str(video_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return []
            
            try:
                data = json.loads(result.stdout)
                if not data:
                    return []
                
                metadata = data[0]
                gps_data = []
                
                # Check for GPS track data
                if 'Track1' in metadata or 'Track2' in metadata or 'Track3' in metadata:
                    for track_key in ['Track1', 'Track2', 'Track3', 'Track4']:
                        if track_key in metadata:
                            track = metadata[track_key]
                            if 'GPSLatitude' in track and 'GPSLongitude' in track:
                                # Extract GPS track data
                                gps_data = self._parse_exiftool_track(track)
                                if gps_data:
                                    return gps_data
                
                # Check for single GPS position
                if 'GPSLatitude' in metadata and 'GPSLongitude' in metadata:
                    gps_point = GPSData(
                        timestamp_ms=0,
                        latitude=self._parse_gps_coord(metadata.get('GPSLatitude')),
                        longitude=self._parse_gps_coord(metadata.get('GPSLongitude')),
                        altitude=float(metadata.get('GPSAltitude', 0))
                    )
                    return [gps_point]
            except json.JSONDecodeError:
                pass
            
            return []
            
        except Exception as e:
            logger.debug(f"exiftool extraction failed: {e}")
            return []
    
    def _extract_from_dji_srt(self, video_path: Path) -> List[GPSData]:
        """Extract GPS data from DJI SRT subtitle file"""
        srt_path = video_path.with_suffix('.SRT')
        if not srt_path.exists():
            srt_path = video_path.with_suffix('.srt')
        
        if not srt_path.exists():
            return []
        
        try:
            gps_data = []
            with open(srt_path, 'r') as f:
                content = f.read()
            
            # Parse SRT entries
            entries = content.strip().split('\n\n')
            for entry in entries:
                lines = entry.strip().split('\n')
                if len(lines) < 3:
                    continue
                
                # Parse timestamp
                timestamp_line = lines[1]
                timestamp_ms = self._parse_srt_timestamp(timestamp_line)
                
                # Parse GPS data from subtitle text
                text = ' '.join(lines[2:])
                gps_point = self._parse_dji_srt_text(text, timestamp_ms)
                if gps_point:
                    gps_data.append(gps_point)
            
            return gps_data
            
        except Exception as e:
            logger.debug(f"DJI SRT extraction failed: {e}")
            return []
    
    def _extract_from_mp4_atoms(self, video_path: Path) -> List[GPSData]:
        """Extract GPS data by parsing MP4 atom structure"""
        try:
            with open(video_path, 'rb') as f:
                # Parse MP4 atoms to find GPS data
                gps_data = self._parse_mp4_file(f)
                return gps_data
        except Exception as e:
            logger.debug(f"MP4 atom extraction failed: {e}")
            return []
    
    def _parse_gpmd_stream(self, video_path: Path, stream_index: int) -> List[GPSData]:
        """Parse GoPro GPMD metadata stream"""
        try:
            # Extract raw GPMD data
            cmd = [
                'ffmpeg', '-i', str(video_path),
                '-codec', 'copy',
                '-map', f'0:{stream_index}',
                '-f', 'rawvideo',
                '-'
            ]
            
            logger.debug(f"Extracting GPMD stream {stream_index}")
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            if result.returncode != 0:
                return []
            
            # Parse GPMD binary data
            return self._parse_gpmd_data(result.stdout)
            
        except Exception as e:
            logger.debug(f"GPMD stream parsing failed: {e}")
            return []
    
    def _parse_gpmd_data(self, data: bytes) -> List[GPSData]:
        """Parse GoPro GPMD binary format"""
        gps_data = []
        offset = 0
        
        while offset < len(data) - 8:
            # Read FOURCC and data size
            fourcc = data[offset:offset+4].decode('ascii', errors='ignore')
            size = struct.unpack('>H', data[offset+4:offset+6])[0]
            
            if fourcc == 'GPS5':  # GPS data (lat, lon, alt, speed2D, speed3D)
                gps_offset = offset + 8
                while gps_offset < offset + 8 + size:
                    try:
                        lat = struct.unpack('>i', data[gps_offset:gps_offset+4])[0] / 1e7
                        lon = struct.unpack('>i', data[gps_offset+4:gps_offset+8])[0] / 1e7
                        alt = struct.unpack('>i', data[gps_offset+8:gps_offset+12])[0] / 1000.0
                        speed2d = struct.unpack('>i', data[gps_offset+12:gps_offset+16])[0] / 1000.0
                        
                        gps_point = GPSData(
                            timestamp_ms=len(gps_data) * 1000,  # Approximate
                            latitude=lat,
                            longitude=lon,
                            altitude=alt,
                            speed=speed2d
                        )
                        gps_data.append(gps_point)
                        gps_offset += 20
                    except:
                        break
            
            offset += 8 + size
            # Align to 4 bytes
            if size % 4 != 0:
                offset += 4 - (size % 4)
        
        return gps_data
    
    def _parse_iso6709(self, location_str: str) -> Optional[GPSData]:
        """Parse ISO 6709 location string"""
        try:
            # Format: +40.7580-073.9855+011.234/
            pattern = r'([+-]\d+\.\d+)([+-]\d+\.\d+)([+-]\d+\.\d+)?'
            match = re.match(pattern, location_str)
            if match:
                lat = float(match.group(1))
                lon = float(match.group(2))
                alt = float(match.group(3)) if match.group(3) else 0
                
                return GPSData(
                    timestamp_ms=0,
                    latitude=lat,
                    longitude=lon,
                    altitude=alt
                )
        except:
            pass
        return None
    
    def _parse_gps_coord(self, coord_str: Any) -> float:
        """Parse GPS coordinate from various formats"""
        if isinstance(coord_str, (int, float)):
            return float(coord_str)
        
        if isinstance(coord_str, str):
            # Handle DMS format: "40 deg 45' 30.12\" N"
            dms_pattern = r'(\d+)\s*deg\s*(\d+)\'\s*([\d.]+)"\s*([NSEW])'
            match = re.match(dms_pattern, coord_str)
            if match:
                deg = float(match.group(1))
                min = float(match.group(2))
                sec = float(match.group(3))
                dir = match.group(4)
                
                decimal = deg + min/60 + sec/3600
                if dir in ['S', 'W']:
                    decimal = -decimal
                return decimal
            
            # Try to parse as float
            try:
                return float(coord_str)
            except:
                pass
        
        return 0.0
    
    def _parse_srt_timestamp(self, timestamp_str: str) -> float:
        """Parse SRT timestamp to milliseconds"""
        try:
            # Format: 00:00:12,000 --> 00:00:15,000
            start_time = timestamp_str.split(' --> ')[0]
            time_parts = re.match(r'(\d+):(\d+):(\d+),(\d+)', start_time)
            if time_parts:
                hours = int(time_parts.group(1))
                minutes = int(time_parts.group(2))
                seconds = int(time_parts.group(3))
                millis = int(time_parts.group(4))
                
                total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000 + millis
                return total_ms
        except:
            pass
        return 0
    
    def _parse_dji_frame_metadata(self, line: str) -> Optional[GPSData]:
        """Parse DJI embedded frame GPS metadata from exiftool output"""
        try:
            # Extract frame number
            frame_match = re.search(r'FrameCnt:\s*(\d+)', line)
            if not frame_match:
                return None
            
            frame_num = int(frame_match.group(1))
            
            # Extract timestamp
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)', line)
            if timestamp_match:
                # Convert timestamp to milliseconds
                from datetime import datetime
                dt = datetime.strptime(timestamp_match.group(1)[:19], '%Y-%m-%d %H:%M:%S')
                ms = int(timestamp_match.group(1).split('.')[-1][:3]) if '.' in timestamp_match.group(1) else 0
                timestamp_ms = (dt.timestamp() * 1000) + ms
            else:
                # Approximate based on frame number (assuming 30fps)
                timestamp_ms = frame_num * 33.33
            
            # Extract GPS coordinates
            lat_match = re.search(r'\[latitude:\s*([-\d.]+)\]', line)
            lon_match = re.search(r'\[longitude:\s*([-\d.]+)\]', line)
            
            if not lat_match or not lon_match:
                return None
            
            latitude = float(lat_match.group(1))
            longitude = float(lon_match.group(1))
            
            # Extract altitudes
            rel_alt_match = re.search(r'\[rel_alt:\s*([-\d.]+)', line)
            abs_alt_match = re.search(r'abs_alt:\s*([-\d.]+)\]', line)
            
            altitude = float(abs_alt_match.group(1)) if abs_alt_match else (
                float(rel_alt_match.group(1)) if rel_alt_match else 0
            )
            
            # Extract gimbal yaw as heading
            yaw_match = re.search(r'\[gb_yaw:\s*([-\d.]+)', line)
            heading = float(yaw_match.group(1)) if yaw_match else None
            
            return GPSData(
                timestamp_ms=timestamp_ms,
                latitude=latitude,
                longitude=longitude,
                altitude=altitude,
                heading=heading,
                frame_number=frame_num
            )
            
        except Exception as e:
            logger.debug(f"Failed to parse DJI frame metadata: {e}")
            return None
    
    def _parse_dji_srt_text(self, text: str, timestamp_ms: float) -> Optional[GPSData]:
        """Parse DJI drone SRT subtitle text"""
        try:
            # DJI format includes GPS coordinates and telemetry
            # Example: "GPS (40.7580, -73.9855, 15) [12]"
            gps_pattern = r'GPS\s*\(([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*),\s*([+-]?\d+\.?\d*)\)'
            match = re.search(gps_pattern, text)
            if match:
                lat = float(match.group(1))
                lon = float(match.group(2))
                alt = float(match.group(3))
                
                # Try to extract additional data
                satellites = None
                sat_pattern = r'\[(\d+)\]'
                sat_match = re.search(sat_pattern, text)
                if sat_match:
                    satellites = int(sat_match.group(1))
                
                return GPSData(
                    timestamp_ms=timestamp_ms,
                    latitude=lat,
                    longitude=lon,
                    altitude=alt,
                    satellites=satellites
                )
        except:
            pass
        return None
    
    def _parse_exiftool_track(self, track_data: Dict) -> List[GPSData]:
        """Parse GPS track data from exiftool output"""
        gps_data = []
        
        try:
            # Get sample times if available
            sample_times = track_data.get('SampleTime', [])
            if isinstance(sample_times, str):
                sample_times = [sample_times]
            
            # Get GPS coordinates
            latitudes = track_data.get('GPSLatitude', [])
            longitudes = track_data.get('GPSLongitude', [])
            altitudes = track_data.get('GPSAltitude', [])
            
            # Ensure lists
            if not isinstance(latitudes, list):
                latitudes = [latitudes]
            if not isinstance(longitudes, list):
                longitudes = [longitudes]
            if not isinstance(altitudes, list):
                altitudes = [altitudes] * len(latitudes)
            
            # Create GPS data points
            for i in range(min(len(latitudes), len(longitudes))):
                timestamp_ms = i * 1000  # Default to 1 second intervals
                if i < len(sample_times):
                    # Parse sample time
                    timestamp_ms = self._parse_time_string(sample_times[i])
                
                gps_point = GPSData(
                    timestamp_ms=timestamp_ms,
                    latitude=self._parse_gps_coord(latitudes[i]),
                    longitude=self._parse_gps_coord(longitudes[i]),
                    altitude=self._parse_gps_coord(altitudes[i]) if i < len(altitudes) else 0
                )
                gps_data.append(gps_point)
            
        except Exception as e:
            logger.debug(f"Failed to parse exiftool track: {e}")
        
        return gps_data
    
    def _parse_time_string(self, time_str: str) -> float:
        """Parse time string to milliseconds"""
        try:
            # Handle format like "0:00:12.000"
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 3:
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = float(parts[2])
                    return (hours * 3600 + minutes * 60 + seconds) * 1000
            
            # Try as float seconds
            return float(time_str) * 1000
        except:
            return 0
    
    def _parse_mp4_file(self, file_handle) -> List[GPSData]:
        """Parse MP4 file structure to find GPS atoms"""
        gps_data = []
        
        def read_atom(f):
            """Read an MP4 atom"""
            start_pos = f.tell()
            size_bytes = f.read(4)
            if len(size_bytes) < 4:
                return None, None, None
            
            size = struct.unpack('>I', size_bytes)[0]
            atom_type = f.read(4).decode('ascii', errors='ignore')
            
            return size, atom_type, start_pos
        
        def find_gps_atoms(f, max_depth=10, depth=0):
            """Recursively find GPS-related atoms"""
            if depth > max_depth:
                return []
            
            gps_data = []
            
            while True:
                size, atom_type, start_pos = read_atom(f)
                if size is None:
                    break
                
                # Check for GPS-related atoms
                if atom_type in ['gps ', 'GPS ', '@xyz', 'loci']:
                    # Read GPS data
                    data = f.read(size - 8)
                    gps_point = self._parse_atom_gps_data(data, atom_type)
                    if gps_point:
                        gps_data.append(gps_point)
                
                # Check container atoms
                elif atom_type in ['moov', 'trak', 'mdia', 'minf', 'stbl', 'udta', 'meta']:
                    # Recursively search container
                    sub_gps = find_gps_atoms(f, max_depth, depth + 1)
                    gps_data.extend(sub_gps)
                
                # Skip to next atom
                f.seek(start_pos + size)
            
            return gps_data
        
        # Start parsing from beginning
        file_handle.seek(0)
        gps_data = find_gps_atoms(file_handle)
        
        return gps_data
    
    def _parse_atom_gps_data(self, data: bytes, atom_type: str) -> Optional[GPSData]:
        """Parse GPS data from MP4 atom"""
        try:
            if atom_type == '@xyz':
                # Apple location format
                # Skip version and flags
                coords_str = data[4:].decode('utf-8', errors='ignore')
                return self._parse_iso6709(coords_str)
            
            elif atom_type in ['gps ', 'GPS ']:
                # Try to parse as GPS coordinates
                if len(data) >= 12:
                    lat = struct.unpack('>f', data[0:4])[0]
                    lon = struct.unpack('>f', data[4:8])[0]
                    alt = struct.unpack('>f', data[8:12])[0]
                    
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        return GPSData(
                            timestamp_ms=0,
                            latitude=lat,
                            longitude=lon,
                            altitude=alt
                        )
        except:
            pass
        
        return None
    
    def interpolate_gps_for_frame(self, gps_data: List[GPSData], frame_num: int, fps: float) -> Optional[GPSData]:
        """
        Interpolate GPS position for a specific frame number.
        
        Args:
            gps_data: List of GPS data points
            frame_num: Frame number to interpolate for
            fps: Frames per second of the video
        
        Returns:
            Interpolated GPS data for the frame, or None if not available
        """
        if not gps_data:
            return None
        
        # Calculate timestamp for this frame
        target_timestamp_ms = (frame_num / fps) * 1000
        
        # If only one GPS point, return it for all frames
        if len(gps_data) == 1:
            gps_point = gps_data[0]
            return GPSData(
                timestamp_ms=target_timestamp_ms,
                latitude=gps_point.latitude,
                longitude=gps_point.longitude,
                altitude=gps_point.altitude,
                speed=gps_point.speed,
                heading=gps_point.heading,
                satellites=gps_point.satellites,
                accuracy=gps_point.accuracy,
                frame_number=frame_num
            )
        
        # Find surrounding GPS points for interpolation
        before_point = None
        after_point = None
        
        for i, gps_point in enumerate(gps_data):
            if gps_point.timestamp_ms <= target_timestamp_ms:
                before_point = gps_point
            if gps_point.timestamp_ms >= target_timestamp_ms and after_point is None:
                after_point = gps_point
                break
        
        # If exact match found
        if before_point and before_point.timestamp_ms == target_timestamp_ms:
            return GPSData(
                timestamp_ms=target_timestamp_ms,
                latitude=before_point.latitude,
                longitude=before_point.longitude,
                altitude=before_point.altitude,
                speed=before_point.speed,
                heading=before_point.heading,
                satellites=before_point.satellites,
                accuracy=before_point.accuracy,
                frame_number=frame_num
            )
        
        # If we have both points, interpolate
        if before_point and after_point:
            # Calculate interpolation factor
            time_diff = after_point.timestamp_ms - before_point.timestamp_ms
            if time_diff > 0:
                factor = (target_timestamp_ms - before_point.timestamp_ms) / time_diff
            else:
                factor = 0
            
            # Linear interpolation
            lat = before_point.latitude + (after_point.latitude - before_point.latitude) * factor
            lon = before_point.longitude + (after_point.longitude - before_point.longitude) * factor
            alt = before_point.altitude + (after_point.altitude - before_point.altitude) * factor
            
            # Interpolate optional fields
            speed = None
            if before_point.speed is not None and after_point.speed is not None:
                speed = before_point.speed + (after_point.speed - before_point.speed) * factor
            
            heading = None
            if before_point.heading is not None and after_point.heading is not None:
                # Circular interpolation for heading
                h1 = before_point.heading
                h2 = after_point.heading
                diff = (h2 - h1 + 180) % 360 - 180
                heading = (h1 + diff * factor) % 360
            
            return GPSData(
                timestamp_ms=target_timestamp_ms,
                latitude=lat,
                longitude=lon,
                altitude=alt,
                speed=speed,
                heading=heading,
                satellites=before_point.satellites,  # Use last known value
                accuracy=before_point.accuracy,  # Use last known value
                frame_number=frame_num
            )
        
        # If only before point available (extrapolate forward)
        if before_point:
            return GPSData(
                timestamp_ms=target_timestamp_ms,
                latitude=before_point.latitude,
                longitude=before_point.longitude,
                altitude=before_point.altitude,
                speed=before_point.speed,
                heading=before_point.heading,
                satellites=before_point.satellites,
                accuracy=before_point.accuracy,
                frame_number=frame_num
            )
        
        # If only after point available (extrapolate backward)
        if after_point:
            return GPSData(
                timestamp_ms=target_timestamp_ms,
                latitude=after_point.latitude,
                longitude=after_point.longitude,
                altitude=after_point.altitude,
                speed=after_point.speed,
                heading=after_point.heading,
                satellites=after_point.satellites,
                accuracy=after_point.accuracy,
                frame_number=frame_num
            )
        
        return None


def format_gps_coordinates(lat: float, lon: float) -> str:
    """Format GPS coordinates in human-readable format"""
    lat_dir = 'N' if lat >= 0 else 'S'
    lon_dir = 'E' if lon >= 0 else 'W'
    
    lat_abs = abs(lat)
    lon_abs = abs(lon)
    
    lat_deg = int(lat_abs)
    lat_min = int((lat_abs - lat_deg) * 60)
    lat_sec = ((lat_abs - lat_deg) * 60 - lat_min) * 60
    
    lon_deg = int(lon_abs)
    lon_min = int((lon_abs - lon_deg) * 60)
    lon_sec = ((lon_abs - lon_deg) * 60 - lon_min) * 60
    
    return f"{lat_deg}°{lat_min:02d}'{lat_sec:05.2f}\"{lat_dir}, {lon_deg}°{lon_min:02d}'{lon_sec:05.2f}\"{lon_dir}"


def calculate_distance(point1: GPSData, point2: GPSData) -> float:
    """Calculate distance between two GPS points in meters using Haversine formula"""
    R = 6371000  # Earth radius in meters
    
    lat1 = np.radians(point1.latitude)
    lat2 = np.radians(point2.latitude)
    dlat = np.radians(point2.latitude - point1.latitude)
    dlon = np.radians(point2.longitude - point1.longitude)
    
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    
    return R * c


def calculate_bearing(point1: GPSData, point2: GPSData) -> float:
    """Calculate bearing from point1 to point2 in degrees"""
    lat1 = np.radians(point1.latitude)
    lat2 = np.radians(point2.latitude)
    dlon = np.radians(point2.longitude - point1.longitude)
    
    x = np.sin(dlon) * np.cos(lat2)
    y = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(dlon)
    
    bearing = np.degrees(np.arctan2(x, y))
    return (bearing + 360) % 360


if __name__ == "__main__":
    # Test the GPS extractor
    import sys
    
    if len(sys.argv) > 1:
        video_file = Path(sys.argv[1])
        extractor = GPSExtractor()
        gps_data = extractor.extract_gps_data(video_file)
        
        if gps_data:
            print(f"Found {len(gps_data)} GPS data points:")
            for i, point in enumerate(gps_data[:5]):  # Show first 5 points
                coords = format_gps_coordinates(point.latitude, point.longitude)
                print(f"  Point {i+1}: {coords}, Alt: {point.altitude:.1f}m")
                if point.speed:
                    print(f"    Speed: {point.speed:.1f} m/s")
                if point.heading:
                    print(f"    Heading: {point.heading:.1f}°")
        else:
            print("No GPS data found in video")
    else:
        print("Usage: python gps_extractor.py <video_file>")