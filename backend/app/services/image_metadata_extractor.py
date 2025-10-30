"""
Service for extracting metadata from drone images.
Supports EXIF and XMP data extraction with high precision GPS coordinates.
"""

import exifread
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal, getcontext
from PIL import Image
from io import BytesIO
import xml.etree.ElementTree as ET

# Set high precision for decimal calculations
getcontext().prec = 50


class ImageMetadataExtractor:
    """Extract and parse metadata from drone images."""

    @staticmethod
    def _convert_to_degrees(value) -> Optional[Decimal]:
        """
        Convert GPS coordinates to decimal degrees with high precision.

        Args:
            value: EXIF GPS coordinate value (ratio format)

        Returns:
            Decimal degree value with high precision
        """
        try:
            d = Decimal(value.values[0].num) / Decimal(value.values[0].den)
            m = Decimal(value.values[1].num) / Decimal(value.values[1].den)
            s = Decimal(value.values[2].num) / Decimal(value.values[2].den)

            return d + (m / Decimal('60')) + (s / Decimal('3600'))
        except (AttributeError, IndexError, ZeroDivisionError):
            return None

    @staticmethod
    def _format_dms(decimal_degree: Decimal, is_latitude: bool) -> str:
        """
        Convert decimal degrees to DMS (Degrees, Minutes, Seconds) format.

        Args:
            decimal_degree: Decimal degree value
            is_latitude: True for latitude, False for longitude

        Returns:
            Formatted DMS string (e.g., "48° 7' 24.4444\" N")
        """
        abs_dd = abs(decimal_degree)
        degrees = int(abs_dd)
        minutes_decimal = (abs_dd - degrees) * 60
        minutes = int(minutes_decimal)
        seconds = (minutes_decimal - minutes) * 60

        # Determine direction
        if is_latitude:
            direction = 'N' if decimal_degree >= 0 else 'S'
        else:
            direction = 'E' if decimal_degree >= 0 else 'W'

        return f"{degrees}° {minutes}' {seconds:.4f}\" {direction}"

    @staticmethod
    def parse_gps_data(tags: Dict) -> Optional[Dict[str, Any]]:
        """
        Extract and parse GPS data from EXIF tags with high precision.

        Args:
            tags: Dictionary of EXIF tags

        Returns:
            Dictionary containing GPS data in multiple formats
        """
        gps_latitude = tags.get('GPS GPSLatitude')
        gps_latitude_ref = tags.get('GPS GPSLatitudeRef')
        gps_longitude = tags.get('GPS GPSLongitude')
        gps_longitude_ref = tags.get('GPS GPSLongitudeRef')
        gps_altitude = tags.get('GPS GPSAltitude')
        gps_altitude_ref = tags.get('GPS GPSAltitudeRef')

        if not (gps_latitude and gps_longitude):
            return None

        # Convert to decimal degrees
        lat_decimal = ImageMetadataExtractor._convert_to_degrees(gps_latitude)
        lon_decimal = ImageMetadataExtractor._convert_to_degrees(gps_longitude)

        if lat_decimal is None or lon_decimal is None:
            return None

        # Apply reference (N/S, E/W)
        if gps_latitude_ref and str(gps_latitude_ref) == 'S':
            lat_decimal = -lat_decimal
        if gps_longitude_ref and str(gps_longitude_ref) == 'W':
            lon_decimal = -lon_decimal

        # Parse altitude
        altitude_meters = None
        altitude_feet = None
        if gps_altitude:
            try:
                alt_value = Decimal(gps_altitude.values[0].num) / Decimal(gps_altitude.values[0].den)
                altitude_meters = alt_value
                altitude_feet = alt_value * Decimal('3.28084')
            except (AttributeError, ZeroDivisionError):
                pass

        altitude_ref = "Above Sea Level"
        if gps_altitude_ref and str(gps_altitude_ref) == '1':
            altitude_ref = "Below Sea Level"

        # Round coordinates to 9 decimal places for display
        lat_rounded = round(float(lat_decimal), 9)
        lon_rounded = round(float(lon_decimal), 9)

        return {
            "latitude": {
                "decimal": str(lat_rounded),
                "dms": ImageMetadataExtractor._format_dms(lat_decimal, True),
                "raw": str(lat_rounded)
            },
            "longitude": {
                "decimal": str(lon_rounded),
                "dms": ImageMetadataExtractor._format_dms(lon_decimal, False),
                "raw": str(lon_rounded)
            },
            "altitude": {
                "meters": str(altitude_meters) if altitude_meters else None,
                "feet": str(altitude_feet) if altitude_feet else None,
                "raw": str(altitude_meters) if altitude_meters else None
            } if altitude_meters else None,
            "altitude_ref": altitude_ref
        }

    @staticmethod
    def extract_camera_metadata(tags: Dict) -> Dict[str, Any]:
        """Extract camera-related metadata."""
        return {
            "make": str(tags.get('Image Make', '')).strip(),
            "model": str(tags.get('Image Model', '')).strip(),
            "lens_model": str(tags.get('EXIF LensModel', '')).strip(),
            "iso": str(tags.get('EXIF ISOSpeedRatings', '')),
            "shutter_speed": str(tags.get('EXIF ExposureTime', '')),
            "aperture": str(tags.get('EXIF FNumber', '')),
            "focal_length": str(tags.get('EXIF FocalLength', '')),
            "white_balance": str(tags.get('EXIF WhiteBalance', '')),
            "exposure_mode": str(tags.get('EXIF ExposureMode', '')),
            "exposure_program": str(tags.get('EXIF ExposureProgram', '')),
            "metering_mode": str(tags.get('EXIF MeteringMode', '')),
        }

    @staticmethod
    def extract_capture_metadata(tags: Dict, image_size: Tuple[int, int]) -> Dict[str, Any]:
        """Extract capture information."""
        return {
            "datetime_original": str(tags.get('EXIF DateTimeOriginal', '')),
            "datetime_digitized": str(tags.get('EXIF DateTimeDigitized', '')),
            "width": image_size[0],
            "height": image_size[1],
            "orientation": str(tags.get('Image Orientation', '1')),
            "software": str(tags.get('Image Software', '')).strip(),
        }

    @staticmethod
    def extract_drone_metadata(tags: Dict) -> Dict[str, Any]:
        """
        Extract drone-specific metadata (primarily from DJI drones).
        DJI stores additional data in XMP format.
        """
        drone_data = {
            "model": str(tags.get('Image Model', '')).strip(),
            "make": str(tags.get('Image Make', '')).strip(),
        }

        # Try to extract XMP data from UserComment or XMP tag
        user_comment = tags.get('EXIF UserComment')
        if user_comment:
            try:
                # DJI stores XMP in UserComment
                xmp_str = str(user_comment)
                if '<x:xmpmeta' in xmp_str or 'drone-dji:' in xmp_str:
                    # Parse XMP data
                    drone_data.update(ImageMetadataExtractor._parse_dji_xmp(xmp_str))
            except Exception:
                pass

        return drone_data

    @staticmethod
    def _parse_dji_xmp(xmp_str: str) -> Dict[str, Any]:
        """Parse DJI-specific XMP metadata."""
        dji_data = {}

        # Common DJI XMP fields
        xmp_fields = {
            'GimbalPitchDegree': 'gimbal_pitch',
            'GimbalRollDegree': 'gimbal_roll',
            'GimbalYawDegree': 'gimbal_yaw',
            'FlightPitchDegree': 'flight_pitch',
            'FlightRollDegree': 'flight_roll',
            'FlightYawDegree': 'flight_yaw',
            'FlightXSpeed': 'flight_x_speed',
            'FlightYSpeed': 'flight_y_speed',
            'FlightZSpeed': 'flight_z_speed',
            'RelativeAltitude': 'relative_altitude',
            'AbsoluteAltitude': 'absolute_altitude',
        }

        for xmp_field, key in xmp_fields.items():
            # Simple regex-like extraction
            search_str = f'drone-dji:{xmp_field}="'
            if search_str in xmp_str:
                start_idx = xmp_str.find(search_str) + len(search_str)
                end_idx = xmp_str.find('"', start_idx)
                if end_idx > start_idx:
                    dji_data[key] = xmp_str[start_idx:end_idx]

        return dji_data

    @classmethod
    def extract_all_metadata(cls, image_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Extract all metadata from an image file.

        Args:
            image_bytes: Raw image file bytes
            filename: Original filename

        Returns:
            Dictionary containing all extracted metadata
        """
        processing_errors = []

        try:
            # Extract EXIF data
            tags = exifread.process_file(BytesIO(image_bytes), details=True)

            # Get image size using Pillow
            try:
                image = Image.open(BytesIO(image_bytes))
                image_size = image.size
                file_size_mb = round(len(image_bytes) / (1024 * 1024), 2)
            except Exception as e:
                processing_errors.append(f"Could not read image dimensions: {str(e)}")
                image_size = (0, 0)
                file_size_mb = 0

            # Extract GPS data
            gps_data = cls.parse_gps_data(tags)
            if not gps_data:
                processing_errors.append("No GPS data found in image")

            # Extract other metadata
            camera_metadata = cls.extract_camera_metadata(tags)
            capture_metadata = cls.extract_capture_metadata(tags, image_size)
            drone_metadata = cls.extract_drone_metadata(tags)

            # Prepare all tags for display
            all_tags = {str(key): str(value) for key, value in tags.items()}

            return {
                "filename": filename,
                "file_size_mb": file_size_mb,
                "gps_data": gps_data,
                "drone_metadata": drone_metadata,
                "camera_metadata": camera_metadata,
                "capture_metadata": capture_metadata,
                "all_tags": all_tags,
                "processing_errors": processing_errors
            }

        except Exception as e:
            return {
                "filename": filename,
                "file_size_mb": round(len(image_bytes) / (1024 * 1024), 2),
                "gps_data": None,
                "drone_metadata": {},
                "camera_metadata": {},
                "capture_metadata": {},
                "all_tags": {},
                "processing_errors": [f"Failed to process image: {str(e)}"]
            }
