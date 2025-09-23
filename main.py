"""Main application for PAPI light detection and analysis"""

import os
import sys
import argparse
import cv2
from datetime import datetime
from papi_detector import PAPIDetector
from rgb_analyzer import RGBAnalyzer
from report_generator import ReportGenerator
import config

def process_image(image_path: str, threshold: int = config.BRIGHTNESS_THRESHOLD, 
                 output_dir: str = "reports") -> bool:
    """
    Process a single image for PAPI detection and analysis
    
    Args:
        image_path: Path to the image file
        threshold: Brightness threshold for detection
        output_dir: Directory for output reports
        
    Returns:
        Success status
    """
    print(f"\n{'='*60}")
    print(f"Processing: {os.path.basename(image_path)}")
    print(f"{'='*60}")
    
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image {image_path}")
        return False
    
    print(f"Image dimensions: {image.shape[1]}x{image.shape[0]}")
    
    # Initialize modules
    detector = PAPIDetector(threshold=threshold)
    analyzer = RGBAnalyzer()
    generator = ReportGenerator(output_dir=output_dir)
    
    # Detect PAPI systems
    print("\nDetecting PAPI systems...")
    papi_systems = detector.detect_papi_systems(image)
    
    if not papi_systems:
        print("No PAPI systems detected in the image")
        return False
    
    print(f"Detected {len(papi_systems)} PAPI system(s)")
    
    # Analyze each system
    print("\nAnalyzing RGB values...")
    for i, system in enumerate(papi_systems):
        print(f"\nSystem {i+1}: {system['type']}")
        
        # Perform RGB analysis
        system = analyzer.analyze_papi_system(system, image)
        
        # Print light details
        for light in system['lights']:
            rgb = light.get('rgb', (0, 0, 0))
            color = light.get('color', 'UNKNOWN')
            print(f"  Light {light['light_number']}: {color} - RGB({rgb[0]}, {rgb[1]}, {rgb[2]})")
        
        # Print status
        print(f"  Status: {system.get('glide_status', 'Unknown')}")
        print(f"  Confidence: {system.get('confidence', 0):.2%}")
        
        # Print RGB differences
        if 'rgb_differences' in system:
            print("\n  RGB Differences:")
            for comparison, diff in system['rgb_differences'].items():
                print(f"    {comparison}: Euclidean distance = {diff['euclidean_distance']:.1f}")
        
        # Print quality metrics
        if 'quality_metrics' in system:
            print("\n  Quality Metrics:")
            for metric, value in system['quality_metrics'].items():
                if isinstance(value, float):
                    if 'consistency' in metric or 'score' in metric or 'purity' in metric:
                        print(f"    {metric}: {value * 100:.1f}%")
                    else:
                        print(f"    {metric}: {value:.2f}")
                else:
                    print(f"    {metric}: {value}")
    
    # Generate report
    print("\nGenerating report...")
    report_path = generator.generate_report(image_path, papi_systems, image)
    
    return True

def process_folder(folder_path: str, threshold: int = config.BRIGHTNESS_THRESHOLD,
                  output_dir: str = "reports") -> None:
    """
    Process all images in a folder
    
    Args:
        folder_path: Path to the folder containing images
        threshold: Brightness threshold for detection
        output_dir: Directory for output reports
    """
    # Supported image extensions
    extensions = ['.jpg', '.jpeg', '.png', '.webp', '.bmp']
    
    # Find all image files
    image_files = []
    for file in os.listdir(folder_path):
        if any(file.lower().endswith(ext) for ext in extensions):
            image_files.append(os.path.join(folder_path, file))
    
    if not image_files:
        print(f"No image files found in {folder_path}")
        return
    
    print(f"\nFound {len(image_files)} image(s) to process")
    
    # Process each image
    success_count = 0
    for image_path in sorted(image_files):
        try:
            if process_image(image_path, threshold, output_dir):
                success_count += 1
        except Exception as e:
            print(f"Error processing {image_path}: {str(e)}")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Processing complete!")
    print(f"Successfully processed {success_count}/{len(image_files)} images")
    print(f"Reports saved to: {output_dir}/")
    print(f"{'='*60}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='PAPI Light Detection and Analysis System')
    parser.add_argument('--image', type=str, help='Path to a single image file')
    parser.add_argument('--folder', type=str, default='images', help='Path to folder containing images')
    parser.add_argument('--threshold', type=int, default=config.BRIGHTNESS_THRESHOLD, 
                       help='Brightness threshold for light detection (0-255)')
    parser.add_argument('--output', type=str, default='reports', help='Output directory for reports')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Set debug mode
    if args.debug:
        config.DEBUG_MODE = True
    
    # Print header
    print("\n" + "="*60)
    print("     PAPI LIGHT DETECTION AND QUALITY ASSESSMENT SYSTEM")
    print("="*60)
    print(f"Version: 1.0")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Process based on input
    if args.image:
        # Process single image
        if not os.path.exists(args.image):
            print(f"Error: Image file not found: {args.image}")
            sys.exit(1)
        process_image(args.image, args.threshold, args.output)
    else:
        # Process folder
        if not os.path.exists(args.folder):
            print(f"Error: Folder not found: {args.folder}")
            sys.exit(1)
        process_folder(args.folder, args.threshold, args.output)

if __name__ == "__main__":
    main()