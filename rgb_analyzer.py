"""RGB Analysis Module for PAPI Lights"""

import numpy as np
from typing import List, Dict, Tuple
import cv2

class RGBAnalyzer:
    """Analyzes RGB values and differences between PAPI lights"""
    
    def __init__(self):
        self.comparison_matrix = None
        
    def analyze_papi_system(self, papi_system: Dict, image: np.ndarray) -> Dict:
        """
        Comprehensive RGB analysis of a PAPI system
        
        Args:
            papi_system: Detected PAPI system dictionary
            image: Original image for detailed analysis
            
        Returns:
            Enhanced system dictionary with RGB analysis
        """
        lights = papi_system['lights']
        
        # Extract detailed RGB statistics
        for i, light in enumerate(lights):
            light['detailed_rgb'] = self._extract_detailed_rgb(light, image)
            light['light_number'] = i + 1
        
        # Calculate all pairwise differences
        papi_system['rgb_differences'] = self._calculate_rgb_differences(lights)
        
        # Generate comparison matrix
        papi_system['comparison_matrix'] = self._generate_comparison_matrix(lights)
        
        # Calculate quality metrics
        papi_system['quality_metrics'] = self._calculate_quality_metrics(lights)
        
        # Analyze color consistency
        papi_system['color_consistency'] = self._analyze_color_consistency(lights)
        
        return papi_system
    
    def _extract_detailed_rgb(self, light: Dict, image: np.ndarray) -> Dict:
        """Extract detailed RGB statistics for a light"""
        x, y, w, h = light['bbox']
        
        # Get ROI with some padding
        padding = 5
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(image.shape[1], x + w + padding)
        y2 = min(image.shape[0], y + h + padding)
        
        roi = image[y1:y2, x1:x2]
        
        # Convert to RGB (OpenCV uses BGR)
        roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        
        # Find bright pixels
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        bright_mask = gray_roi > 200  # High threshold for light core
        
        detailed_stats = {}
        
        if np.any(bright_mask):
            bright_pixels = roi_rgb[bright_mask]
            
            # Calculate statistics
            detailed_stats['mean_rgb'] = tuple(map(int, np.mean(bright_pixels, axis=0)))
            detailed_stats['median_rgb'] = tuple(map(int, np.median(bright_pixels, axis=0)))
            detailed_stats['std_rgb'] = tuple(map(float, np.std(bright_pixels, axis=0).round(2)))
            detailed_stats['min_rgb'] = tuple(map(int, np.min(bright_pixels, axis=0)))
            detailed_stats['max_rgb'] = tuple(map(int, np.max(bright_pixels, axis=0)))
            
            # Calculate color metrics
            r, g, b = detailed_stats['mean_rgb']
            detailed_stats['brightness'] = int((r + g + b) / 3)
            detailed_stats['saturation'] = self._calculate_saturation(r, g, b)
            detailed_stats['hue'] = self._calculate_hue(r, g, b)
            
            # Color dominance
            if r > 0 and g > 0 and b > 0:
                detailed_stats['red_dominance'] = round(r / (r + g + b), 3)
                detailed_stats['green_dominance'] = round(g / (r + g + b), 3)
                detailed_stats['blue_dominance'] = round(b / (r + g + b), 3)
        else:
            # Default values if no bright pixels found
            detailed_stats = {
                'mean_rgb': (0, 0, 0),
                'median_rgb': (0, 0, 0),
                'std_rgb': (0.0, 0.0, 0.0),
                'min_rgb': (0, 0, 0),
                'max_rgb': (0, 0, 0),
                'brightness': 0,
                'saturation': 0.0,
                'hue': 0.0,
                'red_dominance': 0.0,
                'green_dominance': 0.0,
                'blue_dominance': 0.0
            }
        
        return detailed_stats
    
    def _calculate_rgb_differences(self, lights: List[Dict]) -> Dict:
        """Calculate RGB differences between all light pairs"""
        differences = {}
        
        for i in range(len(lights)):
            for j in range(i + 1, len(lights)):
                light1 = lights[i]
                light2 = lights[j]
                
                # Get RGB values
                rgb1 = light1.get('detailed_rgb', {}).get('mean_rgb', light1.get('rgb', (0, 0, 0)))
                rgb2 = light2.get('detailed_rgb', {}).get('mean_rgb', light2.get('rgb', (0, 0, 0)))
                
                # Calculate differences
                diff_key = f"Light_{i+1}_vs_Light_{j+1}"
                differences[diff_key] = {
                    'rgb_diff': (
                        abs(rgb1[0] - rgb2[0]),
                        abs(rgb1[1] - rgb2[1]),
                        abs(rgb1[2] - rgb2[2])
                    ),
                    'euclidean_distance': round(np.sqrt(
                        (rgb1[0] - rgb2[0])**2 + 
                        (rgb1[1] - rgb2[1])**2 + 
                        (rgb1[2] - rgb2[2])**2
                    ), 2),
                    'brightness_diff': abs(
                        sum(rgb1)/3 - sum(rgb2)/3
                    ),
                    'same_color': light1.get('color', '') == light2.get('color', ''),
                    'colors': (light1.get('color', 'UNKNOWN'), light2.get('color', 'UNKNOWN'))
                }
        
        return differences
    
    def _generate_comparison_matrix(self, lights: List[Dict]) -> np.ndarray:
        """Generate a comparison matrix for all lights"""
        n = len(lights)
        matrix = np.zeros((n, n, 3))  # 3 channels for RGB
        
        for i in range(n):
            for j in range(n):
                if i == j:
                    # Diagonal: actual RGB values
                    rgb = lights[i].get('detailed_rgb', {}).get('mean_rgb', lights[i].get('rgb', (0, 0, 0)))
                    matrix[i, j] = rgb
                else:
                    # Off-diagonal: differences
                    rgb1 = lights[i].get('detailed_rgb', {}).get('mean_rgb', lights[i].get('rgb', (0, 0, 0)))
                    rgb2 = lights[j].get('detailed_rgb', {}).get('mean_rgb', lights[j].get('rgb', (0, 0, 0)))
                    matrix[i, j] = [
                        abs(rgb1[0] - rgb2[0]),
                        abs(rgb1[1] - rgb2[1]),
                        abs(rgb1[2] - rgb2[2])
                    ]
        
        return matrix
    
    def _calculate_quality_metrics(self, lights: List[Dict]) -> Dict:
        """Calculate quality metrics for the PAPI system"""
        metrics = {}
        
        # Separate lights by color
        red_lights = [l for l in lights if l.get('color') == 'RED']
        white_lights = [l for l in lights if l.get('color') == 'WHITE']
        
        # Color purity metrics
        if red_lights:
            red_rgbs = [l.get('detailed_rgb', {}).get('mean_rgb', l.get('rgb', (0, 0, 0))) 
                       for l in red_lights]
            metrics['red_purity'] = self._calculate_color_purity(red_rgbs, 'RED')
            metrics['red_consistency'] = self._calculate_consistency(red_rgbs)
        
        if white_lights:
            white_rgbs = [l.get('detailed_rgb', {}).get('mean_rgb', l.get('rgb', (0, 0, 0))) 
                         for l in white_lights]
            metrics['white_purity'] = self._calculate_color_purity(white_rgbs, 'WHITE')
            metrics['white_consistency'] = self._calculate_consistency(white_rgbs)
        
        # Overall brightness consistency
        all_brightness = [l.get('detailed_rgb', {}).get('brightness', 0) for l in lights]
        if all_brightness:
            metrics['brightness_consistency'] = round(
                1 - (np.std(all_brightness) / (np.mean(all_brightness) + 1e-6)), 3
            )
            metrics['avg_brightness'] = round(np.mean(all_brightness), 1)
        
        # Geometric alignment score
        y_positions = [l['center'][1] for l in lights]
        metrics['alignment_score'] = round(
            1 - (np.std(y_positions) / (np.mean(y_positions) + 1e-6)), 3
        )
        
        return metrics
    
    def _analyze_color_consistency(self, lights: List[Dict]) -> Dict:
        """Analyze color consistency across lights"""
        consistency = {}
        
        # Group by color
        color_groups = {}
        for light in lights:
            color = light.get('color', 'UNKNOWN')
            if color not in color_groups:
                color_groups[color] = []
            color_groups[color].append(light)
        
        # Analyze each color group
        for color, group in color_groups.items():
            if len(group) > 1:
                rgbs = [l.get('detailed_rgb', {}).get('mean_rgb', l.get('rgb', (0, 0, 0))) 
                       for l in group]
                
                # Calculate variance within group
                r_values = [rgb[0] for rgb in rgbs]
                g_values = [rgb[1] for rgb in rgbs]
                b_values = [rgb[2] for rgb in rgbs]
                
                consistency[f'{color.lower()}_group'] = {
                    'count': len(group),
                    'r_variance': round(np.var(r_values), 2),
                    'g_variance': round(np.var(g_values), 2),
                    'b_variance': round(np.var(b_values), 2),
                    'mean_rgb': tuple(map(int, [np.mean(r_values), np.mean(g_values), np.mean(b_values)])),
                    'consistency_score': round(self._calculate_consistency(rgbs), 3)
                }
        
        # Overall pattern consistency
        pattern = [l.get('color', 'UNKNOWN') for l in lights]
        consistency['pattern'] = pattern
        consistency['pattern_valid'] = self._validate_pattern(pattern)
        
        return consistency
    
    def _calculate_saturation(self, r: int, g: int, b: int) -> float:
        """Calculate color saturation"""
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        
        if max_val == 0:
            return 0.0
        
        saturation = (max_val - min_val) / max_val
        return round(saturation, 3)
    
    def _calculate_hue(self, r: int, g: int, b: int) -> float:
        """Calculate color hue in degrees"""
        r, g, b = r/255.0, g/255.0, b/255.0
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        diff = max_val - min_val
        
        if diff == 0:
            return 0.0
        
        if max_val == r:
            hue = ((g - b) / diff) % 6
        elif max_val == g:
            hue = (b - r) / diff + 2
        else:
            hue = (r - g) / diff + 4
        
        hue = hue * 60
        return round(hue, 1)
    
    def _calculate_color_purity(self, rgbs: List[Tuple], color_type: str) -> float:
        """Calculate how pure a color is"""
        if not rgbs:
            return 0.0
        
        purities = []
        for rgb in rgbs:
            r, g, b = rgb
            if color_type == 'RED':
                # Red purity: high red, low green/blue
                if r > 0:
                    purity = (r - (g + b)/2) / r
                else:
                    purity = 0
            elif color_type == 'WHITE':
                # White purity: balanced RGB
                avg = (r + g + b) / 3
                if avg > 0:
                    variance = np.var([r, g, b])
                    purity = 1 - (variance / (avg * avg))
                else:
                    purity = 0
            else:
                purity = 0
            
            purities.append(max(0, min(1, purity)))
        
        return round(np.mean(purities), 3)
    
    def _calculate_consistency(self, rgbs: List[Tuple]) -> float:
        """Calculate consistency score for a group of RGB values"""
        if len(rgbs) <= 1:
            return 1.0
        
        # Calculate coefficient of variation for each channel
        r_values = [rgb[0] for rgb in rgbs]
        g_values = [rgb[1] for rgb in rgbs]
        b_values = [rgb[2] for rgb in rgbs]
        
        cv_r = np.std(r_values) / (np.mean(r_values) + 1e-6)
        cv_g = np.std(g_values) / (np.mean(g_values) + 1e-6)
        cv_b = np.std(b_values) / (np.mean(b_values) + 1e-6)
        
        # Consistency is inverse of average CV
        avg_cv = (cv_r + cv_g + cv_b) / 3
        consistency = max(0, 1 - avg_cv)
        
        return consistency
    
    def _validate_pattern(self, pattern: List[str]) -> bool:
        """Validate if the color pattern is a valid PAPI configuration"""
        valid_4_light = [
            ['RED', 'RED', 'RED', 'RED'],
            ['RED', 'RED', 'RED', 'WHITE'],
            ['RED', 'RED', 'WHITE', 'WHITE'],
            ['RED', 'WHITE', 'WHITE', 'WHITE'],
            ['WHITE', 'WHITE', 'WHITE', 'WHITE']
        ]
        
        valid_2_light = [
            ['RED', 'RED'],
            ['RED', 'WHITE'],
            ['WHITE', 'WHITE']
        ]
        
        if len(pattern) == 4:
            return pattern in valid_4_light
        elif len(pattern) == 2:
            return pattern in valid_2_light
        
        return False