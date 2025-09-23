"""Report Generation Module for PAPI Analysis"""

import os
import json
from datetime import datetime
from typing import List, Dict
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import cv2

class ReportGenerator:
    """Generates comprehensive reports for PAPI analysis"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def generate_report(self, image_path: str, papi_systems: List[Dict], original_image: np.ndarray) -> str:
        """
        Generate comprehensive report for analyzed image
        
        Args:
            image_path: Path to the original image
            papi_systems: List of detected and analyzed PAPI systems
            original_image: Original image array
            
        Returns:
            Path to generated report
        """
        # Create report directory for this image
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        report_dir = os.path.join(self.output_dir, f"{image_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(report_dir, exist_ok=True)
        
        # Generate visualizations
        self._create_detection_visualization(original_image, papi_systems, report_dir, image_name)
        self._create_rgb_heatmap(papi_systems, report_dir, image_name)
        
        # Generate JSON report
        json_report = self._generate_json_report(image_path, papi_systems)
        json_path = os.path.join(report_dir, f"{image_name}_data.json")
        with open(json_path, 'w') as f:
            json.dump(json_report, f, indent=2)
        
        # Generate HTML report
        html_report = self._generate_html_report(image_name, papi_systems, report_dir)
        html_path = os.path.join(report_dir, f"{image_name}_report.html")
        with open(html_path, 'w') as f:
            f.write(html_report)
        
        # Generate text summary
        text_summary = self._generate_text_summary(image_path, papi_systems)
        text_path = os.path.join(report_dir, f"{image_name}_summary.txt")
        with open(text_path, 'w') as f:
            f.write(text_summary)
        
        print(f"Report generated: {html_path}")
        return html_path
    
    def _create_detection_visualization(self, image: np.ndarray, papi_systems: List[Dict], 
                                       report_dir: str, image_name: str):
        """Create visualization of detected PAPI systems"""
        # Convert BGR to RGB for matplotlib
        img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.imshow(img_rgb)
        
        # Draw detections
        for i, system in enumerate(papi_systems):
            for j, light in enumerate(system['lights']):
                x, y, w, h = light['bbox']
                color = light.get('color', 'UNKNOWN')
                
                # Choose box color based on light color
                if color == 'RED':
                    box_color = 'red'
                elif color == 'WHITE':
                    box_color = 'yellow'
                else:
                    box_color = 'gray'
                
                # Draw bounding box
                rect = patches.Rectangle((x, y), w, h, linewidth=2, 
                                        edgecolor=box_color, facecolor='none')
                ax.add_patch(rect)
                
                # Add label
                rgb = light.get('rgb', (0, 0, 0))
                label = f"L{j+1}: {color}\nRGB:{rgb}"
                ax.text(x, y-5, label, color='white', fontsize=8,
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='black', alpha=0.7))
            
            # Add system info
            status = system.get('glide_status', 'Unknown')
            confidence = system.get('confidence', 0)
            system_label = f"PAPI System {i+1}\n{status}\nConfidence: {confidence:.2f}"
            
            # Position label above the system
            min_y = min(l['bbox'][1] for l in system['lights'])
            min_x = min(l['bbox'][0] for l in system['lights'])
            ax.text(min_x, min_y - 40, system_label, color='white', fontsize=10,
                   bbox=dict(boxstyle="round,pad=0.5", facecolor='blue', alpha=0.7))
        
        ax.set_title(f"PAPI Detection Results - {image_name}")
        ax.axis('off')
        
        plt.tight_layout()
        plt.savefig(os.path.join(report_dir, f"{image_name}_detection.png"), dpi=150)
        plt.close()
    
    def _create_rgb_heatmap(self, papi_systems: List[Dict], report_dir: str, image_name: str):
        """Create RGB heatmap and difference matrix visualization"""
        for i, system in enumerate(papi_systems):
            lights = system['lights']
            n_lights = len(lights)
            
            if n_lights == 0:
                continue
            
            fig, axes = plt.subplots(2, 2, figsize=(12, 10))
            
            # RGB Values Bar Chart
            ax = axes[0, 0]
            light_labels = [f"Light {j+1}" for j in range(n_lights)]
            r_values = [l.get('detailed_rgb', {}).get('mean_rgb', l.get('rgb', (0,0,0)))[0] for l in lights]
            g_values = [l.get('detailed_rgb', {}).get('mean_rgb', l.get('rgb', (0,0,0)))[1] for l in lights]
            b_values = [l.get('detailed_rgb', {}).get('mean_rgb', l.get('rgb', (0,0,0)))[2] for l in lights]
            
            x = np.arange(n_lights)
            width = 0.25
            
            ax.bar(x - width, r_values, width, label='Red', color='red', alpha=0.7)
            ax.bar(x, g_values, width, label='Green', color='green', alpha=0.7)
            ax.bar(x + width, b_values, width, label='Blue', color='blue', alpha=0.7)
            
            ax.set_xlabel('Light Number')
            ax.set_ylabel('RGB Value')
            ax.set_title('RGB Values by Light')
            ax.set_xticks(x)
            ax.set_xticklabels(light_labels)
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            # Color Classification
            ax = axes[0, 1]
            colors = [l.get('color', 'UNKNOWN') for l in lights]
            color_map = {'RED': 'red', 'WHITE': 'lightgray', 'UNKNOWN': 'black'}
            bar_colors = [color_map[c] for c in colors]
            
            brightness = [l.get('detailed_rgb', {}).get('brightness', 0) for l in lights]
            bars = ax.bar(light_labels, brightness, color=bar_colors, alpha=0.7)
            
            # Add color labels on bars
            for bar, color in zip(bars, colors):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height/2,
                       color, ha='center', va='center', fontweight='bold')
            
            ax.set_ylabel('Brightness')
            ax.set_title('Light Classification and Brightness')
            ax.grid(True, alpha=0.3)
            
            # Difference Matrix Heatmap
            ax = axes[1, 0]
            if 'comparison_matrix' in system:
                matrix = system['comparison_matrix']
                # Calculate euclidean distances for visualization
                dist_matrix = np.zeros((n_lights, n_lights))
                for j in range(n_lights):
                    for k in range(n_lights):
                        if j == k:
                            dist_matrix[j, k] = 0
                        else:
                            dist_matrix[j, k] = np.linalg.norm(matrix[j, k])
                
                im = ax.imshow(dist_matrix, cmap='RdYlGn_r', aspect='auto')
                ax.set_xticks(range(n_lights))
                ax.set_yticks(range(n_lights))
                ax.set_xticklabels(light_labels)
                ax.set_yticklabels(light_labels)
                ax.set_title('RGB Difference Matrix (Euclidean Distance)')
                
                # Add values in cells
                for j in range(n_lights):
                    for k in range(n_lights):
                        text = ax.text(k, j, f'{dist_matrix[j, k]:.0f}',
                                     ha="center", va="center", color="black", fontsize=10)
                
                plt.colorbar(im, ax=ax)
            
            # Quality Metrics
            ax = axes[1, 1]
            if 'quality_metrics' in system:
                metrics = system['quality_metrics']
                metric_names = list(metrics.keys())
                metric_values = list(metrics.values())
                
                # Convert to percentages where appropriate
                display_values = []
                for name, value in zip(metric_names, metric_values):
                    if 'consistency' in name or 'score' in name or 'purity' in name:
                        display_values.append(value * 100)
                    else:
                        display_values.append(value)
                
                y_pos = np.arange(len(metric_names))
                ax.barh(y_pos, display_values, alpha=0.7)
                ax.set_yticks(y_pos)
                ax.set_yticklabels(metric_names)
                ax.set_xlabel('Value')
                ax.set_title('Quality Metrics')
                ax.grid(True, alpha=0.3, axis='x')
                
                # Add values on bars
                for j, (name, value) in enumerate(zip(metric_names, display_values)):
                    if 'consistency' in name or 'score' in name or 'purity' in name:
                        label = f'{value:.1f}%'
                    else:
                        label = f'{value:.1f}'
                    ax.text(value, j, f' {label}', va='center')
            
            plt.suptitle(f'PAPI System {i+1} Analysis - {system.get("type", "Unknown")}')
            plt.tight_layout()
            plt.savefig(os.path.join(report_dir, f"{image_name}_system_{i+1}_analysis.png"), dpi=150)
            plt.close()
    
    def _generate_json_report(self, image_path: str, papi_systems: List[Dict]) -> Dict:
        """Generate JSON format report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'image_path': image_path,
            'analysis_version': '1.0',
            'summary': {
                'total_systems_detected': len(papi_systems),
                'detection_successful': len(papi_systems) > 0
            },
            'papi_systems': []
        }
        
        for i, system in enumerate(papi_systems):
            system_data = {
                'system_id': i + 1,
                'type': system.get('type', 'Unknown'),
                'confidence': system.get('confidence', 0),
                'glide_status': system.get('glide_status', 'Unknown'),
                'color_pattern': system.get('color_pattern', []),
                'lights': []
            }
            
            for light in system['lights']:
                light_data = {
                    'light_number': light.get('light_number', 0),
                    'position': light['center'],
                    'bbox': light['bbox'],
                    'color': light.get('color', 'UNKNOWN'),
                    'rgb': light.get('rgb', (0, 0, 0)),
                    'detailed_rgb': light.get('detailed_rgb', {})
                }
                system_data['lights'].append(light_data)
            
            # Add analysis results
            if 'rgb_differences' in system:
                system_data['rgb_differences'] = system['rgb_differences']
            if 'quality_metrics' in system:
                system_data['quality_metrics'] = system['quality_metrics']
            if 'color_consistency' in system:
                system_data['color_consistency'] = system['color_consistency']
            
            report['papi_systems'].append(system_data)
        
        return report
    
    def _generate_html_report(self, image_name: str, papi_systems: List[Dict], report_dir: str) -> str:
        """Generate HTML format report"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>PAPI Analysis Report - {image_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        h3 {{ color: #7f8c8d; }}
        .system-box {{ 
            background: white; 
            border: 1px solid #ddd; 
            border-radius: 8px; 
            padding: 20px; 
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .status {{ 
            font-size: 18px; 
            font-weight: bold; 
            padding: 10px; 
            border-radius: 5px;
            text-align: center;
            margin: 10px 0;
        }}
        .status.on-path {{ background-color: #2ecc71; color: white; }}
        .status.low {{ background-color: #e74c3c; color: white; }}
        .status.high {{ background-color: #f39c12; color: white; }}
        table {{ 
            width: 100%; 
            border-collapse: collapse; 
            margin: 15px 0;
            background: white;
        }}
        th, td {{ 
            padding: 12px; 
            text-align: left; 
            border: 1px solid #ddd; 
        }}
        th {{ 
            background-color: #3498db; 
            color: white;
            font-weight: bold;
        }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .light-box {{ 
            display: inline-block; 
            width: 30px; 
            height: 30px; 
            margin: 0 5px;
            border: 2px solid #333;
            border-radius: 50%;
        }}
        .red {{ background-color: #e74c3c; }}
        .white {{ background-color: #ecf0f1; }}
        .unknown {{ background-color: #95a5a6; }}
        .metrics {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .metric {{ 
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #3498db;
        }}
        .metric-label {{ 
            font-size: 12px; 
            color: #7f8c8d;
            text-transform: uppercase;
        }}
        .metric-value {{ 
            font-size: 24px; 
            font-weight: bold;
            color: #2c3e50;
        }}
        img {{ 
            max-width: 100%; 
            height: auto; 
            border: 1px solid #ddd;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .summary {{ 
            background: #e8f4f8;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <h1>PAPI Light Analysis Report</h1>
    <div class="summary">
        <p><strong>Image:</strong> {image_name}</p>
        <p><strong>Analysis Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Systems Detected:</strong> {len(papi_systems)}</p>
    </div>
    
    <h2>Detection Visualization</h2>
    <img src="{image_name}_detection.png" alt="Detection Results">
"""
        
        for i, system in enumerate(papi_systems):
            status = system.get('glide_status', 'Unknown')
            status_class = 'on-path' if 'ON GLIDE' in status else 'low' if 'LOW' in status else 'high' if 'HIGH' in status else ''
            
            html += f"""
    <div class="system-box">
        <h2>PAPI System {i+1} - {system.get('type', 'Unknown')}</h2>
        <div class="status {status_class}">{status}</div>
        
        <h3>Light Pattern</h3>
        <div style="text-align: center; margin: 20px 0;">
"""
            for color in system.get('color_pattern', []):
                color_class = color.lower() if color in ['RED', 'WHITE'] else 'unknown'
                html += f'            <div class="light-box {color_class}" title="{color}"></div>\n'
            
            html += """        </div>
        
        <h3>RGB Values and Analysis</h3>
        <table>
            <tr>
                <th>Light</th>
                <th>Color</th>
                <th>RGB Mean</th>
                <th>Brightness</th>
                <th>Saturation</th>
            </tr>
"""
            for light in system['lights']:
                detailed = light.get('detailed_rgb', {})
                rgb = detailed.get('mean_rgb', light.get('rgb', (0, 0, 0)))
                html += f"""
            <tr>
                <td>Light {light.get('light_number', 0)}</td>
                <td>{light.get('color', 'UNKNOWN')}</td>
                <td>R:{rgb[0]} G:{rgb[1]} B:{rgb[2]}</td>
                <td>{detailed.get('brightness', 0)}</td>
                <td>{detailed.get('saturation', 0):.2f}</td>
            </tr>
"""
            
            html += """        </table>
        
        <h3>RGB Differences</h3>
        <table>
            <tr>
                <th>Comparison</th>
                <th>RGB Difference</th>
                <th>Euclidean Distance</th>
                <th>Same Color</th>
            </tr>
"""
            if 'rgb_differences' in system:
                for key, diff in system['rgb_differences'].items():
                    rgb_diff = diff['rgb_diff']
                    html += f"""
            <tr>
                <td>{key.replace('_', ' ')}</td>
                <td>ΔR:{rgb_diff[0]} ΔG:{rgb_diff[1]} ΔB:{rgb_diff[2]}</td>
                <td>{diff['euclidean_distance']:.1f}</td>
                <td>{'Yes' if diff['same_color'] else 'No'}</td>
            </tr>
"""
            
            html += """        </table>
        
        <h3>Quality Metrics</h3>
        <div class="metrics">
"""
            if 'quality_metrics' in system:
                for metric_name, metric_value in system['quality_metrics'].items():
                    display_name = metric_name.replace('_', ' ').title()
                    if isinstance(metric_value, float):
                        if 'consistency' in metric_name or 'score' in metric_name or 'purity' in metric_name:
                            display_value = f"{metric_value * 100:.1f}%"
                        else:
                            display_value = f"{metric_value:.2f}"
                    else:
                        display_value = str(metric_value)
                    
                    html += f"""
            <div class="metric">
                <div class="metric-label">{display_name}</div>
                <div class="metric-value">{display_value}</div>
            </div>
"""
            
            html += f"""
        </div>
        
        <h3>Analysis Charts</h3>
        <img src="{image_name}_system_{i+1}_analysis.png" alt="System {i+1} Analysis">
    </div>
"""
        
        html += """
</body>
</html>
"""
        return html
    
    def _generate_text_summary(self, image_path: str, papi_systems: List[Dict]) -> str:
        """Generate text summary of analysis"""
        summary = f"""
PAPI LIGHT ANALYSIS SUMMARY
============================
Image: {image_path}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Systems Detected: {len(papi_systems)}

"""
        
        if not papi_systems:
            summary += "No PAPI systems detected in the image.\n"
            return summary
        
        for i, system in enumerate(papi_systems):
            summary += f"""
SYSTEM {i+1}: {system.get('type', 'Unknown')}
---------------------------------
Confidence: {system.get('confidence', 0):.2%}
Status: {system.get('glide_status', 'Unknown')}
Pattern: {' - '.join(system.get('color_pattern', []))}

Light Details:
"""
            for light in system['lights']:
                rgb = light.get('rgb', (0, 0, 0))
                summary += f"  Light {light.get('light_number', 0)}: {light.get('color', 'UNKNOWN')} "
                summary += f"RGB({rgb[0]}, {rgb[1]}, {rgb[2]})\n"
            
            if 'quality_metrics' in system:
                summary += "\nQuality Metrics:\n"
                for metric, value in system['quality_metrics'].items():
                    if isinstance(value, float):
                        if 'consistency' in metric or 'score' in metric or 'purity' in metric:
                            summary += f"  {metric}: {value * 100:.1f}%\n"
                        else:
                            summary += f"  {metric}: {value:.2f}\n"
                    else:
                        summary += f"  {metric}: {value}\n"
            
            summary += "\n"
        
        return summary