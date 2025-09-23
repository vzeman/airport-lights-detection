"""Configuration parameters for PAPI detection system"""

# Detection parameters
BRIGHTNESS_THRESHOLD = 200  # Minimum brightness to consider as light (0-255)
MIN_LIGHT_AREA = 10  # Minimum area in pixels for a light
MAX_LIGHT_AREA = 5000  # Maximum area in pixels for a light
PAPI_LIGHT_COUNT = 4  # Standard PAPI has 4 lights
APAPI_LIGHT_COUNT = 2  # Abbreviated PAPI has 2 lights

# Geometric constraints
HORIZONTAL_TOLERANCE = 50  # Maximum vertical deviation in pixels
SPACING_TOLERANCE = 0.3  # 30% tolerance in spacing between lights
MIN_ASPECT_RATIO = 2.0  # Minimum width/height ratio for PAPI group
MAX_ASPECT_RATIO = 10.0  # Maximum width/height ratio for PAPI group

# Color classification thresholds
RED_RATIO_THRESHOLD = 2.0  # R/G and R/B ratio for red classification
WHITE_BALANCE_THRESHOLD = 30  # Maximum difference between RGB channels for white
MIN_INTENSITY = 150  # Minimum intensity for valid light

# Analysis parameters
ROI_EXPANSION = 10  # Pixels to expand around detected light for analysis
GAUSSIAN_KERNEL_SIZE = 5  # Size of Gaussian blur kernel
MORPHOLOGICAL_KERNEL_SIZE = 3  # Size of morphological operations kernel

# Report parameters
REPORT_IMAGE_WIDTH = 800  # Width of images in report
VISUALIZATION_DPI = 100  # DPI for saved visualizations
HEATMAP_RESOLUTION = 50  # Resolution for RGB heatmap

# Processing modes
PROCESS_VIDEO = False  # Set to True for video processing
SAVE_INTERMEDIATE = False  # Save intermediate processing steps
DEBUG_MODE = False  # Enable debug visualizations