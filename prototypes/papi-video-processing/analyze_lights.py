#!/usr/bin/env python3
"""
Airport/Runway Light Analysis Pipeline with GPS Integration
Analyzes bright spots and lights in videos, tracks them over time, extracts drone GPS position,
and generates HTML reports with RGB analysis and geospatial data.
Optimized for detecting runway lights, PAPI lights, and other airport lighting systems.
"""

import cv2
import numpy as np
import pandas as pd
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging
from dataclasses import dataclass, asdict
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.offline as pyo
from scipy.ndimage import gaussian_filter1d
from collections import defaultdict
import argparse
import base64
from io import BytesIO
from PIL import Image
import os
import subprocess
import shutil

# Import GPS extractor
try:
    from gps_extractor import GPSExtractor, GPSData, format_gps_coordinates, calculate_distance, calculate_bearing
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False
    print("Warning: GPS extractor not available. GPS features will be disabled.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class Light:
    """Represents a detected light object"""
    id: int
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
    frame_num: int
    timestamp_ms: float
    area: float
    intensity: float  # Peak intensity value
    # GPS data for this detection
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_altitude: Optional[float] = None
    drone_speed: Optional[float] = None
    drone_heading: Optional[float] = None
    
    
@dataclass
class TrackedLight:
    """Represents a light tracked over multiple frames"""
    track_id: int
    lights: List[Light]
    first_frame: int
    last_frame: int
    class_name: str
    
    def get_time_series(self):
        """Extract time series data for analysis"""
        timestamps = [l.timestamp_ms for l in self.lights]
        r_values = [l.r for l in self.lights]
        g_values = [l.g for l in self.lights]
        b_values = [l.b for l in self.lights]
        brightness = [l.brightness for l in self.lights]
        return timestamps, r_values, g_values, b_values, brightness
    

class RunwayLightDetector:
    """Pipeline step for detecting runway/airport lights in frames"""
    
    def __init__(self, brightness_threshold: int = 150, 
                 min_area: int = 5, 
                 max_area: int = 5000,
                 saturation_threshold: int = 240):
        self.brightness_threshold = brightness_threshold
        self.min_area = min_area
        self.max_area = max_area
        self.saturation_threshold = saturation_threshold
        self.current_gps = None  # Store current GPS position
        
    def preprocess_for_lights(self, frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Preprocess frame to enhance light detection"""
        # Convert to HSV for better light detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Extract value channel (brightness)
        value_channel = hsv[:, :, 2]
        
        # Apply CLAHE for contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(value_channel)
        
        # Create multiple masks for different light conditions
        # 1. Direct bright spots
        bright_mask = cv2.threshold(value_channel, self.brightness_threshold, 255, cv2.THRESH_BINARY)[1]
        
        # 2. Saturated areas (very bright lights often saturate)
        saturated_mask = cv2.threshold(value_channel, self.saturation_threshold, 255, cv2.THRESH_BINARY)[1]
        
        # 3. Enhanced bright regions
        enhanced_mask = cv2.threshold(enhanced, 200, 255, cv2.THRESH_BINARY)[1]
        
        # Combine masks
        combined_mask = cv2.bitwise_or(bright_mask, saturated_mask)
        combined_mask = cv2.bitwise_or(combined_mask, enhanced_mask)
        
        # Morphological operations to clean up
        kernel = np.ones((3,3), np.uint8)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
        combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
        
        return combined_mask, value_channel
        
    def detect_lights(self, frame: np.ndarray, frame_num: int, timestamp_ms: float) -> List[Light]:
        """Detect all bright spots and lights in frame"""
        lights = []
        light_id = 0
        
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
                
                light = Light(
                    id=light_id,
                    x=cx,
                    y=cy,
                    width=w,
                    height=h,
                    confidence=min(1.0, intensity/255.0),  # Confidence based on intensity
                    class_name=class_name,
                    brightness=brightness,
                    r=int(r),
                    g=int(g),
                    b=int(b),
                    frame_num=frame_num,
                    timestamp_ms=timestamp_ms,
                    area=area,
                    intensity=intensity,
                    # Add GPS data if available
                    gps_latitude=self.current_gps.latitude if self.current_gps else None,
                    gps_longitude=self.current_gps.longitude if self.current_gps else None,
                    gps_altitude=self.current_gps.altitude if self.current_gps else None,
                    drone_speed=self.current_gps.speed if self.current_gps else None,
                    drone_heading=self.current_gps.heading if self.current_gps else None
                )
                lights.append(light)
                light_id += 1
        
        return lights
    
    def classify_light(self, r: float, g: float, b: float, area: float, intensity: float) -> str:
        """Classify light based on color and characteristics"""
        # Normalize RGB values
        total = r + g + b
        if total == 0:
            return "unknown_light"
        
        r_norm = r / total
        g_norm = g / total
        b_norm = b / total
        
        # PAPI lights are usually white/red
        if r_norm > 0.4 and intensity > 200:
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
        
        # High intensity lights
        if intensity > 240:
            return "high_intensity_light"
        
        return "runway_light"
    
    def process(self, frame: np.ndarray, frame_num: int, timestamp_ms: float, gps_data: Optional['GPSData'] = None) -> List[Light]:
        """Main processing function"""
        self.current_gps = gps_data  # Update current GPS position
        return self.detect_lights(frame, frame_num, timestamp_ms)


@dataclass
class MotionConsistencyResult:
    """Result of motion consistency validation"""
    total_lights: int
    outliers_detected: int
    outliers_corrected: int
    median_motion: Tuple[float, float]
    max_deviation_percent: float
    corrected_light_ids: List[int]


class MotionConsistencyValidator:
    """
    Validates and corrects motion consistency across all detected lights.

    Ensures all lights move uniformly between frames (within 1% variance),
    as they should all be affected by the same camera/drone movement.
    Corrects lights that move faster or in different direction than average.
    """

    def __init__(self, variance_threshold: float = 0.01, min_lights_required: int = 3):
        """
        Args:
            variance_threshold: Maximum allowed deviation from median motion (default 1%)
            min_lights_required: Minimum number of lights needed for validation
        """
        self.variance_threshold = variance_threshold
        self.min_lights_required = min_lights_required
        self.validation_stats = {
            'total_validations': 0,
            'total_outliers_corrected': 0,
            'max_deviation_seen': 0.0
        }

    def validate_and_correct_motion(
        self,
        current_lights: List[Light],
        prev_lights: List[Light]
    ) -> MotionConsistencyResult:
        """
        Validate motion consistency across all lights and correct outliers.

        All lights should move similarly between frames since they're all affected
        by the same drone/camera movement. Lights with significantly different
        movement are likely misdetections and should be corrected.

        Args:
            current_lights: Detected lights in current frame
            prev_lights: Detected lights in previous frame

        Returns:
            MotionConsistencyResult with validation statistics
        """
        # Early return if insufficient lights
        if len(current_lights) < self.min_lights_required or len(prev_lights) < self.min_lights_required:
            return MotionConsistencyResult(
                total_lights=len(current_lights),
                outliers_detected=0,
                outliers_corrected=0,
                median_motion=(0.0, 0.0),
                max_deviation_percent=0.0,
                corrected_light_ids=[]
            )

        # Step 1: Match current lights to previous lights (nearest neighbor)
        motion_vectors = []
        light_pairs = []  # (current_light, prev_light, motion_vector)

        for curr_light in current_lights:
            best_dist = float('inf')
            best_prev = None

            for prev_light in prev_lights:
                # Only match lights of similar characteristics
                if abs(curr_light.brightness - prev_light.brightness) > 50:
                    continue
                if curr_light.class_name != prev_light.class_name:
                    continue

                dist = np.sqrt((curr_light.x - prev_light.x)**2 + (curr_light.y - prev_light.y)**2)
                if dist < 150 and dist < best_dist:  # Reasonable movement threshold
                    best_dist = dist
                    best_prev = prev_light

            if best_prev:
                dx = curr_light.x - best_prev.x
                dy = curr_light.y - best_prev.y
                motion_vectors.append((dx, dy))
                light_pairs.append((curr_light, best_prev, (dx, dy)))

        # Early return if insufficient matches
        if len(motion_vectors) < self.min_lights_required:
            return MotionConsistencyResult(
                total_lights=len(current_lights),
                outliers_detected=0,
                outliers_corrected=0,
                median_motion=(0.0, 0.0),
                max_deviation_percent=0.0,
                corrected_light_ids=[]
            )

        # Step 2: Calculate median motion (robust against outliers)
        motion_vectors_array = np.array(motion_vectors)
        median_dx = np.median(motion_vectors_array[:, 0])
        median_dy = np.median(motion_vectors_array[:, 1])
        median_motion = (median_dx, median_dy)
        median_magnitude = np.sqrt(median_dx**2 + median_dy**2)

        # Avoid division by zero for stationary camera
        if median_magnitude < 0.5:  # Nearly stationary
            return MotionConsistencyResult(
                total_lights=len(current_lights),
                outliers_detected=0,
                outliers_corrected=0,
                median_motion=median_motion,
                max_deviation_percent=0.0,
                corrected_light_ids=[]
            )

        # Step 3: Identify outliers (lights with >3% deviation from median)
        outliers = []
        max_deviation_percent = 0.0

        for curr_light, prev_light, (dx, dy) in light_pairs:
            # Calculate deviation from median motion
            deviation_x = abs(dx - median_dx)
            deviation_y = abs(dy - median_dy)
            deviation_magnitude = np.sqrt(deviation_x**2 + deviation_y**2)

            # Calculate percentage deviation
            deviation_percent = deviation_magnitude / median_magnitude
            max_deviation_percent = max(max_deviation_percent, deviation_percent)

            # Mark as outlier if deviation exceeds threshold
            if deviation_percent > self.variance_threshold:
                outliers.append((curr_light, prev_light, deviation_percent))

        # Step 4: Correct outlier positions
        corrected_light_ids = []
        outliers_corrected = 0

        # Don't correct if too many outliers (likely scene change or major motion)
        if len(outliers) <= len(light_pairs) * 0.5:  # Max 50% outliers
            for curr_light, prev_light, deviation_percent in outliers:
                # Normalize position using median motion
                corrected_x = prev_light.x + median_dx
                corrected_y = prev_light.y + median_dy

                # Update light position
                curr_light.x = corrected_x
                curr_light.y = corrected_y

                corrected_light_ids.append(curr_light.id)
                outliers_corrected += 1

        # Update statistics
        self.validation_stats['total_validations'] += 1
        self.validation_stats['total_outliers_corrected'] += outliers_corrected
        self.validation_stats['max_deviation_seen'] = max(
            self.validation_stats['max_deviation_seen'],
            max_deviation_percent
        )

        return MotionConsistencyResult(
            total_lights=len(current_lights),
            outliers_detected=len(outliers),
            outliers_corrected=outliers_corrected,
            median_motion=median_motion,
            max_deviation_percent=max_deviation_percent,
            corrected_light_ids=corrected_light_ids
        )

    def get_statistics(self) -> Dict:
        """Get overall validation statistics"""
        return self.validation_stats.copy()


class LightTracker:
    """Pipeline step for tracking lights across frames with motion prediction"""

    def __init__(self, max_distance=50, max_frame_gap=20):
        self.max_distance = max_distance
        self.max_frame_gap = max_frame_gap
        self.tracks: Dict[int, TrackedLight] = {}
        self.next_track_id = 0
        self.global_motion = None  # Store estimated global camera motion
        self.prev_lights = []  # Store previous frame lights for motion estimation
        self.motion_validator = MotionConsistencyValidator(variance_threshold=0.01)
        
    def estimate_global_motion(self, current_lights: List[Light], prev_lights: List[Light]) -> Tuple[float, float]:
        """Estimate global camera motion between frames"""
        if len(current_lights) < 3 or len(prev_lights) < 3:
            return 0.0, 0.0
        
        # Find correspondences between frames using nearest neighbor
        motions = []
        for curr_light in current_lights:
            best_dist = float('inf')
            best_prev = None
            
            for prev_light in prev_lights:
                # Only match lights of similar brightness and type
                if abs(curr_light.brightness - prev_light.brightness) > 50:
                    continue
                if curr_light.class_name != prev_light.class_name:
                    continue
                    
                dist = np.sqrt((curr_light.x - prev_light.x)**2 + (curr_light.y - prev_light.y)**2)
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
    
    def predict_position(self, track: TrackedLight, frame_gap: int) -> Tuple[float, float]:
        """Predict where a light should be based on its motion history"""
        if len(track.lights) < 2:
            # No motion history, use global motion if available
            if self.global_motion:
                last_light = track.lights[-1]
                pred_x = last_light.x + self.global_motion[0] * frame_gap
                pred_y = last_light.y + self.global_motion[1] * frame_gap
                return pred_x, pred_y
            return track.lights[-1].x, track.lights[-1].y
        
        # Calculate average velocity from recent positions
        recent_lights = track.lights[-min(5, len(track.lights)):]  # Use up to 5 recent positions
        
        if len(recent_lights) >= 2:
            # Calculate velocity from first to last position in recent history
            dt = recent_lights[-1].frame_num - recent_lights[0].frame_num
            if dt > 0:
                vx = (recent_lights[-1].x - recent_lights[0].x) / dt
                vy = (recent_lights[-1].y - recent_lights[0].y) / dt
                
                # Predict position
                last_light = track.lights[-1]
                pred_x = last_light.x + vx * frame_gap
                pred_y = last_light.y + vy * frame_gap
                return pred_x, pred_y
        
        return track.lights[-1].x, track.lights[-1].y

    def process(self, lights: List[Light]) -> None:
        """Track lights across frames with motion prediction and consistency validation"""
        if not lights:
            return

        current_frame = lights[0].frame_num if lights else 0

        # Validate and correct motion consistency between frames
        if self.prev_lights and len(self.prev_lights) >= 3 and len(lights) >= 3:
            # Apply motion consistency validation
            validation_result = self.motion_validator.validate_and_correct_motion(
                lights, self.prev_lights
            )

            # Log validation results if outliers were detected
            if validation_result.outliers_detected > 0:
                print(f"Frame {current_frame}: Motion consistency validation - "
                      f"{validation_result.outliers_detected} outliers detected, "
                      f"{validation_result.outliers_corrected} corrected "
                      f"(max deviation: {validation_result.max_deviation_percent:.1%})")

        # Estimate global motion if we have previous lights
        if self.prev_lights and len(self.prev_lights) >= 3 and len(lights) >= 3:
            self.global_motion = self.estimate_global_motion(lights, self.prev_lights)
        
        # Match lights to existing tracks using prediction
        matched_tracks = set()
        unmatched_lights = list(lights)
        
        # Sort tracks by track length (prioritize longer tracks)
        sorted_tracks = sorted(self.tracks.items(), key=lambda x: len(x[1].lights), reverse=True)
        
        for track_id, track in sorted_tracks:
            if track_id in matched_tracks:
                continue
                
            last_light = track.lights[-1]
            frame_gap = current_frame - last_light.frame_num
            
            # Skip if track is too old
            if frame_gap > self.max_frame_gap:
                continue
            
            # Predict where this light should be
            pred_x, pred_y = self.predict_position(track, frame_gap)
            
            # Find best matching light
            best_match = None
            best_score = float('inf')
            best_light_idx = -1
            
            for idx, light in enumerate(unmatched_lights):
                # Distance to predicted position
                pred_distance = np.sqrt((light.x - pred_x)**2 + (light.y - pred_y)**2)
                
                # Distance to last known position
                last_distance = np.sqrt((light.x - last_light.x)**2 + (light.y - last_light.y)**2)
                
                # Combined score (weighted towards prediction)
                score = 0.7 * pred_distance + 0.3 * last_distance
                
                # Penalty for different light types
                if light.class_name != last_light.class_name:
                    score += 20
                
                # Penalty for significant brightness change
                brightness_diff = abs(light.brightness - last_light.brightness)
                score += brightness_diff * 0.05
                
                # Penalty for unreasonable movement (outlier detection)
                if frame_gap > 0:
                    movement_per_frame = last_distance / frame_gap
                    if movement_per_frame > 30:  # More than 30 pixels per frame is suspicious
                        score += movement_per_frame * 0.5
                
                if score < self.max_distance and score < best_score:
                    best_score = score
                    best_match = light
                    best_light_idx = idx
            
            if best_match:
                track.lights.append(best_match)
                track.last_frame = best_match.frame_num
                matched_tracks.add(track_id)
                if best_light_idx >= 0:
                    unmatched_lights.pop(best_light_idx)
        
        # Create new tracks for unmatched lights
        for light in unmatched_lights:
            track = TrackedLight(
                track_id=self.next_track_id,
                lights=[light],
                first_frame=light.frame_num,
                last_frame=light.frame_num,
                class_name=light.class_name
            )
            self.tracks[self.next_track_id] = track
            self.next_track_id += 1
        
        # Store current lights for next iteration
        self.prev_lights = lights


class RGBAnalyzer:
    """Pipeline step for analyzing RGB values and derivatives"""
    
    @staticmethod
    def compute_derivatives(values: List[float], timestamps: List[float]) -> Tuple[List[float], List[float]]:
        """Compute first and second derivatives"""
        if len(values) < 3:
            return [], []
        
        # Convert to numpy arrays
        values = np.array(values)
        timestamps = np.array(timestamps)
        
        # Smooth the signal slightly to reduce noise
        smoothed = gaussian_filter1d(values, sigma=1)
        
        # Compute first derivative
        dt = np.diff(timestamps)
        dt[dt == 0] = 1  # Avoid division by zero
        first_deriv = np.diff(smoothed) / dt
        
        # Compute second derivative
        second_deriv = np.diff(first_deriv) / dt[1:]
        
        # Pad to match original length
        first_deriv = np.concatenate([[0], first_deriv])
        second_deriv = np.concatenate([[0, 0], second_deriv])
        
        return first_deriv.tolist(), second_deriv.tolist()
    
    @staticmethod
    def detect_color_changes(r_values: List[float], g_values: List[float], b_values: List[float], 
                            timestamps: List[float], threshold: float = 20.0) -> List[Dict]:
        """Detect significant color changes in RGB values
        
        Args:
            r_values: Red channel values
            g_values: Green channel values  
            b_values: Blue channel values
            timestamps: Timestamps in milliseconds
            threshold: Minimum change in derivative to consider significant
            
        Returns:
            List of color change events with timestamp and magnitude
        """
        if len(r_values) < 3:
            return []
        
        # Compute first derivatives
        r_deriv1, _ = RGBAnalyzer.compute_derivatives(r_values, timestamps)
        g_deriv1, _ = RGBAnalyzer.compute_derivatives(g_values, timestamps)
        b_deriv1, _ = RGBAnalyzer.compute_derivatives(b_values, timestamps)
        
        color_changes = []
        
        # Detect significant changes
        for i in range(1, len(timestamps)):
            # Calculate magnitude of color change (Euclidean distance in RGB derivative space)
            change_magnitude = np.sqrt(r_deriv1[i]**2 + g_deriv1[i]**2 + b_deriv1[i]**2)
            
            # Check if change is significant
            if change_magnitude > threshold:
                # Determine the dominant color change
                dominant_channel = 'mixed'
                if abs(r_deriv1[i]) > abs(g_deriv1[i]) and abs(r_deriv1[i]) > abs(b_deriv1[i]):
                    dominant_channel = 'red'
                elif abs(g_deriv1[i]) > abs(r_deriv1[i]) and abs(g_deriv1[i]) > abs(b_deriv1[i]):
                    dominant_channel = 'green'
                elif abs(b_deriv1[i]) > abs(r_deriv1[i]) and abs(b_deriv1[i]) > abs(g_deriv1[i]):
                    dominant_channel = 'blue'
                
                # Calculate color before and after
                color_before = (r_values[i-1], g_values[i-1], b_values[i-1])
                color_after = (r_values[i], g_values[i], b_values[i])
                
                color_changes.append({
                    'timestamp_ms': timestamps[i],
                    'frame_index': i,
                    'magnitude': change_magnitude,
                    'r_deriv': r_deriv1[i],
                    'g_deriv': g_deriv1[i],
                    'b_deriv': b_deriv1[i],
                    'dominant_channel': dominant_channel,
                    'color_before': color_before,
                    'color_after': color_after
                })
        
        # Sort by magnitude and return most significant changes
        color_changes.sort(key=lambda x: x['magnitude'], reverse=True)
        return color_changes[:10]  # Return top 10 most significant changes


class LightVideoExtractor:
    """Extract individual video clips for each tracked light"""
    
    @staticmethod
    def extract_light_videos(video_path: Path, tracks: Dict[int, TrackedLight], output_dir: Path, 
                            video_size: int = 128, max_videos: int = 50) -> Dict[int, Path]:
        """Extract small video clips centered on each tracked light
        
        Args:
            video_path: Path to source video
            tracks: Dictionary of tracked lights
            output_dir: Directory to save video clips
            video_size: Size of the output video (square)
            max_videos: Maximum number of videos to generate
            
        Returns:
            Dictionary mapping track_id to video clip path
        """
        # Create subdirectory for light videos
        videos_dir = output_dir / "light_videos"
        videos_dir.mkdir(parents=True, exist_ok=True)
        
        # Filter tracks with sufficient frames
        valid_tracks = {
            tid: track for tid, track in tracks.items()
            if len(track.lights) >= 10  # Need at least 10 frames for a meaningful video
        }
        
        # Limit number of videos
        track_ids = list(valid_tracks.keys())[:max_videos]
        
        if not track_ids:
            logger.info("No valid tracks for video extraction")
            return {}
        
        logger.info(f"Extracting {len(track_ids)} light videos...")
        
        # Open source video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error(f"Failed to open video: {video_path}")
            return {}
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30
            
        # Process each track
        video_paths = {}
        
        for track_id in track_ids:
            track = valid_tracks[track_id]
            
            # Get frame range for this track
            frame_numbers = [light.frame_num for light in track.lights]
            min_frame = min(frame_numbers)
            max_frame = max(frame_numbers)
            
            # Create video writer for this light with unique filename
            source_name = video_path.stem  # Get source video name without extension
            video_name = f"{source_name}_light_{track_id}_{track.class_name}.mp4"
            video_path_out = videos_dir / video_name
            
            # Try different codec for browser compatibility
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            temp_path = str(video_path_out).replace('.mp4', '_temp.mp4')
            out = cv2.VideoWriter(temp_path, fourcc, fps, (video_size, video_size))
            
            # Create frame lookup for this track
            frame_to_light = {light.frame_num: light for light in track.lights}
            
            # Process frames for this track
            cap.set(cv2.CAP_PROP_POS_FRAMES, min_frame)
            
            for frame_idx in range(min_frame, max_frame + 1):
                ret, frame = cap.read()
                if not ret:
                    break
                    
                # Get light position for this frame (interpolate if needed)
                if frame_idx in frame_to_light:
                    light = frame_to_light[frame_idx]
                    cx, cy = int(light.x), int(light.y)
                else:
                    # Interpolate position from nearest frames
                    prev_frame = max([f for f in frame_to_light.keys() if f < frame_idx], default=None)
                    next_frame = min([f for f in frame_to_light.keys() if f > frame_idx], default=None)
                    
                    if prev_frame and next_frame:
                        prev_light = frame_to_light[prev_frame]
                        next_light = frame_to_light[next_frame]
                        
                        # Linear interpolation
                        alpha = (frame_idx - prev_frame) / (next_frame - prev_frame)
                        cx = int(prev_light.x + alpha * (next_light.x - prev_light.x))
                        cy = int(prev_light.y + alpha * (next_light.y - prev_light.y))
                    elif prev_frame:
                        light = frame_to_light[prev_frame]
                        cx, cy = int(light.x), int(light.y)
                    elif next_frame:
                        light = frame_to_light[next_frame]
                        cx, cy = int(light.x), int(light.y)
                    else:
                        continue
                
                # Extract region around the light
                half_size = video_size // 2
                h, w = frame.shape[:2]
                
                # Calculate crop boundaries with bounds checking
                x1 = max(0, cx - half_size)
                x2 = min(w, cx + half_size)
                y1 = max(0, cy - half_size)
                y2 = min(h, cy + half_size)
                
                # Extract the region
                crop = frame[y1:y2, x1:x2]
                
                # Pad if necessary to maintain video_size
                if crop.shape[0] < video_size or crop.shape[1] < video_size:
                    # Create black background
                    padded = np.zeros((video_size, video_size, 3), dtype=np.uint8)
                    
                    # Calculate placement
                    y_offset = (video_size - crop.shape[0]) // 2
                    x_offset = (video_size - crop.shape[1]) // 2
                    
                    # Place crop in center
                    padded[y_offset:y_offset+crop.shape[0], x_offset:x_offset+crop.shape[1]] = crop
                    crop = padded
                
                # Add track ID text
                text = f"#{track_id}"
                cv2.putText(crop, text, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Write frame
                out.write(crop)
            
            out.release()
            
            # Convert video to ensure browser compatibility using ffmpeg
            try:
                # Convert using ffmpeg for proper browser playback
                final_path = str(video_path_out)
                cmd = [
                    'ffmpeg', '-y', '-i', temp_path,
                    '-c:v', 'libx264',  # Use H.264 codec
                    '-pix_fmt', 'yuv420p',  # Pixel format for compatibility
                    '-movflags', '+faststart',  # Enable fast start for web playback
                    final_path
                ]
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                # Remove temp file
                os.remove(temp_path)
                logger.info(f"Created and converted video for track #{track_id}: {video_name}")
            except subprocess.CalledProcessError as e:
                # If ffmpeg fails, just rename the temp file
                shutil.move(temp_path, str(video_path_out))
                logger.warning(f"ffmpeg conversion failed, using original format for track #{track_id}")
            except FileNotFoundError:
                # ffmpeg not installed, just rename
                shutil.move(temp_path, str(video_path_out))
                logger.warning("ffmpeg not found, using original video format")
                
            video_paths[track_id] = video_path_out
        
        cap.release()
        return video_paths


class SnapshotGenerator:
    """Generate annotated snapshots of detected lights"""
    
    @staticmethod
    def create_annotated_frame(frame: np.ndarray, lights: List[Light], tracks: Dict[int, TrackedLight]) -> np.ndarray:
        """Create an annotated frame with light IDs and bounding boxes"""
        annotated = frame.copy()
        
        # Create a mapping from lights to track IDs
        light_to_track = {}
        for track_id, track in tracks.items():
            for light in track.lights:
                light_to_track[id(light)] = track_id
        
        # Define colors for different light types
        colors = {
            'red_light': (0, 0, 255),
            'green_light': (0, 255, 0),
            'blue_light': (255, 0, 0),
            'white_light': (255, 255, 255),
            'yellow_light': (0, 255, 255),
            'high_intensity_light': (255, 0, 255),
            'runway_light': (128, 255, 128),
            'unknown_light': (128, 128, 128)
        }
        
        for light in lights:
            track_id = light_to_track.get(id(light), -1)
            if track_id == -1:
                continue
                
            color = colors.get(light.class_name, (255, 255, 255))
            
            # Draw bounding box
            x1 = int(light.x - light.width/2)
            y1 = int(light.y - light.height/2)
            x2 = int(light.x + light.width/2)
            y2 = int(light.y + light.height/2)
            
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Draw track ID with larger font
            label = f"#{track_id}"
            font_scale = 2.0  # Increased from 0.5 to 2.0 (4x)
            font_thickness = 3  # Increased from 1 to 3 for better visibility
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)[0]
            
            # Background for text (adjusted for larger text)
            padding = 8  # Increased padding for larger text
            cv2.rectangle(annotated, 
                         (x1, y1 - label_size[1] - padding),
                         (x1 + label_size[0] + padding, y1),
                         color, -1)
            
            # Draw text with larger font
            cv2.putText(annotated, label,
                       (x1 + 4, y1 - 4),
                       cv2.FONT_HERSHEY_SIMPLEX,
                       font_scale, (0, 0, 0), font_thickness)
            
            # Draw center point
            cv2.circle(annotated, (int(light.x), int(light.y)), 3, color, -1)
        
        return annotated
    
    @staticmethod
    def frame_to_base64(frame: np.ndarray) -> str:
        """Convert frame to base64 string for HTML embedding"""
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        return f"data:image/jpeg;base64,{img_base64}"


class ReportGenerator:
    """Pipeline step for generating HTML reports"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_generator = SnapshotGenerator()
        
    def generate(self, video_path: Path, tracks: Dict[int, TrackedLight], 
                 snapshot_frames: Dict[str, Tuple[np.ndarray, List[Light]]],
                 gps_data: List['GPSData'] = None) -> Path:
        """Generate HTML report for a video with snapshots and GPS data"""
        report_name = f"{video_path.stem}_light_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        report_path = self.output_dir / report_name
        
        # Get relative path to video from report directory
        video_relative_path = os.path.relpath(video_path, self.output_dir)
        
        # Extract individual light videos
        video_extractor = LightVideoExtractor()
        light_videos = video_extractor.extract_light_videos(video_path, tracks, self.output_dir)
        
        # Filter tracks with sufficient data
        valid_tracks = {
            tid: track for tid, track in tracks.items()
            if len(track.lights) >= 5  # Need at least 5 frames
        }
        
        if not valid_tracks:
            logger.warning(f"No valid tracks found for {video_path.name}")
            self._generate_empty_report(report_path, video_path.name)
            return report_path
        
        # Remove limit - show all valid tracks
        logger.info(f"Processing all {len(valid_tracks)} valid tracks")
        
        # Generate annotated snapshots
        snapshot_images = {}
        for position, (frame, lights) in snapshot_frames.items():
            annotated = self.snapshot_generator.create_annotated_frame(frame, lights, valid_tracks)
            snapshot_images[position] = self.snapshot_generator.frame_to_base64(annotated)
        
        # Prepare data for individual charts generation - show all tracks
        chart_tracks = valid_tracks  # Show all tracks
        analyzer = RGBAnalyzer()
        
        # Generate individual chart data for each track
        chart_data = []
        for track_id, track in chart_tracks.items():
            timestamps, r_values, g_values, b_values, brightness = track.get_time_series()
            
            # Convert timestamps to seconds format for better display
            time_formatted = []
            for ts in timestamps:
                total_seconds = ts / 1000.0
                time_formatted.append(f"{total_seconds:.1f}s")
            
            # Derivatives removed - no longer computing color change rates
            
            # Detect significant color changes
            color_changes = analyzer.detect_color_changes(r_values, g_values, b_values, timestamps)
            
            # Add GPS coordinates to color changes
            for change in color_changes:
                frame_idx = change['frame_index']
                if frame_idx < len(track.lights):
                    light = track.lights[frame_idx]
                    change['gps_latitude'] = light.gps_latitude
                    change['gps_longitude'] = light.gps_longitude
                    change['gps_altitude'] = light.gps_altitude
            
            # Position data
            x_positions = [light.x for light in track.lights]
            y_positions = [light.y for light in track.lights]
            
            # GPS position data (if available)
            gps_lats = [light.gps_latitude for light in track.lights if light.gps_latitude is not None]
            gps_lons = [light.gps_longitude for light in track.lights if light.gps_longitude is not None]
            gps_alts = [light.gps_altitude for light in track.lights if light.gps_altitude is not None]
            
            # Get altitude data for all frames (use None if no GPS)
            altitudes_for_chart = []
            has_altitude = False
            for light in track.lights:
                if light.gps_altitude is not None:
                    altitudes_for_chart.append(light.gps_altitude)
                    has_altitude = True
                else:
                    altitudes_for_chart.append(None)
            
            # Calculate statistics
            duration = (track.lights[-1].timestamp_ms - track.lights[0].timestamp_ms) / 1000
            avg_brightness = np.mean([l.brightness for l in track.lights])
            avg_r = np.mean(r_values)
            avg_g = np.mean(g_values)
            avg_b = np.mean(b_values)
            
            chart_data.append({
                'track_id': track_id,
                'track': track,
                'time_formatted': time_formatted,
                'r_values': r_values,
                'g_values': g_values,
                'b_values': b_values,
                'color_changes': color_changes,
                'x_positions': x_positions,
                'y_positions': y_positions,
                'gps_lats': gps_lats,
                'gps_lons': gps_lons,
                'gps_alts': gps_alts,
                'altitudes_for_chart': altitudes_for_chart,
                'duration': duration,
                'avg_brightness': avg_brightness,
                'avg_r': avg_r,
                'avg_g': avg_g,
                'avg_b': avg_b,
            })
        
        # Count lights by type
        light_type_counts = defaultdict(int)
        for track in valid_tracks.values():
            light_type_counts[track.class_name] += 1
        
        # Prepare GPS data for visualization
        gps_info_html = ""
        gps_map_html = ""
        
        if gps_data and GPS_AVAILABLE:
            # Create GPS summary
            first_gps = gps_data[0]
            last_gps = gps_data[-1]
            
            avg_altitude = np.mean([p.altitude for p in gps_data])
            
            # Calculate total distance traveled
            total_distance = 0
            if len(gps_data) > 1:
                for i in range(1, len(gps_data)):
                    total_distance += calculate_distance(gps_data[i-1], gps_data[i])
            
            gps_info_html = f"""
            <div class="info">
                <h2>🛰️ GPS/Drone Position Data</h2>
                <p><strong>GPS Data Points:</strong> {len(gps_data)}</p>
                <p><strong>Initial Position:</strong> {format_gps_coordinates(first_gps.latitude, first_gps.longitude)}</p>
                <p><strong>Final Position:</strong> {format_gps_coordinates(last_gps.latitude, last_gps.longitude)}</p>
                <p><strong>Average Altitude:</strong> {avg_altitude:.1f} meters</p>
                <p><strong>Total Distance Traveled:</strong> {total_distance:.1f} meters</p>
            </div>
            """
            
            # Create GPS trajectory map
            if len(gps_data) > 0:
                lats = [p.latitude for p in gps_data]
                lons = [p.longitude for p in gps_data]
                alts = [p.altitude for p in gps_data]
                times = [p.timestamp_ms/1000 for p in gps_data]
                
                # Create 3D trajectory plot with proper layering
                trajectory_fig = go.Figure()
                
                # First add start/end markers (bottom layer)
                trajectory_fig.add_trace(go.Scatter3d(
                    x=[lons[0]], y=[lats[0]], z=[alts[0]],
                    mode='markers+text',
                    marker=dict(size=12, color='green', symbol='circle'),
                    text=['START'],
                    textposition='top center',
                    name='Start Position',
                    showlegend=True
                ))
                
                trajectory_fig.add_trace(go.Scatter3d(
                    x=[lons[-1]], y=[lats[-1]], z=[alts[-1]],
                    mode='markers+text',
                    marker=dict(size=12, color='red', symbol='square'),
                    text=['END'],
                    textposition='top center',
                    name='End Position',
                    showlegend=True
                ))
                
                # Then add flight path (top layer) with better visibility
                trajectory_fig.add_trace(go.Scatter3d(
                    x=lons,
                    y=lats,
                    z=alts,
                    mode='lines+markers',
                    line=dict(
                        color=times, 
                        colorscale='Viridis', 
                        width=6,
                        showscale=True,
                        colorbar=dict(title="Time (s)")
                    ),
                    marker=dict(
                        size=4, 
                        color=times, 
                        colorscale='Viridis',
                        opacity=0.8
                    ),
                    text=[f"Time: {t:.1f}s<br>Lat: {lat:.6f}<br>Lon: {lon:.6f}<br>Alt: {a:.1f}m" 
                          for t, lat, lon, a in zip(times, lats, lons, alts)],
                    hoverinfo='text',
                    name='Flight Path',
                    showlegend=True
                ))
                
                # Update layout for better 3D visualization
                trajectory_fig.update_layout(
                    dragmode='turntable',  # Set default 3D interaction mode
                    title={
                        'text': 'Drone Flight Trajectory (3D)',
                        'font': {'size': 20}
                    },
                    scene=dict(
                        xaxis=dict(
                            title='Longitude',
                            showgrid=True,
                            gridwidth=2,
                            gridcolor='lightgray'
                        ),
                        yaxis=dict(
                            title='Latitude', 
                            showgrid=True,
                            gridwidth=2,
                            gridcolor='lightgray'
                        ),
                        zaxis=dict(
                            title='Altitude (m)',
                            showgrid=True,
                            gridwidth=2,
                            gridcolor='lightgray'
                        ),
                        camera=dict(
                            eye=dict(x=1.5, y=1.5, z=1.2),
                            center=dict(x=0, y=0, z=0)
                        ),
                        aspectmode='manual',
                        aspectratio=dict(x=1, y=1, z=0.5)
                    ),
                    height=700,
                    margin=dict(l=0, r=0, t=40, b=0),
                    showlegend=True,
                    legend=dict(
                        x=0.02,
                        y=0.98,
                        bgcolor='rgba(255, 255, 255, 0.8)',
                        bordercolor='black',
                        borderwidth=1
                    )
                )
                
                gps_map_html = f"""
                <div class="info">
                    <h2>🗺️ Flight Path Visualization</h2>
                    {pyo.plot(trajectory_fig, output_type='div', include_plotlyjs=False)}
                </div>
                """
        
        # Generate HTML
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Airport Light Analysis with GPS - {video_path.name}</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                h1 {{ color: #333; }}
                .info {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .stats {{ margin: 10px 0; }}
                table {{ border-collapse: collapse; width: 100%; margin: 10px 0; background: white; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                .snapshots {{ display: flex; justify-content: space-around; flex-wrap: wrap; margin: 20px 0; }}
                .snapshot {{ text-align: center; margin: 10px; }}
                .snapshot img {{ max-width: 100%; height: auto; border: 2px solid #ddd; border-radius: 4px; }}
                .snapshot h3 {{ color: #333; margin: 10px 0; }}
                .light-legend {{ background: white; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                .light-type {{ display: inline-block; margin: 5px 10px; }}
                .color-box {{ display: inline-block; width: 20px; height: 20px; margin-right: 5px; vertical-align: middle; border: 1px solid #000; }}
                .track-section {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .track-header {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4CAF50; }}
                .track-stats {{ display: flex; flex-wrap: wrap; gap: 15px; margin-bottom: 15px; }}
                .stat-item {{ background: #e9ecef; padding: 8px 12px; border-radius: 4px; }}
                .charts-row {{ display: flex; flex-wrap: wrap; gap: 20px; justify-content: space-around; }}
                .chart-container {{ flex: 1; min-width: 45%; }}
                .chart-container > div {{ width: 100% !important; }}
                .plotly-graph-div {{ width: 100% !important; }}
            </style>
        </head>
        <body>
            <h1>🚁 Airport/Runway Light Analysis Report with GPS Tracking</h1>
            
            <div class="info">
                <h2>📊 Video Information</h2>
                <p><strong>File:</strong> {video_path.name}</p>
                <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Total Tracked Lights:</strong> {len(valid_tracks)}</p>
                <p><strong>Detection Method:</strong> Enhanced Brightness Detection for Airport Lights</p>
                <p><strong>GPS Data Available:</strong> {'Yes' if gps_data else 'No'}</p>
            </div>
            
            {gps_info_html}
            {gps_map_html}
            
            <div class="light-legend">
                <h2>🎨 Light Type Legend</h2>
                <div class="light-type"><span class="color-box" style="background-color: red;"></span> Red Light (PAPI/Approach)</div>
                <div class="light-type"><span class="color-box" style="background-color: white;"></span> White Light (Runway/PAPI)</div>
                <div class="light-type"><span class="color-box" style="background-color: green;"></span> Green Light (Taxiway)</div>
                <div class="light-type"><span class="color-box" style="background-color: blue;"></span> Blue Light (Taxiway Edge)</div>
                <div class="light-type"><span class="color-box" style="background-color: yellow;"></span> Yellow Light (Warning)</div>
                <div class="light-type"><span class="color-box" style="background-color: magenta;"></span> High Intensity Light</div>
            </div>
            
            <div class="info">
                <h2>🎥 Source Video</h2>
                <video width="100%" controls>
                    <source src="{video_relative_path}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
            </div>
            
            <div class="snapshots">
        """
        
        # Add snapshot images
        for position in ['start', 'middle', 'end']:
            if position in snapshot_images:
                html_content += f"""
                <div class="snapshot">
                    <h3>{position.capitalize()} Frame</h3>
                    <img src="{snapshot_images[position]}" alt="{position} frame">
                </div>
                """
        
        html_content += """
            </div>
            """
        
        # Add light video gallery if videos were extracted
        if light_videos:
            html_content += """
            <div class="info">
                <h2>📹 Individual Light Videos</h2>
                <p>Small video clips centered on each tracked light. Each video shows the light in the center with a green crosshair.</p>
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px; margin-top: 20px;">
            """
            
            for track_id, video_path in sorted(light_videos.items())[:30]:  # Show up to 30 videos
                if track_id in valid_tracks:
                    track = valid_tracks[track_id]
                    video_relative = os.path.relpath(video_path, self.output_dir)
                    html_content += f"""
                    <div style="text-align: center; background: white; padding: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <video width="128" height="128" controls loop style="border-radius: 4px;">
                            <source src="{video_relative}" type="video/mp4">
                        </video>
                        <p style="margin: 5px 0 0 0; font-size: 12px;">
                            <strong>Track #{track_id}</strong><br>
                            <span style="color: #666;">{track.class_name.replace('_', ' ').title()}</span>
                        </p>
                    </div>
                    """
            
            html_content += """
                </div>
            </div>
            """
        
        html_content += """
            <div class="stats">
                <h2>💡 Detected Light Types</h2>
                <table>
                    <tr><th>Light Type</th><th>Count</th><th>Percentage</th></tr>
        """
        
        total_lights = sum(light_type_counts.values())
        for light_type, count in sorted(light_type_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_lights * 100) if total_lights > 0 else 0
            html_content += f"<tr><td>{light_type.replace('_', ' ').title()}</td><td>{count}</td><td>{percentage:.1f}%</td></tr>"
        
        html_content += """
                </table>
            </div>
            
            <div class="stats">
                <h2>📈 Tracked Lights Details</h2>
                <table>
                    <tr><th>Track ID</th><th>Light Type</th><th>Frames</th><th>Duration (s)</th><th>Avg Brightness</th></tr>
        """
        
        for track_id, track in sorted(valid_tracks.items())[:30]:  # Show top 30
            duration = (track.lights[-1].timestamp_ms - track.lights[0].timestamp_ms) / 1000
            avg_brightness = np.mean([l.brightness for l in track.lights])
            html_content += f"""
                    <tr>
                        <td>#{track_id}</td>
                        <td>{track.class_name.replace('_', ' ').title()}</td>
                        <td>{len(track.lights)}</td>
                        <td>{duration:.2f}</td>
                        <td>{avg_brightness:.1f}</td>
                    </tr>
            """
        
        html_content += """
                </table>
            </div>
            
            <div id="charts">
                <h2>📉 Individual Light Analysis (All Tracks)</h2>
                <p><strong>Each light track shows:</strong> RGB color analysis and individual light video.</p>
            </div>
        """
        
        # Generate individual track sections
        for idx, track_data in enumerate(chart_data):
            track_id = track_data['track_id']
            track = track_data['track']
            
            # Create individual charts for this track
            # RGB Values Chart with Elevation
            rgb_fig = go.Figure()
            
            # Add RGB traces on primary Y-axis
            rgb_fig.add_trace(go.Scatter(x=track_data['time_formatted'], y=track_data['r_values'], 
                                       name="Red", line=dict(color='red'), yaxis='y'))
            rgb_fig.add_trace(go.Scatter(x=track_data['time_formatted'], y=track_data['g_values'], 
                                       name="Green", line=dict(color='green'), yaxis='y'))
            rgb_fig.add_trace(go.Scatter(x=track_data['time_formatted'], y=track_data['b_values'], 
                                       name="Blue", line=dict(color='blue'), yaxis='y'))
            
            # Add elevation trace on secondary Y-axis if GPS data exists
            if 'altitudes_for_chart' in track_data:
                valid_alts = [alt for alt in track_data['altitudes_for_chart'] if alt is not None]
                if valid_alts:
                    rgb_fig.add_trace(go.Scatter(
                        x=track_data['time_formatted'], 
                        y=track_data['altitudes_for_chart'],
                        name="Elevation (m)",
                        line=dict(color='purple', width=3),  # Solid line, thicker
                        yaxis='y2',
                        connectgaps=False,
                        opacity=0.8
                    ))
            
            rgb_fig.update_layout(
                title=f"RGB Values & Elevation - {track.class_name} #{track_id}", 
                height=400, 
                xaxis_title="Time (seconds)", 
                yaxis=dict(
                    title="RGB Value",
                    side='left'
                ),
                yaxis2=dict(
                    title="Elevation (m)",
                    side='right',
                    overlaying='y',
                    color='purple',
                    showgrid=False,  # Don't show grid for secondary axis
                    autorange=True  # Auto-scale to show actual variation
                ),
                dragmode='pan',  # Set default mode to pan
                margin=dict(l=60, r=80, t=60, b=80),
                autosize=True,
                xaxis=dict(
                    tickangle=-45,
                    tickmode='auto',
                    nticks=10,
                    showgrid=True,
                    automargin=True
                ),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            # Get individual light video if available
            video_html = ""
            if track_id in light_videos:
                video_relative = os.path.relpath(light_videos[track_id], self.output_dir)
                video_html = f'''
                <div style="display: flex; align-items: center; justify-content: center; height: 400px;">
                    <div style="text-align: center;">
                        <video width="256" height="256" controls loop autoplay muted style="border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                            <source src="{video_relative}" type="video/mp4">
                            Your browser does not support the video tag.
                        </video>
                        <p style="margin-top: 10px; color: #666;">Individual Light Video<br>Track #{track_id}</p>
                    </div>
                </div>
                '''
            
            
            # Add GPS info if available
            gps_info = ""
            if track_data['gps_lats'] and len(track_data['gps_lats']) > 0:
                first_lat = track_data['gps_lats'][0]
                first_lon = track_data['gps_lons'][0]
                avg_alt = np.mean(track_data['gps_alts']) if track_data['gps_alts'] else 0
                gps_info = f"""
                        <div class="stat-item"><strong>GPS:</strong> {format_gps_coordinates(first_lat, first_lon) if GPS_AVAILABLE else f'{first_lat:.6f}, {first_lon:.6f}'}</div>
                        <div class="stat-item"><strong>Altitude:</strong> {avg_alt:.1f}m</div>
                """
            
            # Add color changes summary
            color_changes_html = ""
            if track_data['color_changes']:
                color_changes_html = """
                    <div style="margin-top: 15px; padding: 10px; background: #fff3cd; border-radius: 5px;">
                        <h4 style="margin: 0 0 10px 0;">🎨 Significant Color Changes Detected:</h4>
                        <ul style="margin: 0; padding-left: 20px;">
                """
                for i, change in enumerate(track_data['color_changes'][:3]):  # Show top 3 changes
                    time_str = f"{change['timestamp_ms']/1000:.1f}s"
                    color_changes_html += f"""
                        <li>At {time_str}: {change['dominant_channel'].capitalize()} change (magnitude: {change['magnitude']:.1f})"""
                    
                    if change.get('gps_latitude'):
                        color_changes_html += f"""<br>
                            <small>📍 GPS: {change['gps_latitude']:.6f}, {change['gps_longitude']:.6f} at {change['gps_altitude']:.1f}m</small>"""
                    
                    color_changes_html += "</li>"
                
                color_changes_html += """
                        </ul>
                    </div>
                """
            
            html_content += f"""
            <div class="track-section">
                <div class="track-header">
                    <h3>🔍 Light Track #{track_id} - {track.class_name.replace('_', ' ').title()}</h3>
                    <div class="track-stats">
                        <div class="stat-item"><strong>Duration:</strong> {track_data['duration']:.2f}s</div>
                        <div class="stat-item"><strong>Frames:</strong> {len(track.lights)}</div>
                        <div class="stat-item"><strong>Avg Brightness:</strong> {track_data['avg_brightness']:.1f}</div>
                        <div class="stat-item"><strong>Avg RGB:</strong> R:{track_data['avg_r']:.0f} G:{track_data['avg_g']:.0f} B:{track_data['avg_b']:.0f}</div>
                        {gps_info}
                    </div>
                    {color_changes_html}
                </div>
                
                <div class="charts-row">
                    <div class="chart-container">
                        {pyo.plot(rgb_fig, output_type='div', include_plotlyjs=False)}
                    </div>
                    <div class="chart-container">
                        {video_html}
                    </div>
                </div>
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        # Write report
        report_path.write_text(html_content)
        logger.info(f"Report generated: {report_path}")
        
        return report_path
    
    def _generate_empty_report(self, report_path: Path, video_name: str):
        """Generate empty report when no lights detected"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Light Analysis - {video_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .warning {{ background: #fff3cd; padding: 20px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <h1>Airport Light Analysis Report</h1>
            <div class="warning">
                <h2>No Lights Detected</h2>
                <p>No lights were detected in the video: {video_name}</p>
                <p>This could be due to:</p>
                <ul>
                    <li>Video is too dark or low quality</li>
                    <li>Lights are too small or far away</li>
                    <li>Need to adjust brightness threshold</li>
                </ul>
            </div>
        </body>
        </html>
        """
        report_path.write_text(html_content)


class VideoPipeline:
    """Main pipeline for processing videos with GPS integration"""
    
    def __init__(self, analyze_every_frame=True, sample_interval_ms=50, extract_gps=True):
        self.analyze_every_frame = analyze_every_frame
        self.sample_interval_ms = sample_interval_ms
        self.detector = RunwayLightDetector()
        self.tracker = LightTracker()
        self.extract_gps = extract_gps and GPS_AVAILABLE
        self.gps_extractor = GPSExtractor() if self.extract_gps else None
        self.gps_data = []
        
    def process_video(self, video_path: Path, output_dir: Path) -> Optional[Path]:
        """Process a single video file with GPS extraction"""
        logger.info(f"Processing video for airport lights: {video_path}")
        
        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return None
        
        # Extract GPS data from video if available
        self.gps_data = []
        if self.gps_extractor:
            logger.info("Attempting to extract GPS metadata from video...")
            try:
                self.gps_data = self.gps_extractor.extract_gps_data(video_path)
                if self.gps_data:
                    logger.info(f"Successfully found {len(self.gps_data)} GPS data points")
                    # Log first GPS position
                    first_gps = self.gps_data[0]
                    coords = format_gps_coordinates(first_gps.latitude, first_gps.longitude)
                    logger.info(f"Initial position: {coords}, Altitude: {first_gps.altitude:.1f}m")
                else:
                    logger.info("No GPS data found in video metadata - processing without GPS")
            except Exception as e:
                logger.warning(f"GPS extraction failed: {e} - continuing without GPS")
                self.gps_data = []
        else:
            logger.info("GPS extraction disabled - processing without GPS")
        
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            logger.error(f"Failed to open video: {video_path}")
            return None
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if fps <= 0:
            logger.warning(f"Invalid FPS for {video_path}, using default 30")
            fps = 30
        
        # Determine frame interval based on mode
        if self.analyze_every_frame:
            frame_interval = 1  # Process every frame
            logger.info(f"Video FPS: {fps}, Total frames: {total_frames}, Mode: EVERY FRAME ANALYSIS")
        else:
            frame_interval = max(1, int(fps * self.sample_interval_ms / 1000))
            logger.info(f"Video FPS: {fps}, Total frames: {total_frames}, Sample interval: {frame_interval} frames")
        
        # Reset tracker for new video
        self.tracker = LightTracker()
        
        frame_num = 0
        processed_frames = 0
        total_detections = 0
        
        # Store snapshots
        snapshot_frames = {}
        snapshot_positions = {
            'start': int(total_frames * 0.1),
            'middle': int(total_frames * 0.5),
            'end': int(total_frames * 0.9)
        }
        
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break
            
            # Check if we need to capture a snapshot
            for position, target_frame in snapshot_positions.items():
                if position not in snapshot_frames and abs(frame_num - target_frame) < frame_interval:
                    # Process this frame even if not on interval
                    timestamp_ms = (frame_num / fps) * 1000
                    
                    # Get GPS data for this frame
                    gps_point = None
                    if self.gps_extractor and self.gps_data:
                        gps_point = self.gps_extractor.interpolate_gps_for_frame(self.gps_data, frame_num, fps)
                    
                    lights = self.detector.process(frame, frame_num, timestamp_ms, gps_point)
                    snapshot_frames[position] = (frame.copy(), lights)
                    self.tracker.process(lights)
                    logger.info(f"Captured {position} snapshot at frame {frame_num}")
            
            if frame_num % frame_interval == 0:
                timestamp_ms = (frame_num / fps) * 1000
                
                # Get GPS data for this frame
                gps_point = None
                if self.gps_extractor and self.gps_data:
                    gps_point = self.gps_extractor.interpolate_gps_for_frame(self.gps_data, frame_num, fps)
                
                # Detect lights with GPS data
                lights = self.detector.process(frame, frame_num, timestamp_ms, gps_point)
                total_detections += len(lights)
                
                # Track lights
                self.tracker.process(lights)
                
                processed_frames += 1
                
                # Adjust progress reporting frequency based on analysis mode
                report_interval = 100 if self.analyze_every_frame else 10
                if processed_frames % report_interval == 0:
                    logger.info(f"Processed {processed_frames} {'frames' if self.analyze_every_frame else 'samples'} from {video_path.name}, "
                              f"Total detections: {total_detections}, Active tracks: {len(self.tracker.tracks)}")
            
            frame_num += 1
        
        cap.release()
        
        logger.info(f"Finished processing {video_path.name}: {processed_frames} {'frames' if self.analyze_every_frame else 'samples'} analyzed, "
                   f"{total_detections} total detections, {len(self.tracker.tracks)} tracks created")
        
        # Generate report with snapshots and GPS data
        generator = ReportGenerator(output_dir)
        report_path = generator.generate(video_path, self.tracker.tracks, snapshot_frames, self.gps_data)
        
        return report_path


def main():
    parser = argparse.ArgumentParser(description="Analyze airport/runway lights in videos")
    parser.add_argument('--videos-dir', type=str, default='videos',
                       help='Directory containing video files')
    parser.add_argument('--output-dir', type=str, default='reports',
                       help='Directory for output reports')
    parser.add_argument('--interval', type=int, default=50,
                       help='Frame sampling interval in milliseconds (ignored if --every-frame is used)')
    parser.add_argument('--no-gps', action='store_true',
                       help='Disable GPS metadata extraction (speeds up processing)')
    parser.add_argument('--every-frame', action='store_true',
                       help='Analyze every single frame instead of sampling (more accurate but slower)')
    parser.add_argument('--sample-mode', action='store_true',
                       help='Use sampling mode instead of every frame (faster but less accurate)')
    args = parser.parse_args()
    
    videos_dir = Path(args.videos_dir)
    output_dir = Path(args.output_dir)
    
    if not videos_dir.exists():
        logger.error(f"Videos directory not found: {videos_dir}")
        return
    
    # Find all video files
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
    video_files = []
    for ext in video_extensions:
        video_files.extend(videos_dir.glob(f"*{ext}"))
        video_files.extend(videos_dir.glob(f"*{ext.upper()}"))
    
    if not video_files:
        logger.warning(f"No video files found in {videos_dir}")
        return
    
    logger.info(f"Found {len(video_files)} video files to process")
    
    # Determine analysis mode (default to every frame for best quality)
    analyze_every_frame = not args.sample_mode
    
    if analyze_every_frame:
        logger.info("Mode: EVERY FRAME ANALYSIS (best quality)")
    else:
        logger.info(f"Mode: SAMPLING (every {args.interval}ms)")
    
    # Process each video
    pipeline = VideoPipeline(
        analyze_every_frame=analyze_every_frame,
        sample_interval_ms=args.interval, 
        extract_gps=not args.no_gps
    )
    
    for video_file in video_files:
        try:
            report_path = pipeline.process_video(video_file, output_dir)
            if report_path:
                logger.info(f"Successfully processed {video_file.name}")
        except Exception as e:
            logger.error(f"Error processing {video_file.name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    logger.info("All videos processed")


if __name__ == "__main__":
    main()