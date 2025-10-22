"""
Video processing service for PAPI measurements
Enhanced with computer vision techniques from the prototype
"""
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
import os
import json
import logging
from dataclasses import dataclass
import math
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.offline as pyo
import subprocess
import struct
import re
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger(__name__)


def convert_to_h264(video_path: str) -> bool:
    """
    Convert video to H.264 using ffmpeg software encoder.
    This works reliably in Docker containers without hardware encoding.

    Args:
        video_path: Path to the video file to convert

    Returns:
        True if conversion successful, False otherwise
    """
    try:
        temp_path = video_path + ".temp.mp4"

        # Use ffmpeg with libx264 software encoder
        # -c:v libx264: Use H.264 software encoder (works in Docker)
        # -preset fast: Good balance of speed/quality
        # -crf 23: Constant quality (lower = better, 23 is good default)
        # -pix_fmt yuv420p: Ensures broad compatibility
        cmd = [
            'ffmpeg', '-y',  # Overwrite output
            '-i', video_path,  # Input file
            '-c:v', 'libx264',  # Use H.264 software encoder
            '-preset', 'fast',  # Encoding speed
            '-crf', '23',  # Quality (lower = better)
            '-pix_fmt', 'yuv420p',  # Pixel format for compatibility
            '-c:a', 'copy',  # Copy audio if exists
            temp_path
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0 and os.path.exists(temp_path):
            # Replace original with H.264 version
            os.replace(temp_path, video_path)
            logger.info(f"✓ Converted video to H.264: {video_path}")
            return True
        else:
            logger.warning(f"ffmpeg conversion failed: {result.stderr.decode()}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"ffmpeg conversion timed out for {video_path}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False
    except Exception as e:
        logger.error(f"Error converting video to H.264: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False


class GPUAccelerator:
    """GPU acceleration utilities for OpenCV operations"""
    
    def __init__(self):
        self.gpu_enabled = False
        self.opencl_available = False
        self._initialize_gpu()
    
    def _initialize_gpu(self):
        """Initialize GPU acceleration if available"""
        try:
            # Check OpenCL availability (works on M1/M2/M3 Macs)
            if hasattr(cv2.ocl, 'haveOpenCL') and cv2.ocl.haveOpenCL():
                cv2.ocl.setUseOpenCL(True)
                self.opencl_available = cv2.ocl.useOpenCL()
                if self.opencl_available:
                    device = cv2.ocl.Device.getDefault()
                    logger.info(f"OpenCL GPU acceleration enabled: {device.name()} ({device.maxComputeUnits()} cores)")
                    self.gpu_enabled = True
                else:
                    logger.warning("OpenCL available but failed to enable")
            else:
                logger.info("OpenCL not available - using CPU processing")
                
        except Exception as e:
            logger.warning(f"GPU initialization failed: {e}")
            self.gpu_enabled = False
    
    def is_enabled(self) -> bool:
        """Check if GPU acceleration is enabled"""
        return self.gpu_enabled
    
    def cvtColor_gpu(self, src, code):
        """GPU-accelerated color space conversion"""
        if self.gpu_enabled:
            try:
                # Upload to GPU, process, download
                gpu_src = cv2.UMat(src)
                gpu_dst = cv2.cvtColor(gpu_src, code)
                return gpu_dst.get()
            except:
                pass
        # Fallback to CPU
        return cv2.cvtColor(src, code)
    
    def threshold_gpu(self, src, thresh, maxval, type):
        """GPU-accelerated thresholding"""
        if self.gpu_enabled:
            try:
                gpu_src = cv2.UMat(src)
                _, gpu_dst = cv2.threshold(gpu_src, thresh, maxval, type)
                return gpu_dst.get()
            except:
                pass
        # Fallback to CPU
        _, dst = cv2.threshold(src, thresh, maxval, type)
        return dst
    
    def morphologyEx_gpu(self, src, op, kernel, iterations=1):
        """GPU-accelerated morphological operations"""
        if self.gpu_enabled:
            try:
                gpu_src = cv2.UMat(src)
                gpu_dst = cv2.morphologyEx(gpu_src, op, kernel, iterations=iterations)
                return gpu_dst.get()
            except:
                pass
        # Fallback to CPU
        return cv2.morphologyEx(src, op, kernel, iterations=iterations)
    
    def bitwise_or_gpu(self, src1, src2):
        """GPU-accelerated bitwise OR"""
        if self.gpu_enabled:
            try:
                gpu_src1 = cv2.UMat(src1)
                gpu_src2 = cv2.UMat(src2)
                gpu_dst = cv2.bitwise_or(gpu_src1, gpu_src2)
                return gpu_dst.get()
            except:
                pass
        # Fallback to CPU
        return cv2.bitwise_or(src1, src2)
    
    def resize_gpu(self, src, size, interpolation=cv2.INTER_LINEAR):
        """GPU-accelerated resize"""
        if self.gpu_enabled:
            try:
                gpu_src = cv2.UMat(src)
                gpu_dst = cv2.resize(gpu_src, size, interpolation=interpolation)
                return gpu_dst.get()
            except:
                pass
        # Fallback to CPU
        return cv2.resize(src, size, interpolation=interpolation)


class FrameProcessingCache:
    """Cache for expensive operations to avoid recomputation"""
    
    def __init__(self, max_cache_size: int = 100):
        self.gps_cache = {}  # frame_number -> GPSData
        self.processed_frames = {}  # frame_number -> processed_data
        self.max_cache_size = max_cache_size
        self._lock = threading.Lock()
    
    def get_gps_data(self, frame_number: int) -> Optional['GPSData']:
        """Get cached GPS data for frame"""
        with self._lock:
            return self.gps_cache.get(frame_number)
    
    def set_gps_data(self, frame_number: int, gps_data: 'GPSData'):
        """Cache GPS data for frame"""
        with self._lock:
            if len(self.gps_cache) >= self.max_cache_size:
                # Remove oldest entry
                oldest = min(self.gps_cache.keys())
                del self.gps_cache[oldest]
            self.gps_cache[frame_number] = gps_data
    
    def clear(self):
        """Clear all cached data"""
        with self._lock:
            self.gps_cache.clear()
            self.processed_frames.clear()


class BatchFrameProcessor:
    """Process frames in batches for better GPU utilization"""
    
    def __init__(self, batch_size: int = 8, num_workers: int = 2):
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.gpu_accelerator = GPUAccelerator()
        self.cache = FrameProcessingCache()
    
    def preprocess_frames_batch(self, frames: List[np.ndarray]) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Preprocess a batch of frames for light detection"""
        results = []
        
        if self.gpu_accelerator.is_enabled():
            # GPU batch processing
            for frame in frames:
                # Convert to HSV using GPU
                hsv = self.gpu_accelerator.cvtColor_gpu(frame, cv2.COLOR_BGR2HSV)
                value_channel = hsv[:, :, 2]
                
                # Create brightness mask using GPU
                bright_mask = self.gpu_accelerator.threshold_gpu(value_channel, 150, 255, cv2.THRESH_BINARY)
                
                results.append((bright_mask, value_channel))
        else:
            # CPU batch processing with threading
            def process_single_frame(frame):
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                value_channel = hsv[:, :, 2]
                _, bright_mask = cv2.threshold(value_channel, 150, 255, cv2.THRESH_BINARY)
                return (bright_mask, value_channel)
            
            with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
                results = list(executor.map(process_single_frame, frames))
        
        return results


@dataclass
class DetectedLight:
    """Represents a detected light object"""
    x: float
    y: float
    width: float
    height: float
    confidence: float
    class_name: str
    brightness: float
    r: int
    g: int
    b: int
    frame_num: int = 0
    timestamp_ms: float = 0.0
    intensity: float = 0.0
    # GPS and drone data
    drone_latitude: Optional[float] = None
    drone_longitude: Optional[float] = None
    drone_altitude: Optional[float] = None
    # PAPI light reference position
    papi_latitude: Optional[float] = None
    papi_longitude: Optional[float] = None
    papi_elevation: Optional[float] = None


@dataclass
class GPSData:
    """Represents GPS data for a specific timestamp/frame"""
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
    """Extract GPS metadata from drone video files"""
    
    def __init__(self):
        self.supported_formats = ['.mp4', '.mov', '.avi', '.mkv']
        
    def extract_gps_data(self, video_path: str) -> List[GPSData]:
        """
        Extract GPS data from video file using multiple methods.
        Tries different extraction methods in order of reliability.
        """
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            logger.error(f"Video file not found: {video_path}")
            return []
        
        logger.info(f"Extracting GPS data from: {video_path}")
        
        # Method 1: Try DJI SRT file first (most reliable for DJI drones)
        logger.debug("Trying DJI SRT extraction...")
        try:
            gps_data = self._extract_from_dji_srt(video_path_obj)
            if gps_data:
                logger.info(f"Extracted {len(gps_data)} GPS points from DJI SRT file")
                return gps_data
        except Exception as e:
            logger.debug(f"DJI SRT extraction failed: {e}")
        
        # Method 2: Try exiftool for DJI embedded frame metadata (most accurate)
        logger.debug("Trying exiftool frame extraction...")
        try:
            gps_data = self._extract_with_exiftool_frames(video_path_obj)
            if gps_data:
                logger.info(f"Extracted {len(gps_data)} GPS points using exiftool frame data")
                return gps_data
        except Exception as e:
            logger.debug(f"exiftool frame extraction failed: {e}")
        
        # Method 3: Try ffprobe for standard GPS metadata
        logger.debug("Trying ffprobe extraction...")
        try:
            gps_data = self._extract_with_ffprobe(video_path_obj)
            if gps_data:
                logger.info(f"Extracted {len(gps_data)} GPS points using ffprobe")
                return gps_data
        except Exception as e:
            logger.debug(f"ffprobe extraction failed: {e}")
        
        logger.warning(f"No GPS data found in {video_path} - will use fallback data")
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
    
    def _extract_with_exiftool_frames(self, video_path: Path) -> List[GPSData]:
        """Extract GPS data from DJI embedded frame metadata using exiftool"""
        try:
            # Check if exiftool is available
            check_cmd = ['which', 'exiftool']
            check_result = subprocess.run(check_cmd, capture_output=True)
            if check_result.returncode != 0:
                logger.debug("exiftool not found, skipping this method")
                return []
            
            # Extract embedded frame GPS data (DJI format)
            cmd = ['exiftool', '-ee', '-G', '-a', str(video_path)]
            logger.debug("Extracting embedded GPS with exiftool -ee...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
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
                    return gps_data
            
            return []
            
        except Exception as e:
            logger.debug(f"exiftool frame extraction failed: {e}")
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
        
        # Check if GPS data has frame numbers - use those for more accurate interpolation
        has_frame_numbers = all(p.frame_number is not None for p in gps_data)
        
        if has_frame_numbers:
            # Use frame numbers for interpolation (more accurate for DJI videos)
            before_point = None
            after_point = None
            
            for i, gps_point in enumerate(gps_data):
                if gps_point.frame_number <= frame_num:
                    before_point = gps_point
                if gps_point.frame_number >= frame_num and after_point is None:
                    after_point = gps_point
                    break
        else:
            # Fall back to timestamp-based interpolation
            # Find surrounding GPS points for interpolation
            before_point = None
            after_point = None
            
            for i, gps_point in enumerate(gps_data):
                if gps_point.timestamp_ms <= target_timestamp_ms:
                    before_point = gps_point
                if gps_point.timestamp_ms >= target_timestamp_ms and after_point is None:
                    after_point = gps_point
                    break
        
        # If exact match found (check frame number)
        if before_point and has_frame_numbers and before_point.frame_number == frame_num:
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
            if has_frame_numbers:
                # Use frame numbers for interpolation
                frame_diff = after_point.frame_number - before_point.frame_number
                if frame_diff > 0:
                    factor = (frame_num - before_point.frame_number) / frame_diff
                else:
                    factor = 0
            else:
                # Use timestamps for interpolation
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


class RunwayLightDetector:
    """Advanced light detection using computer vision techniques from prototype with GPU acceleration"""
    
    def __init__(self, brightness_threshold: int = 150, 
                 min_area: int = 5, 
                 max_area: int = 5000,
                 saturation_threshold: int = 240,
                 use_gpu: bool = True):
        self.brightness_threshold = brightness_threshold
        self.min_area = min_area
        self.max_area = max_area
        self.saturation_threshold = saturation_threshold
        
        # Initialize GPU acceleration
        self.gpu_accelerator = GPUAccelerator() if use_gpu else None
        if self.gpu_accelerator and self.gpu_accelerator.is_enabled():
            logger.info("Light detector initialized with GPU acceleration")
        else:
            logger.info("Light detector initialized with CPU processing")
        
    def preprocess_for_lights(self, frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Preprocess frame to enhance light detection with GPU acceleration"""
        # Convert to HSV for better light detection using GPU
        if self.gpu_accelerator and self.gpu_accelerator.is_enabled():
            hsv = self.gpu_accelerator.cvtColor_gpu(frame, cv2.COLOR_BGR2HSV)
        else:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Extract value channel (brightness)
        value_channel = hsv[:, :, 2]
        
        # Apply CLAHE for contrast enhancement (CPU-only operation)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(value_channel)
        
        # Create multiple masks for different light conditions using GPU
        if self.gpu_accelerator and self.gpu_accelerator.is_enabled():
            # 1. Direct bright spots
            bright_mask = self.gpu_accelerator.threshold_gpu(value_channel, self.brightness_threshold, 255, cv2.THRESH_BINARY)
            
            # 2. Saturated areas (very bright lights often saturate)
            saturated_mask = self.gpu_accelerator.threshold_gpu(value_channel, self.saturation_threshold, 255, cv2.THRESH_BINARY)
            
            # 3. Enhanced bright regions
            enhanced_mask = self.gpu_accelerator.threshold_gpu(enhanced, 200, 255, cv2.THRESH_BINARY)
            
            # Combine masks using GPU
            combined_mask = self.gpu_accelerator.bitwise_or_gpu(bright_mask, saturated_mask)
            combined_mask = self.gpu_accelerator.bitwise_or_gpu(combined_mask, enhanced_mask)
            
            # Morphological operations using GPU
            kernel = np.ones((3,3), np.uint8)
            combined_mask = self.gpu_accelerator.morphologyEx_gpu(combined_mask, cv2.MORPH_CLOSE, kernel)
            combined_mask = self.gpu_accelerator.morphologyEx_gpu(combined_mask, cv2.MORPH_OPEN, kernel)
        else:
            # CPU fallback
            bright_mask = cv2.threshold(value_channel, self.brightness_threshold, 255, cv2.THRESH_BINARY)[1]
            saturated_mask = cv2.threshold(value_channel, self.saturation_threshold, 255, cv2.THRESH_BINARY)[1]
            enhanced_mask = cv2.threshold(enhanced, 200, 255, cv2.THRESH_BINARY)[1]
            
            combined_mask = cv2.bitwise_or(bright_mask, saturated_mask)
            combined_mask = cv2.bitwise_or(combined_mask, enhanced_mask)
            
            kernel = np.ones((3,3), np.uint8)
            combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
            combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
        
        return combined_mask, value_channel
        
    def detect_lights(self, frame: np.ndarray) -> List[DetectedLight]:
        """Detect all bright spots and lights in frame"""
        lights = []
        
        # Preprocess frame
        mask, value_channel = self.preprocess_for_lights(frame)
        
        # Find contours of bright regions
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            if self.min_area <= area <= self.max_area:
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                
                # Get center point
                cx = x + w/2
                cy = y + h/2
                
                # Create mask for this specific light
                light_mask = np.zeros(mask.shape, dtype=np.uint8)
                cv2.drawContours(light_mask, [contour], -1, 255, -1)
                
                # Extract RGB values within the light region
                mean_vals = cv2.mean(frame, mask=light_mask)
                b, g, r = mean_vals[:3]
                
                # Calculate brightness and intensity
                brightness = np.mean([r, g, b])
                
                # Get peak intensity
                roi = value_channel[y:y+h, x:x+w]
                intensity = np.max(roi) if roi.size > 0 else brightness
                
                # Determine light type based on characteristics
                class_name = self.classify_light(r, g, b, area, intensity)
                
                light = DetectedLight(
                    x=cx,
                    y=cy,
                    width=w,
                    height=h,
                    confidence=min(1.0, intensity/255.0),  # Confidence based on intensity
                    class_name=class_name,
                    brightness=brightness,
                    r=int(r),
                    g=int(g),
                    b=int(b)
                )
                lights.append(light)
        
        return lights
    
    def classify_light(self, r: float, g: float, b: float, area: float, intensity: float) -> str:
        """Classify light based on color and characteristics with priority for high-intensity PAPI lights"""
        # Normalize RGB values
        total = r + g + b
        if total == 0:
            return "unknown_light"
        
        r_norm = r / total
        g_norm = g / total
        b_norm = b / total
        
        # Priority 1: Very high intensity lights (likely PAPI)
        if intensity > 220:
            return "high_intensity_light"
        
        # Priority 2: PAPI lights are usually white/red with high intensity
        if intensity > 180:
            if r_norm > 0.4:
                if g_norm < 0.3:
                    return "red_light"
                else:
                    return "white_light"
            # White lights (balanced RGB) with high intensity
            if abs(r_norm - 0.33) < 0.15 and abs(g_norm - 0.33) < 0.15:
                return "white_light"
        
        # Priority 3: Standard color-based classification for lower intensity lights
        # PAPI lights with moderate intensity
        if r_norm > 0.4 and intensity > 150:
            if g_norm < 0.3:
                return "red_light"
            else:
                return "white_light"
        
        # Green taxiway lights
        if g_norm > 0.4:
            return "green_light"
        
        # Blue taxiway edge lights
        if b_norm > 0.4:
            return "blue_light"
        
        # Yellow/amber lights
        if r_norm > 0.35 and g_norm > 0.35 and b_norm < 0.3:
            return "yellow_light"
        
        # White lights (balanced RGB)
        if abs(r_norm - 0.33) < 0.1 and abs(g_norm - 0.33) < 0.1:
            return "white_light"
        
        return "runway_light"


class VideoProcessor:
    """Process drone videos for PAPI light measurements"""

    @staticmethod
    def extract_recording_date(video_path: str) -> Optional[datetime]:
        """Extract recording date from video metadata"""
        try:
            # Try exiftool first (most reliable for DJI videos)
            try:
                cmd = ['exiftool', '-CreateDate', '-s', '-s', '-s', video_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and result.stdout.strip():
                    date_str = result.stdout.strip()
                    # Parse exiftool date format: "YYYY:MM:DD HH:MM:SS"
                    return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError, FileNotFoundError):
                pass

            # Try ffprobe as fallback
            try:
                cmd = [
                    'ffprobe', '-v', 'quiet', '-print_format', 'json',
                    '-show_format', video_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    import json
                    data = json.loads(result.stdout)
                    if 'format' in data and 'tags' in data['format']:
                        tags = data['format']['tags']
                        # Try different date tag names
                        for tag_name in ['creation_time', 'date', 'com.apple.quicktime.creationdate']:
                            if tag_name in tags:
                                date_str = tags[tag_name]
                                # Parse ISO format: "2024-01-15T14:30:45.000000Z"
                                try:
                                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                except ValueError:
                                    pass
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError, FileNotFoundError):
                pass

            # Fallback to file creation time
            file_stat = os.stat(video_path)
            return datetime.fromtimestamp(file_stat.st_ctime)

        except Exception as e:
            logger.warning(f"Could not extract recording date: {e}")
            return None

    @staticmethod
    def extract_first_frame(video_path: str, output_path: str) -> Dict:
        """Extract first frame from video and get metadata"""
        try:
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            
            if ret:
                cv2.imwrite(output_path, frame)
                
                # Extract metadata (this would come from drone telemetry)
                metadata = {
                    "frame_width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    "frame_height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    "fps": cap.get(cv2.CAP_PROP_FPS),
                    "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                }
                
                cap.release()
                return metadata
            
            cap.release()
            return {}
            
        except Exception as e:
            logger.error(f"Error extracting first frame: {e}")
            return {}
    
    @staticmethod
    def detect_lights(image_path: str, reference_points: List[Dict]) -> Dict[str, Dict]:
        """Detect PAPI lights in image using advanced computer vision with line detection"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Could not load image: {image_path}")
                return {}
            
            height, width = img.shape[:2]
            detector = RunwayLightDetector()
            
            # Detect all lights in the image
            detected_lights_list = detector.detect_lights(img)
            
            if not detected_lights_list:
                logger.warning("No lights detected, using default positions")
                return VideoProcessor._generate_default_positions(width, height)
            
            # Enhanced PAPI detection with line-based approach
            papi_candidates = VideoProcessor._filter_papi_candidates(detected_lights_list)
            
            if not papi_candidates:
                logger.warning("No high-intensity PAPI candidates found, using default positions")
                return VideoProcessor._generate_default_positions(width, height)
            
            # Find the best line of 4 PAPI lights
            best_papi_line = VideoProcessor._find_best_papi_line(papi_candidates)
            
            if best_papi_line:
                logger.info(f"Found PAPI line with {len(best_papi_line)} lights, avg intensity: {np.mean([l.intensity for l in best_papi_line]):.1f}")
                return VideoProcessor._convert_to_papi_positions(best_papi_line, width, height)
            else:
                logger.warning("No coherent PAPI light line found, using fallback method")
                return VideoProcessor._fallback_papi_detection(papi_candidates, width, height)
                
        except Exception as e:
            logger.error(f"Error in light detection: {e}")
            return VideoProcessor._generate_default_positions(width, height)
    
    @staticmethod
    def _filter_papi_candidates(detected_lights_list: List[DetectedLight]) -> List[DetectedLight]:
        """Filter lights that could be PAPI lights based on intensity, size, characteristics, and position

        Priority:
        1. Search from middle of image (PAPI lights are typically in center region)
        2. Prioritize red lights (PAPI starts at red)
        3. Filter by intensity, size, and brightness
        """
        if not detected_lights_list:
            return []

        papi_candidates = []

        # Get image dimensions from detected lights
        max_y = max(light.y for light in detected_lights_list) if detected_lights_list else 1000
        max_x = max(light.x for light in detected_lights_list) if detected_lights_list else 1000

        # Define middle region (center 60% horizontal, center 70% vertical)
        mid_x_start = max_x * 0.2
        mid_x_end = max_x * 0.8
        mid_y_start = max_y * 0.15
        mid_y_end = max_y * 0.85

        # Calculate area statistics for size-based filtering
        areas = [max(light.width * light.height, light.width * light.width, light.height * light.height)
                for light in detected_lights_list]
        avg_area = np.mean(areas) if areas else 0

        for light in detected_lights_list:
            light_area = max(light.width * light.height, light.width * light.width, light.height * light.height)

            # Calculate position-based bonus (prioritize middle region)
            in_middle_region = (mid_x_start <= light.x <= mid_x_end and
                              mid_y_start <= light.y <= mid_y_end)
            position_bonus = 50 if in_middle_region else 0

            # Calculate red light bonus (PAPI often starts with red lights)
            is_red = light.class_name == "red_light" or (
                hasattr(light, 'rgb_color') and
                light.rgb_color and
                light.rgb_color[0] > light.rgb_color[1] + 30 and
                light.rgb_color[0] > light.rgb_color[2] + 30
            )
            red_bonus = 40 if is_red else 0

            adjusted_intensity = light.intensity + position_bonus + red_bonus

            # Primary filter: High intensity PAPI lights (very bright) with bonuses
            if adjusted_intensity > 200:
                papi_candidates.append(light)
                logger.debug(f"Candidate: pos=({light.x:.0f},{light.y:.0f}), "
                           f"intensity={light.intensity:.0f}+{position_bonus}+{red_bonus}, "
                           f"class={light.class_name}")
                continue

            # Secondary filter: Large lights with good intensity in middle region
            if in_middle_region and light_area > avg_area * 1.2 and light.intensity > 140:
                papi_candidates.append(light)
                continue

            # Tertiary filter: Red lights with good intensity (prioritize red)
            if is_red and light.intensity > 160 and light_area > avg_area * 0.8:
                papi_candidates.append(light)
                continue

            # Quaternary filter: High brightness with specific light types in middle region
            if (in_middle_region and light.brightness > 170 and
                light.class_name in ["white_light", "red_light", "high_intensity_light"]):
                papi_candidates.append(light)
                continue

            # Fifth filter: Large lights with high brightness
            if light_area > avg_area * 1.5 and light.brightness > 160:
                papi_candidates.append(light)
                continue

            # Final filter: Very bright lights regardless of size
            if light.brightness > 220:
                papi_candidates.append(light)

        logger.info(f"Found {len(papi_candidates)} potential PAPI candidates "
                   f"(prioritized middle region and red lights)")
        return papi_candidates
    
    @staticmethod
    def _find_best_papi_line(candidates: List[DetectedLight]) -> List[DetectedLight]:
        """Find the best line of 4 PAPI lights using geometric and intensity analysis"""
        if len(candidates) < 4:
            return []
        
        best_line = []
        best_score = -1
        
        # Try different combinations of 4 lights
        from itertools import combinations
        
        for combo in combinations(candidates, 4):
            score = VideoProcessor._score_papi_line(list(combo))
            if score > best_score:
                best_score = score
                best_line = list(combo)
        
        # Require minimum score threshold for valid PAPI line
        if best_score > 0.5:
            return sorted(best_line, key=lambda x: x.x)  # Sort left to right
        
        return []
    
    @staticmethod
    def _score_papi_line(lights: List[DetectedLight]) -> float:
        """Score a potential PAPI light line based on geometric alignment, intensity, and size

        PAPI characteristics:
        - In same horizontal line (minimal Y variation)
        - Similar spacing between lights (evenly distributed)
        - Concentrated in same area (compact arrangement)
        - Similar size and intensity
        """
        if len(lights) != 4:
            return 0.0

        # Sort by x-coordinate (PAPI_A on left, PAPI_D on right)
        sorted_lights = sorted(lights, key=lambda x: x.x)

        # 1. Check horizontal alignment (Y-coordinates should be very similar)
        y_coords = [light.y for light in sorted_lights]
        y_std = np.std(y_coords)
        alignment_score = max(0, 1 - (y_std / 40))  # Stricter penalty for vertical misalignment

        # 2. Check spacing consistency (distances should be very similar)
        x_coords = [light.x for light in sorted_lights]
        spacings = [x_coords[i+1] - x_coords[i] for i in range(3)]
        avg_spacing = np.mean(spacings)
        spacing_std = np.std(spacings)
        # PAPI lights should have very consistent spacing
        spacing_consistency = max(0, 1 - (spacing_std / (avg_spacing * 0.2))) if avg_spacing > 0 else 0
        spacing_score = spacing_consistency

        # 3. Check region compactness (lights should be in concentrated area)
        # Calculate bounding box of all lights
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        bbox_width = max_x - min_x
        bbox_height = max_y - min_y

        # PAPI lights are in a compact horizontal line - height should be minimal
        compactness_score = max(0, 1 - (bbox_height / (bbox_width * 0.2))) if bbox_width > 0 else 0
        compactness_score = min(1.0, compactness_score)  # Cap at 1.0

        # 4. Check intensity consistency (PAPI lights should have similar high intensity)
        intensities = [light.intensity for light in sorted_lights]
        avg_intensity = np.mean(intensities)
        intensity_std = np.std(intensities)
        intensity_score = min(1.0, avg_intensity / 230)  # Reward high intensity
        intensity_consistency = max(0, 1 - (intensity_std / avg_intensity)) if avg_intensity > 0 else 0
        combined_intensity_score = (intensity_score * 0.7 + intensity_consistency * 0.3)

        # 5. Check size consistency (PAPI lights should be similar size)
        areas = [max(light.width * light.height, light.width * light.width, light.height * light.height)
                for light in sorted_lights]
        avg_area = np.mean(areas)
        area_std = np.std(areas)

        size_score = min(1.0, avg_area / 100)  # Reward larger average area
        size_consistency_score = max(0, 1 - (area_std / avg_area)) if avg_area > 0 else 0
        combined_size_score = (size_score * 0.5 + size_consistency_score * 0.5)

        # 6. Check that lights form a reasonable line length (not too close, not too far)
        line_length = bbox_width
        length_score = 1.0 if 100 < line_length < 500 else 0.5  # Reasonable PAPI spacing

        # 7. Bonus for red lights (PAPI often starts with red)
        red_count = sum(1 for light in sorted_lights if light.class_name == "red_light")
        red_bonus = min(0.1, red_count * 0.025)  # Small bonus for having red lights

        # Combined score with emphasis on alignment, spacing, and compactness
        total_score = (alignment_score * 0.25 +           # Horizontal alignment is critical
                      spacing_score * 0.20 +              # Even spacing is critical
                      compactness_score * 0.15 +          # Concentrated area is important
                      combined_intensity_score * 0.25 +   # High intensity is important
                      combined_size_score * 0.10 +        # Similar size is helpful
                      length_score * 0.05 +               # Reasonable length
                      red_bonus)                          # Bonus for red lights

        logger.debug(f"Line score: {total_score:.3f} (align:{alignment_score:.2f}, space:{spacing_score:.2f}, "
                    f"compact:{compactness_score:.2f}, intensity:{combined_intensity_score:.2f}, "
                    f"size:{combined_size_score:.2f}, length:{length_score:.2f}, red_bonus:{red_bonus:.2f})")

        return total_score
    
    @staticmethod
    def _convert_to_papi_positions(lights: List[DetectedLight], width: int, height: int) -> Dict[str, Dict]:
        """Convert detected lights to PAPI position format"""
        detected_lights = {}
        papi_names = ["PAPI_A", "PAPI_B", "PAPI_C", "PAPI_D"]
        
        for i, light in enumerate(lights):
            if i < len(papi_names):
                x_percent = (light.x / width) * 100
                y_percent = (light.y / height) * 100
                size_percent = max(8, min(15, (max(light.width, light.height) / width) * 100))
                
                light_area = max(light.width * light.height, light.width * light.width, light.height * light.height)
                logger.info(f"Assigning {papi_names[i]}: pos=({x_percent:.1f}%, {y_percent:.1f}%), "
                          f"intensity={light.intensity:.1f}, brightness={light.brightness:.1f}, "
                          f"area={light_area:.1f}px²")
                
                detected_lights[papi_names[i]] = {
                    "x": x_percent,
                    "y": y_percent,
                    "size": size_percent,
                    "width": (light.width / width) * 100,
                    "height": (light.height / height) * 100,
                    "confidence": light.confidence,
                    "class_name": light.class_name,
                    "brightness": light.brightness,
                    "intensity": light.intensity
                }
        
        return detected_lights
    
    @staticmethod
    def _fallback_papi_detection(candidates: List[DetectedLight], width: int, height: int) -> Dict[str, Dict]:
        """Fallback PAPI detection using combined intensity, size, position, and color scoring

        Priority:
        1. Middle region of image
        2. Red lights
        3. High intensity and size
        """
        # Get image center region boundaries
        mid_x_start = width * 0.2
        mid_x_end = width * 0.8
        mid_y_start = height * 0.15
        mid_y_end = height * 0.85

        # Calculate combined score for each candidate
        for candidate in candidates:
            light_area = max(candidate.width * candidate.height,
                           candidate.width * candidate.width,
                           candidate.height * candidate.height)

            # Normalize scores (intensity out of 255, area as relative score)
            intensity_score = candidate.intensity / 255.0
            size_score = min(1.0, light_area / 200)  # Normalize area to 0-1 scale

            # Position bonus (prioritize middle region)
            in_middle = (mid_x_start <= candidate.x <= mid_x_end and
                        mid_y_start <= candidate.y <= mid_y_end)
            position_score = 0.15 if in_middle else 0.0

            # Red light bonus (PAPI often starts with red)
            is_red = candidate.class_name == "red_light" or (
                hasattr(candidate, 'rgb_color') and
                candidate.rgb_color and
                candidate.rgb_color[0] > candidate.rgb_color[1] + 30 and
                candidate.rgb_color[0] > candidate.rgb_color[2] + 30
            )
            red_score = 0.10 if is_red else 0.0

            # Combined score: intensity (50%) + size (30%) + position (15%) + red (5%)
            candidate.combined_score = (intensity_score * 0.50 +
                                       size_score * 0.30 +
                                       position_score +
                                       red_score)

        # Sort by combined score (highest first)
        candidates.sort(key=lambda x: x.combined_score, reverse=True)

        # Take top 4 candidates with best combined score
        top_candidates = candidates[:4]

        logger.info(f"Fallback detection selected 4 lights with combined scores: "
                   f"{[f'{c.combined_score:.2f}' for c in top_candidates]} "
                   f"(middle region + red light priority)")

        # Sort by x-position for proper PAPI ordering (A->B->C->D from left to right)
        top_candidates.sort(key=lambda x: x.x)

        return VideoProcessor._convert_to_papi_positions(top_candidates, width, height)
    
    @staticmethod
    def _generate_default_positions(width: int, height: int) -> Dict[str, Dict]:
        """Generate default PAPI positions when detection fails"""
        detected_lights = {}
        base_x = width // 3
        base_y = height // 2
        
        for i, light_type in enumerate(["PAPI_A", "PAPI_B", "PAPI_C", "PAPI_D"]):
            x_percent = ((base_x + (i * 100)) / width) * 100
            y_percent = (base_y / height) * 100
            
            detected_lights[light_type] = {
                "x": x_percent,
                "y": y_percent,
                "size": 8
            }
        
        return detected_lights
    
    @staticmethod
    def process_frame(frame: np.ndarray, light_positions: Dict, 
                     drone_data: Dict, reference_points: Dict = None) -> Dict:
        """Process single frame for light measurements using actual tracked positions"""
        measurements = {}
        
        # Debug logging
        logger.info(f"Processing frame with light_positions: {light_positions}")
        
        height, width = frame.shape[:2]
        
        for light_name, pos in light_positions.items():
            if light_name not in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
                continue
                
            # Determine pixel coordinates
            if 'x' in pos and 'y' in pos and pos['x'] > 100 and pos['y'] > 100:
                # Use tracked position directly (already in pixel coordinates)
                pixel_x = int(pos['x'])
                pixel_y = int(pos['y'])
                pixel_size = int(pos.get('size', 20))
                # Check if RGB values are provided from tracking
                rgb_values = pos.get('rgb', None)
            else:
                # Treat as percentage coordinates (most common case)
                x, y = pos.get("x", 50), pos.get("y", 50)
                size = pos.get("size", pos.get("width", 8))
                
                pixel_x = int((x / 100) * width)
                pixel_y = int((y / 100) * height)
                # Use fixed pixel size for ROI extraction instead of percentage-based
                # PAPI lights are small, so 20-30 pixels radius is sufficient
                pixel_size = 40  # Fixed 40px ROI (20px radius)
                rgb_values = None  # Force RGB extraction
            
            # Extract RGB from frame if not provided by tracking
            if rgb_values is None:
                half_size = pixel_size // 2
                x1 = max(0, pixel_x - half_size)
                y1 = max(0, pixel_y - half_size)
                x2 = min(width, pixel_x + half_size)
                y2 = min(height, pixel_y + half_size)
                
                roi = frame[y1:y2, x1:x2]
                if roi.size > 0:
                    mean_rgb = cv2.mean(roi)[:3]
                    rgb_values = [int(mean_rgb[2]), int(mean_rgb[1]), int(mean_rgb[0])]  # BGR to RGB
                else:
                    rgb_values = [255, 255, 255]
            
            # Use RGB values from tracking if available
            if isinstance(rgb_values, list) and len(rgb_values) >= 3:
                r, g, b = rgb_values[0], rgb_values[1], rgb_values[2]
            else:
                r, g, b = 255, 255, 255
            
            # Calculate intensity
            intensity = np.mean([r, g, b])
            
            # Determine light status using enhanced classification
            status = classify_light_status(r, g, b, intensity)
            
            # Get reference point GPS coordinates for this PAPI light
            papi_gps = None
            if "ref_points" in drone_data and light_name in drone_data["ref_points"]:
                papi_gps = drone_data["ref_points"][light_name]
            elif reference_points and light_name in reference_points:
                papi_gps = reference_points[light_name]
            else:
                raise ValueError(
                    f"Reference point coordinates for {light_name} are required for measurements. "
                    f"Please ensure PAPI light GPS coordinates are configured in the database for this runway."
                )
            
            # Calculate angles and distances using GPS coordinates
            angle = calculate_angle(drone_data, papi_gps)
            distance_ground = calculate_ground_distance(drone_data, papi_gps)
            distance_direct = calculate_direct_distance(drone_data, papi_gps)

            # Calculate horizontal angle if runway heading is available
            horizontal_angle = None
            runway_heading = drone_data.get('runway_heading')
            if runway_heading is not None:
                try:
                    horizontal_angle = calculate_horizontal_angle(
                        papi_gps['latitude'],
                        papi_gps['longitude'],
                        drone_data['latitude'],
                        drone_data['longitude'],
                        runway_heading
                    )
                    logger.debug(f"{light_name}: Runway heading={runway_heading}°, Horizontal angle={horizontal_angle:.3f}°")
                except Exception as e:
                    logger.warning(f"Error calculating horizontal angle for {light_name}: {e}")
                    horizontal_angle = None
            else:
                logger.warning(f"Runway heading not available for horizontal angle calculation")

            measurements[light_name] = {
                "status": status,
                "rgb": {"r": r, "g": g, "b": b},
                "intensity": intensity,
                "angle": angle,
                "horizontal_angle": horizontal_angle,
                "distance_ground": distance_ground,
                "distance_direct": distance_direct
            }
        
        return measurements
    
    @staticmethod
    def create_light_video(video_path: str, light_position: Dict, 
                          output_path: str):
        """Create cropped video for single PAPI light"""
        cap = cv2.VideoCapture(video_path)
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        # Handle both old format (width/height) and new format (size)
        if "width" in light_position and "height" in light_position:
            x, y, w, h = light_position["x"], light_position["y"], \
                        light_position["width"], light_position["height"]
        else:
            # Convert from percentage-based position and size to pixel coordinates
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Convert percentage to pixels
            x_pct = light_position["x"]
            y_pct = light_position["y"] 
            size_pct = light_position["size"]
            
            x = int((x_pct / 100) * frame_width)
            y = int((y_pct / 100) * frame_height)
            w = h = int((size_pct / 100) * frame_width)  # Square region
        
        # Create video writer with mp4v codec (reliable in Docker)
        # Will convert to H.264 after creation using ffmpeg
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

        if not out.isOpened():
            logger.error(f"Failed to create video writer for {output_path}")
            cap.release()
            return

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Extract and write ROI
            roi = frame[y:y+h, x:x+w]
            out.write(roi)

        cap.release()
        out.release()

        # Convert to H.264 for better browser support
        convert_to_h264(output_path)


def calculate_angle(drone_data: Dict, light_pos: Dict) -> float:
    """Calculate angle between drone and light using GPS coordinates"""
    try:
        # Get drone position
        drone_lat = drone_data.get("latitude")
        drone_lon = drone_data.get("longitude") 
        drone_alt = drone_data.get("elevation", drone_data.get("altitude", 100))
        
        # Get PAPI light position (from reference points)
        papi_lat = light_pos.get("latitude")
        papi_lon = light_pos.get("longitude")
        papi_elevation = light_pos.get("elevation", 0)
        
        # Debug logging
        logger.debug(f"Angle calculation - Drone: lat={drone_lat}, lon={drone_lon}, alt={drone_alt}")
        logger.debug(f"Angle calculation - PAPI: lat={papi_lat}, lon={papi_lon}, elev={papi_elevation}")
        
        if None in [drone_lat, drone_lon, papi_lat, papi_lon]:
            logger.error(f"Missing GPS data - cannot calculate accurate PAPI angle without coordinates")
            raise ValueError("GPS coordinates are required for accurate PAPI angle calculation")
        
        # Calculate ground distance using Haversine formula
        ground_dist = haversine_distance(drone_lat, drone_lon, papi_lat, papi_lon)
        
        # Calculate height difference (drone elevation minus PAPI elevation)
        # This gives positive angles when drone is above PAPI (normal case for glide slope)
        height_diff = drone_alt - papi_elevation
        
        # Debug logging
        logger.debug(f"Angle calculation - Ground distance: {ground_dist:.1f}m, Height diff: {height_diff:.1f}m")
        
        # Calculate angle (elevation angle from horizontal)
        if ground_dist > 0:
            angle = np.degrees(np.arctan(height_diff / ground_dist))
        else:
            angle = 90.0 if height_diff > 0 else -90.0

        # Round to 3 decimal places for consistent precision with horizontal angles
        angle = round(angle, 3)

        logger.debug(f"Angle calculation - Final angle: {angle:.3f}")
        return angle
        
    except Exception as e:
        logger.warning(f"Error calculating angle: {e}")
        return 0.0


def calculate_ground_distance(drone_data: Dict, light_pos: Dict) -> float:
    """Calculate ground distance between drone and light using GPS"""
    try:
        drone_lat = drone_data.get("latitude")
        drone_lon = drone_data.get("longitude")
        papi_lat = light_pos.get("latitude")
        papi_lon = light_pos.get("longitude")
        
        if None in [drone_lat, drone_lon, papi_lat, papi_lon]:
            return 500.0  # Fallback distance
            
        return haversine_distance(drone_lat, drone_lon, papi_lat, papi_lon)
        
    except Exception as e:
        logger.warning(f"Error calculating ground distance: {e}")
        return 500.0


def calculate_direct_distance(drone_data: Dict, light_pos: Dict) -> float:
    """Calculate direct 3D distance between drone and light"""
    try:
        ground_dist = calculate_ground_distance(drone_data, light_pos)
        
        drone_alt = drone_data.get("elevation", drone_data.get("altitude", 100))
        papi_elevation = light_pos.get("elevation", 0)
        height_diff = drone_alt - papi_elevation
        
        return math.sqrt(ground_dist**2 + height_diff**2)
        
    except Exception as e:
        logger.warning(f"Error calculating direct distance: {e}")
        return 500.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on Earth (in meters)"""
    R = 6371000  # Earth's radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) * math.sin(delta_phi / 2) +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda / 2) * math.sin(delta_lambda / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the bearing (forward azimuth) from point 1 to point 2.
    Returns bearing in degrees (0-360), where 0 = North, 90 = East, 180 = South, 270 = West.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)

    bearing_rad = math.atan2(y, x)
    bearing_deg = math.degrees(bearing_rad)

    # Normalize to 0-360
    bearing_deg = (bearing_deg + 360) % 360

    return bearing_deg


def calculate_horizontal_angle(
    target_lat: float,
    target_lon: float,
    drone_lat: float,
    drone_lon: float,
    runway_heading: float
) -> float:
    """
    Calculate the horizontal angle between the runway centerline and the drone position.

    The angle is measured at the light/touch point, between the runway centerline
    (which extends in both directions) and the line to the drone position.
    Positive angles mean drone is to the right of the centerline when looking along the runway heading.
    Negative angles mean drone is to the left of the centerline.

    Args:
        target_lat: Latitude of the light/touch point
        target_lon: Longitude of the light/touch point
        drone_lat: Latitude of the drone
        drone_lon: Longitude of the drone
        runway_heading: Runway heading in degrees (0-360)

    Returns:
        Horizontal angle in degrees (-90 to +90), with 3 decimal places precision
    """
    # Calculate bearing from target to drone
    bearing_to_drone = calculate_bearing(target_lat, target_lon, drone_lat, drone_lon)

    # Calculate angle difference from runway heading
    angle_diff = bearing_to_drone - runway_heading

    # Normalize to -180 to +180 range
    if angle_diff > 180:
        angle_diff -= 360
    elif angle_diff < -180:
        angle_diff += 360

    # The runway centerline extends in both directions (heading and heading + 180°)
    # We want the angle to the nearest side of this line, so clamp to -90 to +90
    if angle_diff > 90:
        angle_diff = 180 - angle_diff
    elif angle_diff < -90:
        angle_diff = -180 - angle_diff

    # Round to 3 decimal places for high precision
    return round(angle_diff, 3)


def classify_light_status(r: float, g: float, b: float, intensity: float) -> str:
    """Classify light status as per PAPI requirements"""
    # Improved classification logic based on RGB values
    if intensity < 30:  # Very dark
        return "not_visible"
    
    # Normalize RGB values
    total = r + g + b
    if total == 0:
        return "not_visible"
    
    r_norm = r / total
    g_norm = g / total
    b_norm = b / total
    
    # Red light detection (PAPI red sector)
    if r_norm > 0.45 and g_norm < 0.35 and b_norm < 0.35:
        return "red"
    
    # White light detection (PAPI white sector)  
    if (abs(r_norm - 0.33) < 0.15 and 
        abs(g_norm - 0.33) < 0.15 and 
        abs(b_norm - 0.33) < 0.15 and
        intensity > 80):
        return "white"
    
    # Transition zone (color changing)
    if (0.35 < r_norm < 0.5 and 0.25 < g_norm < 0.4):
        return "transition"
    
    # Default to not_visible for unclear cases
    return "not_visible"


@dataclass
class TrackedPAPILight:
    """Represents a PAPI light tracked over multiple frames"""
    light_name: str  # PAPI_A, PAPI_B, PAPI_C, PAPI_D
    positions: List[Tuple[int, int]]  # (x, y) positions over time
    rgb_values: List[Tuple[int, int, int]]  # RGB values over time
    frame_numbers: List[int]  # Frame numbers where detected
    confidence_scores: List[float]  # Detection confidence scores
    sizes: List[int]  # Light sizes over time
    
    def get_last_position(self) -> Tuple[int, int]:
        """Get most recent position"""
        return self.positions[-1] if self.positions else (0, 0)
    
    def get_velocity(self, frame_gap: int = 1) -> Tuple[float, float]:
        """Calculate velocity based on recent positions"""
        if len(self.positions) < 2:
            return 0.0, 0.0
        
        # Use last few positions for velocity calculation
        recent_positions = self.positions[-min(5, len(self.positions)):]
        recent_frames = self.frame_numbers[-len(recent_positions):]
        
        if len(recent_positions) >= 2:
            dt = recent_frames[-1] - recent_frames[0]
            if dt > 0:
                vx = (recent_positions[-1][0] - recent_positions[0][0]) / dt
                vy = (recent_positions[-1][1] - recent_positions[0][1]) / dt
                return vx, vy
        
        return 0.0, 0.0
    
    def predict_position(self, frame_gap: int) -> Tuple[int, int]:
        """Predict position based on motion history"""
        if not self.positions:
            return 0, 0
        
        last_x, last_y = self.get_last_position()
        vx, vy = self.get_velocity()
        
        pred_x = int(last_x + vx * frame_gap)
        pred_y = int(last_y + vy * frame_gap)
        
        return pred_x, pred_y


class PAPILightTracker:
    """Advanced PAPI light tracker with motion prediction based on prototype algorithm"""
    
    def __init__(self, initial_positions: Dict, frame_width: int, frame_height: int):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.light_detector = RunwayLightDetector()
        self.max_distance = 50  # Maximum matching distance
        self.max_frame_gap = 20  # Maximum frames without detection
        
        # Initialize tracked lights from manual positions
        self.tracked_lights: Dict[str, TrackedPAPILight] = {}
        valid_lights_count = 0
        
        for light_name, pos in initial_positions.items():
            if light_name in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
                # Handle different position data formats
                if isinstance(pos, dict):
                    if 'x' in pos and 'y' in pos:
                        # Use provided coordinates
                        pixel_x = int((pos['x'] / 100) * frame_width)
                        pixel_y = int((pos['y'] / 100) * frame_height)
                        pixel_size = int((pos.get('size', 8) / 100) * frame_width)
                        valid_lights_count += 1
                    else:
                        # Use fallback default positions if coordinates are missing
                        logger.warning(f"Using fallback position for {light_name}: incomplete data: {pos}")
                        light_index = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'].index(light_name)
                        pixel_x = int((20 + light_index * 20) / 100 * frame_width)
                        pixel_y = int(50 / 100 * frame_height)
                        pixel_size = int(8 / 100 * frame_width)
                        valid_lights_count += 1
                else:
                    # Handle completely invalid position data
                    logger.warning(f"Using fallback position for {light_name}: invalid data: {pos}")
                    light_index = ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D'].index(light_name)
                    pixel_x = int((20 + light_index * 20) / 100 * frame_width)
                    pixel_y = int(50 / 100 * frame_height)
                    pixel_size = int(8 / 100 * frame_width)
                    valid_lights_count += 1
                    
                self.tracked_lights[light_name] = TrackedPAPILight(
                    light_name=light_name,
                    positions=[(pixel_x, pixel_y)],
                    rgb_values=[(255, 255, 255)],  # Default white
                    frame_numbers=[0],
                    confidence_scores=[0.0],
                    sizes=[pixel_size]
                )
        
        if valid_lights_count == 0:
            logger.error("No valid PAPI lights could be initialized for tracking")
        else:
            logger.info(f"Initialized {valid_lights_count} PAPI lights for tracking")
        
        self.global_motion = (0.0, 0.0)  # Estimated camera motion
        self.prev_detections = []  # Previous frame detections for motion estimation
    
    def estimate_global_motion(self, current_lights: List, prev_lights: List) -> Tuple[float, float]:
        """Estimate global camera motion between frames using detected lights"""
        if len(current_lights) < 3 or len(prev_lights) < 3:
            return 0.0, 0.0
        
        motions = []
        for curr_light in current_lights:
            best_dist = float('inf')
            best_prev = None
            
            for prev_light in prev_lights:
                # Only match lights of similar brightness and characteristics
                if abs(curr_light.brightness - prev_light.brightness) > 50:
                    continue
                
                dist = math.sqrt((curr_light.x - prev_light.x)**2 + (curr_light.y - prev_light.y)**2)
                if dist < 100 and dist < best_dist:  # Reasonable movement threshold
                    best_dist = dist
                    best_prev = prev_light
            
            if best_prev:
                dx = curr_light.x - best_prev.x
                dy = curr_light.y - best_prev.y
                motions.append((dx, dy))
        
        if len(motions) < 3:
            return 0.0, 0.0
        
        # Use median to get robust motion estimate (removes outliers)
        motions = np.array(motions)
        median_dx = np.median(motions[:, 0])
        median_dy = np.median(motions[:, 1])
        
        return median_dx, median_dy
    
    def update_frame(self, frame: np.ndarray, frame_number: int) -> Dict:
        """Update light positions for current frame using sophisticated tracking"""
        # Detect all lights in current frame
        detected_lights = self.light_detector.detect_lights(frame)
        
        # Estimate global motion if we have previous detections
        if self.prev_detections and len(self.prev_detections) >= 3 and len(detected_lights) >= 3:
            self.global_motion = self.estimate_global_motion(detected_lights, self.prev_detections)
        
        # Update each tracked PAPI light
        frame_positions = {}
        unmatched_detections = list(detected_lights)
        
        for light_name, tracked_light in self.tracked_lights.items():
            last_frame = tracked_light.frame_numbers[-1] if tracked_light.frame_numbers else 0
            frame_gap = frame_number - last_frame
            
            # Skip if track is too old
            if frame_gap > self.max_frame_gap:
                # Use global motion to predict position
                last_x, last_y = tracked_light.get_last_position()
                pred_x = int(last_x + self.global_motion[0] * frame_gap)
                pred_y = int(last_y + self.global_motion[1] * frame_gap)
                
                frame_positions[light_name] = {
                    'x': pred_x,
                    'y': pred_y,
                    'size': tracked_light.sizes[-1] if tracked_light.sizes else 20,
                    'rgb': tracked_light.rgb_values[-1] if tracked_light.rgb_values else [255, 255, 255],
                    'confidence': 0.1  # Low confidence for predicted position
                }
                continue
            
            # Predict where this light should be
            pred_x, pred_y = tracked_light.predict_position(frame_gap)
            
            # Apply global motion correction
            pred_x += int(self.global_motion[0] * frame_gap)
            pred_y += int(self.global_motion[1] * frame_gap)
            
            # Find best matching detection
            best_match = None
            best_score = float('inf')
            best_match_idx = -1
            
            for idx, detection in enumerate(unmatched_detections):
                # Distance to predicted position
                pred_distance = math.sqrt((detection.x - pred_x)**2 + (detection.y - pred_y)**2)
                
                # Distance to last known position
                last_x, last_y = tracked_light.get_last_position()
                last_distance = math.sqrt((detection.x - last_x)**2 + (detection.y - last_y)**2)
                
                # Combined score (weighted towards prediction)
                score = 0.7 * pred_distance + 0.3 * last_distance
                
                # Penalty for significant brightness change
                if tracked_light.rgb_values:
                    last_rgb = tracked_light.rgb_values[-1]
                    last_brightness = sum(last_rgb) / 3
                    brightness_diff = abs(detection.brightness - last_brightness)
                    score += brightness_diff * 0.05
                
                # Penalty for unreasonable movement
                if frame_gap > 0:
                    movement_per_frame = last_distance / frame_gap
                    if movement_per_frame > 30:  # More than 30 pixels per frame is suspicious
                        score += movement_per_frame * 0.5
                
                if score < self.max_distance and score < best_score:
                    best_score = score
                    best_match = detection
                    best_match_idx = idx
            
            if best_match:
                # Update tracked light with detection
                tracked_light.positions.append((int(best_match.x), int(best_match.y)))
                tracked_light.rgb_values.append((best_match.r, best_match.g, best_match.b))
                tracked_light.frame_numbers.append(frame_number)
                tracked_light.confidence_scores.append(best_match.confidence)
                tracked_light.sizes.append(max(best_match.width, best_match.height))
                
                # Remove from unmatched list
                if best_match_idx >= 0:
                    unmatched_detections.pop(best_match_idx)
                
                frame_positions[light_name] = {
                    'x': int(best_match.x),
                    'y': int(best_match.y),
                    'size': max(best_match.width, best_match.height),
                    'rgb': [best_match.r, best_match.g, best_match.b],
                    'confidence': best_match.confidence
                }
            else:
                # No detection found, use prediction
                last_rgb = tracked_light.rgb_values[-1] if tracked_light.rgb_values else [255, 255, 255]
                last_size = tracked_light.sizes[-1] if tracked_light.sizes else 20
                
                # Optionally update with interpolated position
                if frame_gap <= 5:  # Only interpolate for short gaps
                    tracked_light.positions.append((pred_x, pred_y))
                    tracked_light.rgb_values.append(last_rgb)
                    tracked_light.frame_numbers.append(frame_number)
                    tracked_light.confidence_scores.append(0.2)  # Low confidence
                    tracked_light.sizes.append(last_size)
                
                frame_positions[light_name] = {
                    'x': pred_x,
                    'y': pred_y,
                    'size': last_size,
                    'rgb': last_rgb,
                    'confidence': 0.2
                }
        
        # Store current detections for next iteration
        self.prev_detections = detected_lights
        
        return frame_positions


class PAPIVideoGenerator:
    """Generate individual PAPI light videos from the main video with GPU acceleration"""
    
    def __init__(self, output_dir: str, use_gpu: bool = True, batch_size: int = 8, progress_callback=None):
        self.output_dir = output_dir
        self.use_gpu = use_gpu
        self.batch_size = batch_size
        self.progress_callback = progress_callback  # Callback for progress updates
        os.makedirs(output_dir, exist_ok=True)

        # Initialize GPU acceleration and batch processor
        self.gpu_accelerator = GPUAccelerator() if use_gpu else None
        self.batch_processor = BatchFrameProcessor(batch_size=batch_size)
        self.frame_cache = FrameProcessingCache()

        if self.gpu_accelerator and self.gpu_accelerator.is_enabled():
            logger.info(f"Video generator initialized with GPU acceleration (batch size: {batch_size})")
        else:
            logger.info(f"Video generator initialized with CPU processing (batch size: {batch_size})")
    
    def generate_enhanced_main_video(self, video_path: str, session_id: str,
                                   light_positions: Dict, measurements_data: List[Dict],
                                   drone_telemetry: List[Dict] = None,
                                   reference_points: Dict = None) -> str:
        """Generate enhanced version of main video with real drone GPS data overlay and tracked PAPI light rectangles"""
        try:
            logger.info("=" * 80)
            logger.info(f"STARTING ENHANCED VIDEO GENERATION for session {session_id}")
            logger.info(f"Video path: {video_path}")
            logger.info(f"Light positions: {light_positions}")
            logger.info(f"Reference points: {list(reference_points.keys()) if reference_points else None}")
            logger.info(f"Measurements data frames: {len(measurements_data) if measurements_data else 0}")
            logger.info("=" * 80)

            # Extract real GPS data from video file
            logger.info("Step 1: Extracting GPS data from video file...")
            gps_extractor = GPSExtractor()
            real_gps_data = gps_extractor.extract_gps_data(video_path)
            if real_gps_data:
                logger.info(f"✓ Successfully extracted {len(real_gps_data)} GPS data points from video")
            else:
                logger.error("✗ No GPS data found in video - enhanced video generation will fail without GPS data")
                return ""

            logger.info("Step 2: Opening video file...")
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"✗ Failed to open video: {video_path}")
                return ""
            logger.info("✓ Video file opened successfully")

            # Get video properties
            logger.info("Step 3: Reading video properties...")
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            logger.info(f"✓ Video properties: {frame_width}x{frame_height}, {fps} fps, {total_frames} frames")

            if total_frames <= 0:
                logger.error(f"✗ Invalid video: zero frames in {video_path}")
                cap.release()
                return ""

            # Initialize PAPI light tracker
            logger.info("Step 4: Initializing PAPI light tracker...")
            light_tracker = PAPILightTracker(light_positions, frame_width, frame_height)
            logger.info(f"✓ Tracker initialized with {len(light_tracker.tracked_lights)} lights")

            # Check if any lights were successfully initialized
            if not light_tracker.tracked_lights:
                logger.error("✗ No PAPI lights initialized - cannot generate enhanced video")
                cap.release()
                return ""

            # Create output video path
            enhanced_video_filename = f"{session_id}_enhanced_main_video.mp4"
            enhanced_video_path = os.path.join(self.output_dir, enhanced_video_filename)
            logger.info(f"Step 5: Creating output video at: {enhanced_video_path}")

            # Create video writer with mp4v codec (reliable in Docker)
            # Will convert to H.264 after creation using ffmpeg
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(enhanced_video_path, fourcc, fps, (frame_width, frame_height))

            if not out.isOpened():
                logger.error(f"✗ Failed to initialize video writer for {enhanced_video_path}")
                cap.release()
                return ""
            logger.info("✓ Video writer initialized successfully")
            
            frame_count = 0
            frames_written = 0
            start_time = time.time()  # Initialize start time for progress tracking

            # Pre-compute GPS data for all frames to avoid repeated interpolation
            logger.info("Step 6: Pre-computing GPS data for all frames...")
            gps_cache = {}
            if real_gps_data:
                gps_start_time = time.time()
                gps_extractor = GPSExtractor()

                # Batch compute GPS data every 10 frames to reduce computation
                for i in range(0, total_frames, 10):
                    end_frame = min(i + 10, total_frames)
                    for frame_idx in range(i, end_frame):
                        interpolated_gps = gps_extractor.interpolate_gps_for_frame(real_gps_data, frame_idx, fps)
                        if interpolated_gps:
                            gps_cache[frame_idx] = {
                                "latitude": interpolated_gps.latitude,
                                "longitude": interpolated_gps.longitude,
                                "elevation": interpolated_gps.altitude,
                                "speed": interpolated_gps.speed or 0.0,
                                "heading": interpolated_gps.heading or 0.0,
                                "satellites": interpolated_gps.satellites,
                                "accuracy": interpolated_gps.accuracy
                            }

                gps_time = time.time() - gps_start_time
                logger.info(f"✓ GPS pre-computation completed in {gps_time:.2f}s for {len(gps_cache)} frames")
            else:
                logger.warning("No GPS data available for caching")
            
            # Process frames in batches for better GPU utilization
            logger.info(f"Step 7: Processing {total_frames} frames in batches of {self.batch_size}...")
            frame_batch = []
            frame_indices = []

            while True:
                ret, frame = cap.read()
                if not ret:
                    # Process remaining frames in batch
                    if frame_batch:
                        self._process_frame_batch(frame_batch, frame_indices, light_tracker, out, 
                                                total_frames, measurements_data, drone_telemetry, 
                                                reference_points, gps_cache, fps)
                        frames_written += len(frame_batch)
                    break
                
                frame_batch.append(frame)
                frame_indices.append(frame_count)
                frame_count += 1
                
                # Process batch when full or at end of video
                if len(frame_batch) >= self.batch_size:
                    try:
                        self._process_frame_batch(frame_batch, frame_indices, light_tracker, out, 
                                                total_frames, measurements_data, drone_telemetry, 
                                                reference_points, gps_cache, fps)
                        frames_written += len(frame_batch)

                        # Progress logging and callback
                        if frame_count % 100 <= self.batch_size:
                            elapsed = time.time() - start_time
                            fps_rate = frame_count / elapsed if elapsed > 0 else 0
                            logger.info(f"Enhanced video: processed {frame_count}/{total_frames} frames ({fps_rate:.1f} fps)")

                            # Update progress via callback (92% base + up to 3% for video generation)
                            if self.progress_callback:
                                progress = 92.0 + (frame_count / total_frames) * 3.0
                                self.progress_callback(progress, f"Generating enhanced video: frame {frame_count}/{total_frames}")
                            
                    except Exception as batch_error:
                        logger.warning(f"Error processing frame batch at {frame_indices[0]}: {batch_error}")
                        # Write original frames without enhancements
                        for original_frame in frame_batch:
                            out.write(original_frame)
                        frames_written += len(frame_batch)
                    
                    # Reset batch
                    frame_batch = []
                    frame_indices = []
            
            # Release resources
            logger.info("Step 8: Releasing video resources...")
            cap.release()
            out.release()
            logger.info(f"✓ Resources released. Total frames written: {frames_written}")

            # Verify that we actually wrote frames
            logger.info("Step 9: Verifying output file...")
            if frames_written == 0:
                logger.error(f"✗ No frames written to enhanced video - removing empty file")
                if os.path.exists(enhanced_video_path):
                    os.remove(enhanced_video_path)
                return ""

            # Verify file size
            if os.path.exists(enhanced_video_path):
                file_size = os.path.getsize(enhanced_video_path)
                logger.info(f"Output file size: {file_size} bytes")
                if file_size < 1000:  # Less than 1KB is likely invalid
                    logger.error(f"✗ Enhanced video file too small ({file_size} bytes) - removing")
                    os.remove(enhanced_video_path)
                    return ""
                total_time = time.time() - start_time
                logger.info("=" * 80)
                logger.info(f"✓ ENHANCED VIDEO GENERATION COMPLETE!")
                logger.info(f"  Output: {enhanced_video_path}")
                logger.info(f"  Size: {file_size:,} bytes")
                logger.info(f"  Frames: {frames_written}/{total_frames}")
                logger.info(f"  Time: {total_time:.2f}s")
                logger.info("=" * 80)

                # Convert to H.264 for better browser support
                logger.info("Converting enhanced video to H.264...")
                convert_to_h264(enhanced_video_path)
            else:
                logger.error("=" * 80)
                logger.error(f"✗ ENHANCED VIDEO FILE WAS NOT CREATED!")
                logger.error(f"  Expected path: {enhanced_video_path}")
                logger.error("=" * 80)
                return ""

            return enhanced_video_path
            
        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"✗ EXCEPTION DURING ENHANCED VIDEO GENERATION!")
            logger.error(f"  Error: {e}")
            import traceback
            logger.error(f"  Stack trace:\n{traceback.format_exc()}")
            logger.error("=" * 80)
            # Clean up any partial file
            enhanced_video_filename = f"{session_id}_enhanced_main_video.mp4"
            enhanced_video_path = os.path.join(self.output_dir, enhanced_video_filename)
            if os.path.exists(enhanced_video_path):
                logger.info(f"Removing partial file: {enhanced_video_path}")
                os.remove(enhanced_video_path)
            return ""
    
    def _process_frame_batch(self, frame_batch: List[np.ndarray], frame_indices: List[int], 
                            light_tracker, out, total_frames: int, measurements_data: List[Dict],
                            drone_telemetry: List[Dict], reference_points: Dict, 
                            gps_cache: Dict, fps: float):
        """Process a batch of frames for GPU optimization"""
        enhanced_frames = []
        
        for i, (frame, frame_idx) in enumerate(zip(frame_batch, frame_indices)):
            try:
                # Update light positions for current frame
                tracked_positions = light_tracker.update_frame(frame, frame_idx)
                
                # Get pre-computed GPS data
                drone_data = gps_cache.get(frame_idx)
                
                # Enhance frame with overlays using tracked positions and cached GPS data
                enhanced_frame = self._add_overlays_to_frame_with_tracking_optimized(
                    frame, tracked_positions, frame_idx, total_frames, 
                    measurements_data, drone_telemetry, reference_points, drone_data
                )
                
                enhanced_frames.append(enhanced_frame)
                
            except Exception as frame_error:
                logger.warning(f"Error processing frame {frame_idx}: {frame_error}")
                enhanced_frames.append(frame)  # Use original frame
        
        # Write all enhanced frames
        for enhanced_frame in enhanced_frames:
            out.write(enhanced_frame)
    
    def _add_overlays_to_frame_with_tracking_optimized(self, frame: np.ndarray, tracked_positions: Dict, 
                                                      frame_number: int, total_frames: int,
                                                      measurements_data: List[Dict] = None,
                                                      drone_telemetry: List[Dict] = None,
                                                      reference_points: Dict = None,
                                                      cached_drone_data: Dict = None) -> np.ndarray:
        """Optimized version with pre-computed GPS data"""
        enhanced_frame = frame.copy()
        height, width = frame.shape[:2]
        
        # Draw tracked PAPI light rectangles with current RGB values
        for light_name, pos in tracked_positions.items():
            if light_name not in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
                continue
            
            if not isinstance(pos, dict) or 'x' not in pos or 'y' not in pos:
                continue
                
            pixel_x = pos['x']
            pixel_y = pos['y']
            pixel_size = pos.get('size', 20)
            confidence = pos.get('confidence', 0.0)
            
            # Calculate rectangle bounds
            half_size = pixel_size // 2
            x1 = max(0, pixel_x - half_size)
            y1 = max(0, pixel_y - half_size)
            x2 = min(width, pixel_x + half_size)
            y2 = min(height, pixel_y + half_size)
            
            # Get RGB values from tracking if available
            rgb_values = pos.get('rgb', [255, 255, 255])
            if len(rgb_values) >= 3:
                r, g, b = rgb_values[0], rgb_values[1], rgb_values[2]
            else:
                r, g, b = 255, 255, 255
            
            # Determine rectangle color based on light status
            status = classify_light_status(r, g, b, np.mean([r, g, b]))
            color_map = {
                'red_light': (0, 0, 255),
                'white_light': (255, 255, 255), 
                'green_light': (0, 255, 0),
                'blue_light': (255, 0, 0),
                'transition': (0, 165, 255),
                'not_visible': (128, 128, 128),
            }
            rect_color = color_map.get(status, (0, 255, 255))

            # Draw rectangle and label
            thickness = 3  # Fixed thickness (confidence removed - not needed for user)
            cv2.rectangle(enhanced_frame, (x1, y1), (x2, y2), rect_color, thickness)
            
            # Calculate angle to PAPI light if we have GPS data
            angle_text = ""
            if cached_drone_data and reference_points:
                try:
                    drone_lat = cached_drone_data.get('latitude')
                    drone_lon = cached_drone_data.get('longitude') 
                    drone_alt = cached_drone_data.get('elevation', 0)
                    
                    # Get PAPI coordinates from reference points
                    # reference_points structure: {"PAPI_A": {"latitude": ..., "longitude": ..., "elevation": ...}}

                    if (drone_lat and drone_lon and light_name in reference_points and
                        reference_points[light_name].get('latitude') and reference_points[light_name].get('longitude')):

                        papi_lat = reference_points[light_name]['latitude']
                        papi_lon = reference_points[light_name]['longitude']
                        papi_alt = reference_points[light_name].get('elevation', 0)
                        
                        # Calculate angle using our existing function
                        drone_data = {
                            'latitude': drone_lat,
                            'longitude': drone_lon,
                            'elevation': drone_alt
                        }
                        papi_gps = {
                            'latitude': papi_lat,
                            'longitude': papi_lon,
                            'elevation': papi_alt
                        }

                        angle = calculate_angle(drone_data, papi_gps)
                        angle_text = f" {angle:.2f}"
                        
                except Exception as e:
                    # If angle calculation fails, continue without angle
                    logger.debug(f"Failed to calculate angle for {light_name}: {e}")
            
            label = f"{light_name}{angle_text}"
            # Confidence removed - not needed for user

            # Add text label (2x bigger font as requested)
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 4)[0]
            text_x = max(0, x1)
            text_y = max(text_size[1] + 5, y1 - 5)

            cv2.rectangle(enhanced_frame,
                         (text_x, text_y - text_size[1] - 5),
                         (text_x + text_size[0] + 5, text_y + 5),
                         (0, 0, 0), -1)
            cv2.putText(enhanced_frame, label, (text_x + 2, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 4)
        
        # Add optimized overlays
        self._add_drone_position_overlay_optimized(enhanced_frame, frame_number, cached_drone_data, reference_points)
        self._add_progress_bar(enhanced_frame, frame_number, total_frames)
        
        return enhanced_frame
    
    def _add_drone_position_overlay_optimized(self, frame: np.ndarray, frame_number: int, 
                                             cached_drone_data: Dict = None,
                                             reference_points: Dict = None):
        """Optimized overlay using pre-computed GPS data"""
        height, width = frame.shape[:2]
        
        # Create semi-transparent overlay box
        overlay = frame.copy()
        box_height = 220
        box_width = 420
        
        cv2.rectangle(overlay, (10, 10), (box_width, box_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Use cached drone data or fallback
        if cached_drone_data:
            drone_data = cached_drone_data
            gps_source = "📡 REAL GPS"
        else:
            raise ValueError(f"No GPS data available for frame {frame_number}. Video must contain GPS coordinates for processing.")
        
        # GPS quality indicators
        gps_quality = ""
        if drone_data.get('satellites'):
            gps_quality = f" ({drone_data['satellites']} sats)"
        if drone_data.get('accuracy'):
            gps_quality += f" ±{drone_data['accuracy']:.1f}m"
        
        # Calculate angle to touch point if reference points available
        touch_point_angle_text = ""
        if reference_points and 'TOUCH_POINT' in reference_points:
            try:
                drone_lat = drone_data.get('latitude')
                drone_lon = drone_data.get('longitude')
                drone_alt = drone_data.get('elevation', 0)

                touch_lat = reference_points['TOUCH_POINT'].get('latitude')
                touch_lon = reference_points['TOUCH_POINT'].get('longitude')
                touch_alt = reference_points['TOUCH_POINT'].get('elevation', 0)

                if drone_lat and drone_lon and touch_lat and touch_lon:
                    # Calculate angle to touch point
                    touch_data = {
                        'latitude': drone_lat,
                        'longitude': drone_lon,
                        'elevation': drone_alt
                    }
                    touch_gps = {
                        'latitude': touch_lat,
                        'longitude': touch_lon,
                        'elevation': touch_alt
                    }

                    touch_angle = calculate_angle(touch_data, touch_gps)
                    touch_point_angle_text = f"Touch Point Angle: {touch_angle:.2f}"
            except Exception as e:
                # If angle calculation fails, continue without angle
                logger.debug(f"Failed to calculate touch point angle: {e}")

        # Basic drone data (removed speed, added touch point angle)
        basic_texts = [
            f"Frame: {frame_number + 1} | {gps_source}{gps_quality}",
            f"Lat: {drone_data.get('latitude', 0):.6f}",
            f"Lon: {drone_data.get('longitude', 0):.6f}",
            f"Alt: {drone_data.get('elevation', 0):.1f}m",
            f"Heading: {drone_data.get('heading', 0):.2f}",
        ]

        # Add touch point angle if available (replaces speed parameter)
        if touch_point_angle_text:
            basic_texts.append(touch_point_angle_text)
        else:
            # Placeholder to maintain consistent overlay size
            basic_texts.append("")  # Empty line if no touch point angle
        
        # Draw information
        text_color = (255, 255, 255)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 2.25
        line_height = 80
        
        y_offset = 25
        for i, text in enumerate(basic_texts):
            y_pos = y_offset + i * line_height
            cv2.putText(frame, text, (20, y_pos), font, font_scale, text_color, 1)
    
    def _add_overlays_to_frame_with_tracking(self, frame: np.ndarray, tracked_positions: Dict, 
                                            frame_number: int, total_frames: int,
                                            measurements_data: List[Dict] = None,
                                            drone_telemetry: List[Dict] = None,
                                            reference_points: Dict = None,
                                            real_gps_data: List[GPSData] = None,
                                            fps: float = 30.0) -> np.ndarray:
        """Add drone position overlay and tracked PAPI light rectangles to frame"""
        enhanced_frame = frame.copy()
        height, width = frame.shape[:2]
        
        # Draw tracked PAPI light rectangles with current RGB values
        for light_name, pos in tracked_positions.items():
            if light_name not in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
                continue
            
            # Skip if position data is incomplete
            if not isinstance(pos, dict) or 'x' not in pos or 'y' not in pos:
                logger.warning(f"Skipping {light_name}: incomplete position data: {pos}")
                continue
                
            pixel_x = pos['x']
            pixel_y = pos['y']
            pixel_size = max(20, pos.get('size', 20))
            
            # Calculate rectangle bounds
            half_size = pixel_size // 2
            x1 = max(0, pixel_x - half_size)
            y1 = max(0, pixel_y - half_size)
            x2 = min(width, pixel_x + half_size)
            y2 = min(height, pixel_y + half_size)
            
            # Use actual RGB values from detection for rectangle color
            rgb = pos.get('rgb', [255, 255, 255])
            confidence = pos.get('confidence', 0.0)
            
            # Convert RGB to BGR for OpenCV
            rect_color = (int(rgb[2]), int(rgb[1]), int(rgb[0]))  # BGR format
            
            # Draw rectangle around PAPI light with detected color
            thickness = 3  # Fixed thickness (confidence removed - not needed for user)
            cv2.rectangle(enhanced_frame, (x1, y1), (x2, y2), rect_color, thickness)

            # Draw light name label
            label = f"{light_name}"
            # Confidence removed - not needed for user

            # Calculate text position (above the rectangle) - 2x bigger font as requested
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 4)[0]
            text_x = max(0, x1)
            text_y = max(text_size[1] + 5, y1 - 5)

            # Draw text background
            cv2.rectangle(enhanced_frame,
                         (text_x, text_y - text_size[1] - 5),
                         (text_x + text_size[0] + 5, text_y + 5),
                         (0, 0, 0), -1)

            # Draw text
            cv2.putText(enhanced_frame, label, (text_x + 2, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 4)
        
        # Keep the existing overlay methods for drone position, etc.
        self._add_drone_position_overlay(enhanced_frame, frame_number, drone_telemetry, reference_points, real_gps_data, fps)
        self._add_progress_bar(enhanced_frame, frame_number, total_frames)
        self._add_angle_overlay(enhanced_frame, frame_number, drone_telemetry, reference_points, real_gps_data, fps)
        
        return enhanced_frame

    def _add_overlays_to_frame(self, frame: np.ndarray, light_positions: Dict, 
                              frame_number: int, total_frames: int,
                              measurements_data: List[Dict] = None,
                              drone_telemetry: List[Dict] = None,
                              reference_points: Dict = None) -> np.ndarray:
        """Add drone position overlay and PAPI light rectangles to frame (legacy method)"""
        enhanced_frame = frame.copy()
        height, width = frame.shape[:2]
        
        # Draw PAPI light rectangles
        for light_name, pos in light_positions.items():
            # Convert percentage coordinates to pixel coordinates
            x_percent = pos.get("x", 0)
            y_percent = pos.get("y", 0)
            size_percent = pos.get("size", 8)
            
            pixel_x = int((x_percent / 100) * width)
            pixel_y = int((y_percent / 100) * height)
            pixel_size = max(20, int((size_percent / 100) * width))
            
            # Calculate rectangle bounds
            half_size = pixel_size // 2
            x1 = max(0, pixel_x - half_size)
            y1 = max(0, pixel_y - half_size)
            x2 = min(width, pixel_x + half_size)
            y2 = min(height, pixel_y + half_size)
            
            # Get light status color from measurements if available
            light_color = self._get_light_status_color(light_name, frame_number, measurements_data)
            
            # Draw rectangle around PAPI light
            cv2.rectangle(enhanced_frame, (x1, y1), (x2, y2), light_color, 3)
            
            # Draw center cross
            cv2.drawMarker(enhanced_frame, (pixel_x, pixel_y), light_color, 
                          cv2.MARKER_CROSS, 15, 2)
            
            # Add light name label
            label_pos = (x1, y1 - 10 if y1 > 20 else y2 + 25)
            cv2.putText(enhanced_frame, light_name, label_pos, 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, light_color, 2)
        
        # Add drone position overlay (legacy method - use fallback)
        self._add_drone_position_overlay(enhanced_frame, frame_number, drone_telemetry, reference_points, None, 30.0)
        
        # Add frame information overlay
        self._add_frame_info_overlay(enhanced_frame, frame_number, total_frames)
        
        return enhanced_frame
    
    def _get_light_status_color(self, light_name: str, frame_number: int, 
                              measurements_data: List[Dict] = None) -> Tuple[int, int, int]:
        """Get color based on light status from measurements"""
        if not measurements_data or frame_number >= len(measurements_data):
            return (0, 255, 255)  # Default yellow
        
        try:
            frame_data = measurements_data[frame_number]
            if light_name in frame_data:
                status = frame_data[light_name].get('status', 'not_visible')
                
                color_map = {
                    'red': (0, 0, 255),      # Red
                    'white': (255, 255, 255), # White
                    'transition': (0, 165, 255), # Orange
                    'not_visible': (128, 128, 128), # Gray
                }
                return color_map.get(status, (0, 255, 255))  # Default yellow
        except (IndexError, KeyError):
            pass
        
        return (0, 255, 255)  # Default yellow
    
    def _add_drone_position_overlay(self, frame: np.ndarray, frame_number: int, 
                                   drone_telemetry: List[Dict] = None,
                                   reference_points: Dict = None,
                                   real_gps_data: List[GPSData] = None,
                                   fps: float = 30.0):
        """Add drone position information overlay with angles to PAPI lights and touch point"""
        height, width = frame.shape[:2]
        
        # Create semi-transparent overlay box - expanded for more data
        overlay = frame.copy()
        box_height = 220  # Increased height for angle data
        box_width = 420   # Increased width for angle data
        
        # Position in top-left corner
        cv2.rectangle(overlay, (10, 10), (box_width, box_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Get real drone data for this frame
        drone_data = None
        
        # Priority 1: Use real GPS data extracted from video file
        if real_gps_data:
            gps_extractor = GPSExtractor()
            interpolated_gps = gps_extractor.interpolate_gps_for_frame(real_gps_data, frame_number, fps)
            if interpolated_gps:
                drone_data = {
                    "latitude": interpolated_gps.latitude,
                    "longitude": interpolated_gps.longitude, 
                    "elevation": interpolated_gps.altitude,
                    "speed": interpolated_gps.speed or 0.0,
                    "heading": interpolated_gps.heading or 0.0,
                    "satellites": interpolated_gps.satellites,
                    "accuracy": interpolated_gps.accuracy
                }
                logger.debug(f"Frame {frame_number}: Using real GPS data - Lat: {interpolated_gps.latitude:.6f}, Lon: {interpolated_gps.longitude:.6f}, Alt: {interpolated_gps.altitude:.1f}m")
        
        # Priority 2: Use provided drone telemetry
        if not drone_data and drone_telemetry and frame_number < len(drone_telemetry):
            drone_data = drone_telemetry[frame_number]
            logger.debug(f"Frame {frame_number}: Using provided telemetry data")
        
        # Priority 3: Fail if no GPS data is available
        if not drone_data:
            raise ValueError(f"No GPS data available for frame {frame_number}. Video must contain GPS coordinates for processing.")
        
        # Calculate angles to PAPI lights and touch point
        angles_data = self._calculate_angles_to_targets(drone_data, reference_points)
        
        # Draw drone position information
        text_color = (255, 255, 255)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 2.25
        line_height = 80
        
        # Basic drone data with GPS quality indicators
        gps_source = "REAL GPS" if real_gps_data else "FALLBACK"
        gps_quality = ""
        if drone_data.get('satellites'):
            gps_quality = f" ({drone_data['satellites']} sats)"
        if drone_data.get('accuracy'):
            gps_quality += f" ±{drone_data['accuracy']:.1f}m"
        
        basic_texts = [
            f"",
            f"Frame: {frame_number + 1} | {gps_source}{gps_quality}",
            f"Lat: {drone_data.get('latitude', 0):.6f}",
            f"Lon: {drone_data.get('longitude', 0):.6f}",
            f"Alt: {drone_data.get('elevation', 0):.1f}m",
            f"Heading: {drone_data.get('heading', 0):.2f}",
            "",  # Empty line separator
            "📐 Angles to Targets:"
        ]
        
        # Add basic information
        y_offset = 25
        for i, text in enumerate(basic_texts):
            y_pos = y_offset + i * line_height
            cv2.putText(frame, text, (20, y_pos), font, font_scale, text_color, 1)
        
        # Add angle information with color coding
        y_offset += len(basic_texts) * line_height + 5
        
        # PAPI light angles
        papi_colors = {
            'PAPI_A': (0, 255, 255),    # Yellow
            'PAPI_B': (255, 165, 0),    # Orange  
            'PAPI_C': (255, 0, 255),    # Magenta
            'PAPI_D': (0, 255, 0)       # Green
        }
        
        for i, (papi_id, angle_data) in enumerate(angles_data.items()):
            if papi_id.startswith('PAPI_'):
                color = papi_colors.get(papi_id, (255, 255, 255))
                angle_text = f"{papi_id}: {angle_data['angle']:.2f}° ({angle_data['distance']:.0f}m)"
                y_pos = y_offset + i * line_height
                cv2.putText(frame, angle_text, (25, y_pos), font, font_scale, color, 1)
        
        # Touch point angle (if available)
        if 'touch_point' in angles_data:
            touch_data = angles_data['touch_point']
            touch_text = f"Touch Pt: {touch_data['angle']:.2f}° ({touch_data['distance']:.0f}m)"
            y_pos = y_offset + len([k for k in angles_data.keys() if k.startswith('PAPI_')]) * line_height
            cv2.putText(frame, touch_text, (25, y_pos), font, font_scale, (255, 255, 255), 1)
    
    def _calculate_angles_to_targets(self, drone_data: Dict, reference_points: Dict = None) -> Dict:
        """Calculate angles from drone to all target points (PAPI lights and touch point)"""
        angles_data = {}

        if not reference_points:
            raise ValueError(
                "Reference points are required for angle calculations. "
                "Please ensure PAPI light and touch point coordinates are configured in the database for this runway."
            )

        drone_lat = drone_data.get('latitude')
        drone_lon = drone_data.get('longitude')
        drone_alt = drone_data.get('elevation')
        runway_heading = drone_data.get('runway_heading')

        # Validate that all required coordinates are present
        if drone_lat is None or drone_lon is None or drone_alt is None:
            raise ValueError(f"Incomplete GPS data in frame {frame_number}. Missing: " +
                           f"{'latitude ' if drone_lat is None else ''}" +
                           f"{'longitude ' if drone_lon is None else ''}" +
                           f"{'elevation' if drone_alt is None else ''}")

        for target_id, target_pos in reference_points.items():
            target_lat = target_pos.get('latitude')
            target_lon = target_pos.get('longitude')
            target_elevation = target_pos.get('elevation', 0)

            if target_lat is not None and target_lon is not None:
                # Calculate ground distance using Haversine formula
                ground_dist = haversine_distance(drone_lat, drone_lon, target_lat, target_lon)

                # Calculate height difference
                height_diff = drone_alt - target_elevation

                # Calculate vertical angle (elevation angle from horizontal)
                if ground_dist > 0:
                    vertical_angle = np.degrees(np.arctan(height_diff / ground_dist))
                else:
                    vertical_angle = 90.0 if height_diff > 0 else -90.0

                # Round to 3 decimal places for consistent precision
                vertical_angle = round(vertical_angle, 3)

                # Calculate horizontal angle (deviation from runway centerline)
                horizontal_angle = None
                if runway_heading is not None:
                    horizontal_angle = calculate_horizontal_angle(
                        target_lat, target_lon, drone_lat, drone_lon, runway_heading
                    )

                # Calculate direct distance
                direct_distance = math.sqrt(ground_dist**2 + height_diff**2)

                angles_data[target_id] = {
                    'angle': vertical_angle,
                    'horizontal_angle': horizontal_angle,
                    'distance': direct_distance,
                    'ground_distance': ground_dist,
                    'height_diff': height_diff
                }
            else:
                # Raise error if coordinates are not available - no fallback data
                raise ValueError(
                    f"Reference point coordinates for '{target_id}' are missing or incomplete. "
                    f"Required: latitude and longitude. Please ensure all reference points are properly configured."
                )

        return angles_data
    
    def _add_frame_info_overlay(self, frame: np.ndarray, frame_number: int, total_frames: int):
        """Add frame information overlay"""
        height, width = frame.shape[:2]
        
        # Progress bar
        bar_width = 300
        bar_height = 8
        bar_x = width - bar_width - 20
        bar_y = height - 40
        
        # Background bar
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), 
                     (50, 50, 50), -1)
        
        # Progress bar
        progress = frame_number / max(1, total_frames - 1)
        progress_width = int(bar_width * progress)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + progress_width, bar_y + bar_height), 
                     (0, 255, 0), -1)
        
        # Frame counter
        frame_text = f"{frame_number + 1}/{total_frames}"
        cv2.putText(frame, frame_text, (bar_x, bar_y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 2.5, (255, 255, 255), 3)
    
    def generate_papi_videos(self, video_path: str, session_id: str, light_positions: Dict,
                            measurements_data: List[Dict] = None) -> Dict[str, str]:
        """Generate individual videos for each PAPI light using tracking with angle information"""
        video_paths = {}
        
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                return video_paths

            # Get video properties
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # Initialize PAPI light tracker for individual videos
            light_tracker = PAPILightTracker(light_positions, frame_width, frame_height)
            
            # Create video writers for each PAPI light
            video_writers = {}
            light_regions = {}
            
            for light_name in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
                if light_name in light_positions:
                    # Initial region (will be updated by tracker)
                    pos = light_positions[light_name]
                    x_pct = pos['x']
                    y_pct = pos['y']
                    width_pct = pos.get('width', 2)  # Use actual detected width
                    height_pct = pos.get('height', 2)  # Use actual detected height
                    
                    x = int((x_pct / 100) * frame_width)
                    y = int((y_pct / 100) * frame_height)
                    light_width = int((width_pct / 100) * frame_width)
                    light_height = int((height_pct / 100) * frame_height)
                    
                    # Set region to capture light with minimal padding (will be resized to 100x100)
                    padding = max(light_width, light_height, 20)  # Use light size or minimum 20px padding
                    x1 = max(0, x - padding)
                    y1 = max(0, y - padding)
                    x2 = min(frame_width, x + padding)
                    y2 = min(frame_height, y + padding)
                    
                    light_regions[light_name] = (x1, y1, x2, y2)
                    
                    # Create output video path
                    video_filename = f"{session_id}_{light_name.lower()}_light.mp4"
                    video_output_path = os.path.join(self.output_dir, video_filename)
                    video_paths[light_name] = video_output_path
                    
                    # Create video writer with mp4v codec (reliable in Docker)
                    # Will convert to H.264 after creation using ffmpeg
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    video_writers[light_name] = cv2.VideoWriter(
                        video_output_path, fourcc, fps, (300, 350)  # Fixed 300x350 output size (50px for footer)
                    )
            
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Update light positions using tracker
                tracked_positions = light_tracker.update_frame(frame, frame_count)
                
                # Extract regions for each PAPI light using tracked positions
                for light_name in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
                    if light_name in video_writers and light_name in tracked_positions:
                        tracked_pos = tracked_positions[light_name]
                        
                        # Get tracked position and size
                        x = tracked_pos['x']
                        y = tracked_pos['y']
                        size = tracked_pos['size']
                        
                        # Calculate region with padding
                        padding = size * 2
                        x1 = max(0, x - padding)
                        y1 = max(0, y - padding)
                        x2 = min(frame_width, x + padding)
                        y2 = min(frame_height, y + padding)
                        
                        # Update the region size if needed (resize video writer if dimensions changed significantly)
                        original_x1, original_y1, original_x2, original_y2 = light_regions[light_name]
                        new_width = x2 - x1
                        new_height = y2 - y1
                        original_width = original_x2 - original_x1
                        original_height = original_y2 - original_y1
                        
                        # If size changed significantly, keep original size but center on new position
                        if abs(new_width - original_width) > 20 or abs(new_height - original_height) > 20:
                            # Keep original size, just center on new position
                            half_width = original_width // 2
                            half_height = original_height // 2
                            x1 = max(0, x - half_width)
                            y1 = max(0, y - half_height)
                            x2 = min(frame_width, x1 + original_width)
                            y2 = min(frame_height, y1 + original_height)
                            
                            # Adjust if hitting boundaries
                            if x2 == frame_width:
                                x1 = x2 - original_width
                            if y2 == frame_height:
                                y1 = y2 - original_height
                        
                        # Extract the region
                        light_frame = frame[y1:y2, x1:x2]
                        
                        if light_frame.size > 0:
                            # Get RGB values for color-coded text
                            rgb = tracked_pos.get('rgb', [255, 255, 255])
                            
                            # Resize the light region to 300x300
                            light_frame_resized = cv2.resize(light_frame, (300, 300))
                            
                            # Create final frame with white footer strip
                            final_frame = np.zeros((350, 300, 3), dtype=np.uint8)
                            
                            # Copy the resized light frame to the top part
                            final_frame[0:300, 0:300] = light_frame_resized
                            
                            # Create white footer strip (50px height)
                            final_frame[300:350, 0:300] = [255, 255, 255]  # White background
                            
                            # Add text to white footer strip
                            confidence = tracked_pos.get('confidence', 0.0)
                            
                            # Light name and frame info
                            info_text = f"{light_name} - Frame {frame_count}"
                            if confidence > 0:
                                info_text += f" ({confidence:.2f})"
                            
                            cv2.putText(final_frame, info_text, (5, 320), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 2.5, (0, 0, 0), 3)  # Black text on white
                            
                            # Add color-coded RGB values in footer (smaller font to prevent overlap)
                            y_pos = 345
                            font = cv2.FONT_HERSHEY_SIMPLEX
                            font_scale = 0.5
                            thickness = 1

                            # Red component
                            cv2.putText(final_frame, f"R:{rgb[0]:.0f}", (5, y_pos),
                                      font, font_scale, (0, 0, 255), thickness)  # Red color (BGR)

                            # Green component
                            cv2.putText(final_frame, f"G:{rgb[1]:.0f}", (60, y_pos),
                                      font, font_scale, (0, 255, 0), thickness)  # Green color (BGR)

                            # Blue component
                            cv2.putText(final_frame, f"B:{rgb[2]:.0f}", (115, y_pos),
                                      font, font_scale, (255, 0, 0), thickness)  # Blue color (BGR)

                            # Add angle information if measurements_data is available
                            if measurements_data and frame_count < len(measurements_data):
                                frame_measurements = measurements_data[frame_count]
                                if light_name in frame_measurements:
                                    angle = frame_measurements[light_name].get('angle')
                                    if angle is not None:
                                        angle_text = f"Angle: {angle:.2f}"
                                        cv2.putText(final_frame, angle_text, (170, y_pos),
                                                  font, font_scale, (0, 0, 0), thickness)  # Black text
                            
                            video_writers[light_name].write(final_frame)
                
                frame_count += 1

                # Progress logging and callback every 100 frames
                if frame_count % 100 == 0:
                    logger.info(f"Processed {frame_count}/{total_frames} frames for PAPI videos")

                    # Update progress via callback (87% base + up to 5% for PAPI video generation)
                    if self.progress_callback and total_frames > 0:
                        progress = 87.0 + (frame_count / total_frames) * 5.0
                        self.progress_callback(progress, f"Generating PAPI videos: frame {frame_count}/{total_frames}")
            
            # Release resources
            cap.release()
            for writer in video_writers.values():
                writer.release()

            # Convert all videos to H.264 for better browser support
            logger.info("Converting PAPI videos to H.264...")
            for light_name, video_path in video_paths.items():
                logger.info(f"Converting {light_name} video to H.264...")
                convert_to_h264(video_path)

            logger.info(f"Generated {len(video_paths)} PAPI light videos")
            return video_paths
            
        except Exception as e:
            logger.error(f"Error generating PAPI videos: {e}")
            return {}
    
    def _add_progress_bar(self, frame: np.ndarray, frame_number: int, total_frames: int):
        """Add progress bar overlay to frame"""
        # Fixed indentation
        height, width = frame.shape[:2]
        
        # Progress bar settings
        bar_width = 300
        bar_height = 8
        bar_x = width - bar_width - 20
        bar_y = height - 40
        
        # Background bar
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), 
                     (50, 50, 50), -1)
        
        # Progress bar
        progress = frame_number / max(1, total_frames - 1)
        progress_width = int(bar_width * progress)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + progress_width, bar_y + bar_height), 
                     (0, 255, 0), -1)
        
        # Frame counter
        frame_text = f"{frame_number + 1}/{total_frames}"
        cv2.putText(frame, frame_text, (bar_x, bar_y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 2.5, (255, 255, 255), 3)
    
    
    def _add_angle_overlay(self, frame: np.ndarray, frame_number: int, 
                          drone_telemetry: List[Dict] = None,
                          reference_points: Dict = None,
                          real_gps_data: List[GPSData] = None,
                          fps: float = 30.0):
        """Add angle information overlay to frame"""
        height, width = frame.shape[:2]
        
        # Get real drone data for this frame (same logic as main overlay)
        drone_data = None
        
        # Priority 1: Use real GPS data extracted from video file
        if real_gps_data:
            gps_extractor = GPSExtractor()
            interpolated_gps = gps_extractor.interpolate_gps_for_frame(real_gps_data, frame_number, fps)
            if interpolated_gps:
                drone_data = {
                    "latitude": interpolated_gps.latitude,
                    "longitude": interpolated_gps.longitude, 
                    "altitude": interpolated_gps.altitude,
                    "speed": interpolated_gps.speed or 0.0,
                    "heading": interpolated_gps.heading or 0.0
                }
        
        # Priority 2: Use provided drone telemetry
        if not drone_data and drone_telemetry and frame_number < len(drone_telemetry):
            drone_data = drone_telemetry[frame_number]
        
        # Priority 3: Fail if no GPS data is available  
        if not drone_data:
            raise ValueError(f"No GPS data available for frame {frame_number}. Video must contain GPS coordinates for processing.")
        
        # Calculate angles to PAPI lights and touch point if reference points available
        if reference_points:
            try:
                # Position angle info in the top-right corner
                info_x = width - 250
                info_y = 30
                line_height = 25
                
                # Semi-transparent background
                overlay = frame.copy()
                cv2.rectangle(overlay, (info_x - 10, info_y - 10), 
                             (width - 10, info_y + 5 * line_height), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
                
                # Calculate and display angles
                y_pos = info_y
                for papi_name in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
                    if papi_name in reference_points:
                        # Simple angle calculation (in real implementation, would use proper geodesic calculations)
                        papi_point = reference_points[papi_name]
                        # Use proper Haversine distance calculation for accurate angles
                        ground_dist = haversine_distance(
                            drone_data['latitude'], drone_data['longitude'],
                            papi_point.get('latitude'), papi_point.get('longitude')
                        )
                        alt_diff = drone_data['altitude'] - papi_point.get('elevation')
                        
                        # Correct angle calculation using proper ground distance
                        if ground_dist > 0:
                            angle = np.degrees(np.arctan(alt_diff / ground_dist))
                        else:
                            angle = 90.0 if alt_diff > 0 else -90.0
                        
                        angle_text = f"{papi_name}: {angle:.2f}"
                        cv2.putText(frame, angle_text, (info_x, y_pos), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                        y_pos += line_height
                
                # Touch point angle if available
                if 'TOUCH_POINT' in reference_points:
                    touch_point = reference_points['TOUCH_POINT']
                    # Use proper Haversine distance calculation for accurate angles
                    ground_dist = haversine_distance(
                        drone_data['latitude'], drone_data['longitude'],
                        touch_point.get('latitude'), touch_point.get('longitude')
                    )
                    alt_diff = drone_data['altitude'] - touch_point.get('elevation')
                    
                    # Correct angle calculation using proper ground distance
                    if ground_dist > 0:
                        angle = np.degrees(np.arctan(alt_diff / ground_dist))
                    else:
                        angle = 90.0 if alt_diff > 0 else -90.0
                    
                    angle_text = f"Touch Point: {angle:.2f}"
                    cv2.putText(frame, angle_text, (info_x, y_pos), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    
            except Exception as e:
                logger.warning(f"Error calculating angles: {e}")
        else:
            # Display placeholder when no reference points
            info_x = width - 200
            info_y = 30
            cv2.putText(frame, "Angles: No ref points", (info_x, info_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (128, 128, 128), 2)


class PAPIReportGenerator:
    """Generate comprehensive HTML reports for PAPI measurements"""
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_html_report(self, session_data: Dict, measurements: List[Dict], video_paths: Dict[str, str] = None, reference_points: Dict = None, enhanced_main_video_path: str = None) -> str:
        """Generate interactive HTML report with Plotly charts, embedded videos, and reference point coordinates"""
        try:
            # Organize data by PAPI light
            papi_data = {}
            timestamps = []
            
            for measurement in measurements:
                timestamp = measurement.get('timestamp', 0)
                timestamps.append(timestamp / 1000)  # Convert to seconds
                
                for papi_id in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
                    if papi_id not in papi_data:
                        papi_data[papi_id] = {
                            'r_values': [],
                            'g_values': [],
                            'b_values': [],
                            'status': [],
                            'intensity': [],
                            'angles': [],
                            'ground_distance': [],
                            'direct_distance': []
                        }
                    
                    if papi_id in measurement:
                        data = measurement[papi_id]
                        rgb = data.get('rgb', {'r': 0, 'g': 0, 'b': 0})
                        
                        papi_data[papi_id]['r_values'].append(rgb['r'])
                        papi_data[papi_id]['g_values'].append(rgb['g'])
                        papi_data[papi_id]['b_values'].append(rgb['b'])
                        papi_data[papi_id]['status'].append(data.get('status', 'not_visible'))
                        papi_data[papi_id]['intensity'].append(data.get('intensity', 0))
                        papi_data[papi_id]['angles'].append(data.get('angle', 0))
                        papi_data[papi_id]['ground_distance'].append(data.get('distance_ground', 0))
                        papi_data[papi_id]['direct_distance'].append(data.get('distance_direct', 0))
            
            # Generate HTML with interactive charts and videos
            html_content = self._create_html_template(
                session_data, papi_data, timestamps, video_paths or {}, 
                reference_points or {}, enhanced_main_video_path
            )
            
            # Save report
            report_filename = f"papi_report_{session_data.get('session_id', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            report_path = os.path.join(self.output_dir, report_filename)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"HTML report generated: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"Error generating HTML report: {e}")
            return ""
    
    def _create_html_template(self, session_data: Dict, papi_data: Dict, timestamps: List[float], video_paths: Dict[str, str], reference_points: Dict, enhanced_main_video_path: str = None) -> str:
        """Create HTML template with Plotly charts, embedded videos, and reference point coordinates"""
        
        # Create individual charts for each PAPI light
        charts_html = ""
        
        for papi_id in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
            if papi_id in papi_data and papi_data[papi_id]['r_values']:
                data = papi_data[papi_id]
                
                # Create RGB + Angle chart
                fig = make_subplots(
                    rows=2, cols=1,
                    subplot_titles=(f'{papi_id} RGB Values', f'{papi_id} Angle & Distances'),
                    vertical_spacing=0.1
                )
                
                # RGB traces
                fig.add_trace(go.Scatter(x=timestamps, y=data['r_values'], name='Red', 
                                       line=dict(color='red')), row=1, col=1)
                fig.add_trace(go.Scatter(x=timestamps, y=data['g_values'], name='Green',
                                       line=dict(color='green')), row=1, col=1)
                fig.add_trace(go.Scatter(x=timestamps, y=data['b_values'], name='Blue',
                                       line=dict(color='blue')), row=1, col=1)
                
                # Angle and distance traces
                fig.add_trace(go.Scatter(x=timestamps, y=data['angles'], name='Angle (degrees)',
                                       line=dict(color='purple')), row=2, col=1)
                fig.add_trace(go.Scatter(x=timestamps, y=data['ground_distance'], name='Ground Distance (m)',
                                       line=dict(color='orange')), row=2, col=1)
                
                fig.update_layout(
                    title=f'{papi_id} Analysis',
                    height=600,
                    showlegend=True
                )
                fig.update_xaxes(title_text="Time (seconds)")
                fig.update_yaxes(title_text="RGB Value", row=1, col=1)
                fig.update_yaxes(title_text="Angle (deg) / Distance (m)", row=2, col=1)
                
                chart_html = pyo.plot(fig, output_type='div', include_plotlyjs=False)
                
                # Add video player if video exists for this PAPI light
                video_html = ""
                if papi_id in video_paths and video_paths[papi_id]:
                    # Use API endpoint for video src with full hostname
                    light_name = papi_id.lower()  # papi_a, papi_b, etc.
                    # Import settings here to get the configured base URL
                    from app.core.config import settings
                    video_src = f"{settings.API_BASE_URL}/api/v1/papi-measurements/session/{session_data.get('session_id')}/papi-video/{light_name}"
                    video_html = f'''
                    <div class="video-container">
                        <h4>{papi_id} Light Video</h4>
                        <video width="400" height="300" controls>
                            <source src="{video_src}" type="video/mp4">
                            Your browser does not support the video tag.
                        </video>
                        <p class="video-description">
                            This video shows the {papi_id} light throughout the measurement flight.
                            The crosshair marks the light position and frame numbers are displayed.
                        </p>
                    </div>
                    '''
                
                # Add reference point coordinates if available
                coordinates_html = ""
                if papi_id in reference_points:
                    coords = reference_points[papi_id]
                    coordinates_html = f'''
                    <div class="coordinates-info">
                        <h5>📍 Reference Point Coordinates</h5>
                        <div class="coord-grid">
                            <div class="coord-item">
                                <span class="coord-label">Latitude:</span>
                                <span class="coord-value">{coords.get('latitude', 'N/A')}°</span>
                            </div>
                            <div class="coord-item">
                                <span class="coord-label">Longitude:</span>
                                <span class="coord-value">{coords.get('longitude', 'N/A')}°</span>
                            </div>
                            <div class="coord-item">
                                <span class="coord-label">Elevation:</span>
                                <span class="coord-value">{coords.get('elevation', 'N/A')} m</span>
                            </div>
                        </div>
                    </div>
                    '''
                
                # Combine chart, video, and coordinates in a layout
                charts_html += f'''
                <div class="papi-section">
                    <h3>{papi_id} Analysis</h3>
                    {coordinates_html}
                    <div class="chart-video-container">
                        <div class="chart-container">{chart_html}</div>
                        {video_html}
                    </div>
                </div>
                '''
        
        # Create summary statistics
        summary_html = self._create_summary_table(papi_data, timestamps)
        
        # Create reference points summary (including touch point)
        reference_points_html = self._create_reference_points_table(reference_points)
        
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>PAPI Measurement Report - {session_data.get('session_id', 'Unknown')}</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                .header {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .papi-section {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .chart-video-container {{ display: flex; gap: 20px; align-items: flex-start; }}
                .chart-container {{ flex: 2; min-width: 0; }}
                .video-container {{ flex: 1; min-width: 300px; }}
                .video-container h4 {{ margin-top: 0; color: #333; }}
                .video-container video {{ width: 100%; height: auto; border-radius: 8px; }}
                .video-description {{ font-size: 12px; color: #666; margin-top: 10px; }}
                .coordinates-info {{ background: #f8f9fa; padding: 15px; border-radius: 6px; margin-bottom: 20px; border-left: 4px solid #007bff; }}
                .coordinates-info h5 {{ margin: 0 0 10px 0; color: #333; font-size: 14px; }}
                .coord-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }}
                .coord-item {{ display: flex; justify-content: space-between; padding: 5px 0; }}
                .coord-label {{ font-weight: bold; color: #666; }}
                .coord-value {{ color: #333; font-family: monospace; }}
                .summary {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
                th {{ background-color: #4CAF50; color: white; }}
                .status-red {{ background-color: #ffebee; }}
                .status-white {{ background-color: #f3f3f3; }}
                .status-transition {{ background-color: #fff3e0; }}
                .status-not_visible {{ background-color: #fafafa; }}
                @media (max-width: 768px) {{
                    .chart-video-container {{ flex-direction: column; }}
                    .video-container {{ min-width: auto; }}
                }}
                .reference-points-section {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .reference-points-section h3 {{ margin-top: 0; color: #333; font-size: 18px; }}
                .reference-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                .reference-table th {{ background-color: #007bff; color: white; padding: 12px 8px; }}
                .reference-table td {{ padding: 10px 8px; border: 1px solid #ddd; }}
                .reference-table tr:nth-child(even) {{ background-color: #f8f9fa; }}
                .reference-table tr:hover {{ background-color: #e9ecef; }}
                .original-video-section {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .original-video-section h2 {{ margin-top: 0; color: #333; }}
                .original-video-container {{ text-align: center; }}
                .original-video-container video {{ border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🛩️ PAPI Light Measurement Report</h1>
                <p><strong>Session ID:</strong> {session_data.get('session_id', 'Unknown')}</p>
                <p><strong>Airport:</strong> {session_data.get('airport_icao', 'Unknown')}</p>
                <p><strong>Runway:</strong> {session_data.get('runway_code', 'Unknown')}</p>
                <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Total Frames Analyzed:</strong> {len(timestamps)}</p>
                <p><strong>Duration:</strong> {max(timestamps) - min(timestamps):.1f} seconds</p>
            </div>
            
            <div class="original-video-section">
                <h2>🎥 Enhanced Analysis Video</h2>
                <div class="original-video-container">
                    <video width="800" height="600" controls>
                        <source src="{self._get_enhanced_video_url(session_data.get('session_id'), enhanced_main_video_path)}" type="video/mp4">
                        Your browser does not support the video tag.
                    </video>
                    <p class="video-description">
                        Enhanced video with real-time drone position information (latitude, longitude, elevation), 
                        PAPI light status rectangles, angles to each PAPI light and touch point, and frame progress. 
                        The rectangles change color based on light status: Red for red lights, White for white lights, 
                        Orange for transition, Gray for not visible. Angle measurements show elevation angles from 
                        drone to each target with distance information.
                    </p>
                </div>
            </div>
            
            <div class="summary">
                <h2>📊 Summary Statistics</h2>
                {summary_html}
            </div>
            
            {reference_points_html}
            
            <div class="charts">
                <h2>📈 Detailed Analysis</h2>
                {charts_html}
            </div>
        </body>
        </html>
        """
        
        return html_template
    
    def _get_enhanced_video_url(self, session_id: str, enhanced_main_video_path: str) -> str:
        """Get URL for enhanced video or fallback to original video"""
        from app.core.config import settings
        
        if enhanced_main_video_path and os.path.exists(enhanced_main_video_path):
            # Use enhanced video endpoint (we'll create this)
            return f"{settings.API_BASE_URL}/api/v1/papi-measurements/session/{session_id}/enhanced-video"
        else:
            # Fallback to original video
            return f"{settings.API_BASE_URL}/api/v1/papi-measurements/session/{session_id}/original-video"
    
    def _create_summary_table(self, papi_data: Dict, timestamps: List[float]) -> str:
        """Create summary statistics table"""
        summary_rows = ""
        
        for papi_id in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
            if papi_id in papi_data and papi_data[papi_id]['status']:
                data = papi_data[papi_id]
                
                # Calculate statistics
                status_counts = {}
                for status in data['status']:
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                avg_intensity = sum(data['intensity']) / len(data['intensity']) if data['intensity'] else 0
                avg_angle = sum(data['angles']) / len(data['angles']) if data['angles'] else 0
                avg_distance = sum(data['ground_distance']) / len(data['ground_distance']) if data['ground_distance'] else 0
                
                summary_rows += f"""
                <tr>
                    <td><strong>{papi_id}</strong></td>
                    <td>{len(data['status'])}</td>
                    <td>{status_counts.get('red', 0)}</td>
                    <td>{status_counts.get('white', 0)}</td>
                    <td>{status_counts.get('transition', 0)}</td>
                    <td>{status_counts.get('not_visible', 0)}</td>
                    <td>{avg_intensity:.1f}</td>
                    <td>{avg_angle:.2f}°</td>
                    <td>{avg_distance:.1f}m</td>
                </tr>
                """
        
        return f"""
        <table>
            <tr>
                <th>PAPI Light</th>
                <th>Total Frames</th>
                <th>Red Frames</th>
                <th>White Frames</th>
                <th>Transition Frames</th>
                <th>Not Visible</th>
                <th>Avg Intensity</th>
                <th>Avg Angle</th>
                <th>Avg Distance</th>
            </tr>
            {summary_rows}
        </table>
        """

    def _create_reference_points_table(self, reference_points: Dict) -> str:
        """Create reference points table including PAPI lights and touch point coordinates"""
        if not reference_points:
            return '<p style="color: #666; font-style: italic;">No reference point data available.</p>'
        
        reference_rows = ""
        
        # Add PAPI light coordinates
        for papi_id in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
            if papi_id in reference_points:
                coords = reference_points[papi_id]
                lat = coords.get('latitude', 'N/A')
                lon = coords.get('longitude', 'N/A') 
                elev = coords.get('elevation', 'N/A')
                
                reference_rows += f"""
                <tr>
                    <td><strong>{papi_id}</strong></td>
                    <td>PAPI Light</td>
                    <td>{lat}°</td>
                    <td>{lon}°</td>
                    <td>{elev} m</td>
                </tr>
                """
        
        # Add touch point coordinates  
        if 'touch_point' in reference_points:
            coords = reference_points['touch_point']
            lat = coords.get('latitude', 'N/A')
            lon = coords.get('longitude', 'N/A')
            elev = coords.get('elevation', 'N/A')
            
            reference_rows += f"""
            <tr>
                <td><strong>Touch Point</strong></td>
                <td>Runway Touch Point</td>
                <td>{lat}°</td>
                <td>{lon}°</td>
                <td>{elev} m</td>
            </tr>
            """
        
        return f"""
        <div class="reference-points-section">
            <h3>🗺️ Reference Points & Coordinates</h3>
            <table class="reference-table">
                <thead>
                    <tr>
                        <th>Point Name</th>
                        <th>Type</th>
                        <th>Latitude</th>
                        <th>Longitude</th>
                        <th>Elevation</th>
                    </tr>
                </thead>
                <tbody>
                    {reference_rows}
                </tbody>
            </table>
        </div>
        """