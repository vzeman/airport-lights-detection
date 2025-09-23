"""PAPI Light Detection Module"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
import config

class PAPIDetector:
    """Detects PAPI lights in airport images"""
    
    def __init__(self, threshold: int = config.BRIGHTNESS_THRESHOLD):
        self.threshold = threshold
        self.debug = config.DEBUG_MODE
        
    def detect_papi_systems(self, image: np.ndarray) -> List[Dict]:
        """
        Main detection pipeline for PAPI systems
        
        Args:
            image: Input image (BGR format)
            
        Returns:
            List of detected PAPI systems with their properties
        """
        # Preprocess image
        preprocessed = self._preprocess_image(image)
        
        # Detect bright spots
        light_candidates = self._detect_bright_spots(preprocessed)
        
        # Group and validate PAPI patterns
        papi_systems = self._identify_papi_patterns(light_candidates, image.shape)
        
        # Refine detection with color analysis
        validated_systems = self._validate_with_color(papi_systems, image)
        
        return validated_systems
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better light detection"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (config.GAUSSIAN_KERNEL_SIZE, config.GAUSSIAN_KERNEL_SIZE), 0)
        
        # Enhance contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)
        
        return enhanced
    
    def _detect_bright_spots(self, gray_image: np.ndarray) -> List[Dict]:
        """Detect bright spots that could be lights"""
        # Threshold to find bright regions
        _, binary = cv2.threshold(gray_image, self.threshold, 255, cv2.THRESH_BINARY)
        
        # Morphological operations to clean up
        kernel = np.ones((config.MORPHOLOGICAL_KERNEL_SIZE, config.MORPHOLOGICAL_KERNEL_SIZE), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Extract light candidates
        light_candidates = []
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter by area
            if config.MIN_LIGHT_AREA <= area <= config.MAX_LIGHT_AREA:
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                
                # Calculate center and properties
                M = cv2.moments(contour)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    light_candidates.append({
                        'center': (cx, cy),
                        'bbox': (x, y, w, h),
                        'area': area,
                        'contour': contour,
                        'intensity': np.mean(gray_image[y:y+h, x:x+w])
                    })
        
        # Sort by x-coordinate for easier grouping
        light_candidates.sort(key=lambda x: x['center'][0])
        
        return light_candidates
    
    def _identify_papi_patterns(self, candidates: List[Dict], image_shape: Tuple) -> List[Dict]:
        """Group candidates into potential PAPI systems"""
        if len(candidates) < config.APAPI_LIGHT_COUNT:
            return []
        
        papi_systems = []
        used_indices = set()
        
        # Try to find groups of 4 lights (standard PAPI)
        for i in range(len(candidates)):
            if i in used_indices:
                continue
                
            # Look for 3 more lights to form a group of 4
            group = [candidates[i]]
            base_y = candidates[i]['center'][1]
            
            for j in range(i + 1, len(candidates)):
                if j in used_indices:
                    continue
                    
                # Check vertical alignment
                if abs(candidates[j]['center'][1] - base_y) <= config.HORIZONTAL_TOLERANCE:
                    group.append(candidates[j])
                    
                    if len(group) == config.PAPI_LIGHT_COUNT:
                        break
            
            # Validate group
            if len(group) == config.PAPI_LIGHT_COUNT:
                if self._validate_papi_geometry(group):
                    papi_systems.append({
                        'lights': group,
                        'type': 'PAPI-4',
                        'confidence': self._calculate_confidence(group)
                    })
                    for g in group:
                        used_indices.add(candidates.index(g))
            
            # Also check for 2-light A-PAPI systems
            elif len(group) >= config.APAPI_LIGHT_COUNT:
                group_2 = group[:config.APAPI_LIGHT_COUNT]
                if self._validate_papi_geometry(group_2, is_apapi=True):
                    papi_systems.append({
                        'lights': group_2,
                        'type': 'A-PAPI',
                        'confidence': self._calculate_confidence(group_2)
                    })
                    for g in group_2:
                        idx = candidates.index(g)
                        if idx not in used_indices:
                            used_indices.add(idx)
        
        return papi_systems
    
    def _validate_papi_geometry(self, group: List[Dict], is_apapi: bool = False) -> bool:
        """Validate geometric arrangement of lights"""
        expected_count = config.APAPI_LIGHT_COUNT if is_apapi else config.PAPI_LIGHT_COUNT
        
        if len(group) != expected_count:
            return False
        
        # Check horizontal alignment
        y_coords = [light['center'][1] for light in group]
        y_variance = np.std(y_coords)
        if y_variance > config.HORIZONTAL_TOLERANCE / 2:
            return False
        
        # Check spacing consistency
        x_coords = [light['center'][0] for light in group]
        spacings = [x_coords[i+1] - x_coords[i] for i in range(len(x_coords)-1)]
        
        if len(spacings) > 0:
            mean_spacing = np.mean(spacings)
            for spacing in spacings:
                if abs(spacing - mean_spacing) / mean_spacing > config.SPACING_TOLERANCE:
                    return False
        
        # Check aspect ratio of the group
        total_width = x_coords[-1] - x_coords[0]
        total_height = max(y_coords) - min(y_coords) + np.mean([light['bbox'][3] for light in group])
        
        if total_height > 0:
            aspect_ratio = total_width / total_height
            if not (config.MIN_ASPECT_RATIO <= aspect_ratio <= config.MAX_ASPECT_RATIO):
                return False
        
        return True
    
    def _validate_with_color(self, papi_systems: List[Dict], image: np.ndarray) -> List[Dict]:
        """Validate and enhance detection using color analysis"""
        validated = []
        
        for system in papi_systems:
            # Extract RGB values for each light
            for light in system['lights']:
                x, y, w, h = light['bbox']
                
                # Expand ROI slightly
                x1 = max(0, x - config.ROI_EXPANSION)
                y1 = max(0, y - config.ROI_EXPANSION)
                x2 = min(image.shape[1], x + w + config.ROI_EXPANSION)
                y2 = min(image.shape[0], y + h + config.ROI_EXPANSION)
                
                roi = image[y1:y2, x1:x2]
                
                # Calculate mean RGB values
                if roi.size > 0:
                    # Find brightest pixels in ROI
                    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                    bright_mask = gray_roi > self.threshold
                    
                    if np.any(bright_mask):
                        # Calculate mean RGB of bright pixels
                        bright_pixels = roi[bright_mask]
                        mean_bgr = np.mean(bright_pixels, axis=0)
                        
                        # OpenCV uses BGR, convert to RGB
                        light['rgb'] = (int(mean_bgr[2]), int(mean_bgr[1]), int(mean_bgr[0]))
                        light['color'] = self._classify_light_color(light['rgb'])
                    else:
                        light['rgb'] = (0, 0, 0)
                        light['color'] = 'UNKNOWN'
                else:
                    light['rgb'] = (0, 0, 0)
                    light['color'] = 'UNKNOWN'
            
            # Validate that we have meaningful colors
            colors = [light['color'] for light in system['lights']]
            if 'UNKNOWN' not in colors:
                system['color_pattern'] = colors
                system['glide_status'] = self._determine_glide_status(colors)
                validated.append(system)
        
        return validated
    
    def _classify_light_color(self, rgb: Tuple[int, int, int]) -> str:
        """Classify light as RED, WHITE, or UNKNOWN"""
        r, g, b = rgb
        
        # Check minimum intensity
        if max(r, g, b) < config.MIN_INTENSITY:
            return 'UNKNOWN'
        
        # Check for red light
        if g > 0 and b > 0:  # Avoid division by zero
            if r / g > config.RED_RATIO_THRESHOLD and r / b > config.RED_RATIO_THRESHOLD:
                return 'RED'
        
        # Check for white light
        if abs(r - g) < config.WHITE_BALANCE_THRESHOLD and \
           abs(g - b) < config.WHITE_BALANCE_THRESHOLD and \
           abs(r - b) < config.WHITE_BALANCE_THRESHOLD and \
           r > config.MIN_INTENSITY:
            return 'WHITE'
        
        # Check if it's reddish-white (common in some conditions)
        if r > 200 and g > 150 and b > 150 and r > g and r > b:
            if (r - g) < 60 and (r - b) < 60:
                return 'WHITE'
        
        return 'UNKNOWN'
    
    def _determine_glide_status(self, colors: List[str]) -> str:
        """Determine glide path status based on color pattern"""
        red_count = colors.count('RED')
        white_count = colors.count('WHITE')
        
        if len(colors) == 4:
            if red_count == 4:
                return "TOO LOW - Increase altitude immediately"
            elif red_count == 3 and white_count == 1:
                return "SLIGHTLY LOW - Increase altitude"
            elif red_count == 2 and white_count == 2:
                return "ON GLIDE PATH - Maintain current approach"
            elif red_count == 1 and white_count == 3:
                return "SLIGHTLY HIGH - Decrease altitude"
            elif white_count == 4:
                return "TOO HIGH - Decrease altitude"
        elif len(colors) == 2:  # A-PAPI
            if red_count == 2:
                return "TOO LOW - Increase altitude"
            elif red_count == 1 and white_count == 1:
                return "ON GLIDE PATH - Maintain current approach"
            elif white_count == 2:
                return "TOO HIGH - Decrease altitude"
        
        return "UNABLE TO DETERMINE"
    
    def _calculate_confidence(self, group: List[Dict]) -> float:
        """Calculate confidence score for detection"""
        # Factors: intensity consistency, spacing consistency, size consistency
        
        # Intensity consistency
        intensities = [light['intensity'] for light in group]
        intensity_std = np.std(intensities) / (np.mean(intensities) + 1e-6)
        intensity_score = max(0, 1 - intensity_std)
        
        # Size consistency
        areas = [light['area'] for light in group]
        area_std = np.std(areas) / (np.mean(areas) + 1e-6)
        size_score = max(0, 1 - area_std)
        
        # Spacing consistency (if more than 2 lights)
        if len(group) > 2:
            x_coords = [light['center'][0] for light in group]
            spacings = [x_coords[i+1] - x_coords[i] for i in range(len(x_coords)-1)]
            spacing_std = np.std(spacings) / (np.mean(spacings) + 1e-6)
            spacing_score = max(0, 1 - spacing_std)
        else:
            spacing_score = 0.8  # Default for 2-light systems
        
        # Weighted average
        confidence = (intensity_score * 0.3 + size_score * 0.3 + spacing_score * 0.4)
        
        return round(confidence, 2)