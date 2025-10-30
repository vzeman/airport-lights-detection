"""
Pydantic schemas for frame measurements
These schemas ensure robust JSON serialization/deserialization with default values
"""
from typing import Optional, Dict, Any
import sys
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


class LightStatus(str, Enum):
    """PAPI light status enumeration"""
    NOT_VISIBLE = "NOT_VISIBLE"
    RED = "RED"
    WHITE = "WHITE"
    TRANSITION = "TRANSITION"


class PAPILightData(BaseModel):
    """Data for a single PAPI light"""
    status: Optional[LightStatus] = Field(default=None, description="Light status")
    rgb: Optional[Dict[str, int]] = Field(default=None, description="RGB color values")
    intensity: Optional[float] = Field(default=None, description="Light intensity")
    angle: Optional[float] = Field(default=None, description="Vertical angle from ground")
    horizontal_angle: Optional[float] = Field(default=None, description="Horizontal angle from runway centerline")
    distance_ground: Optional[float] = Field(default=None, description="Distance on ground")
    distance_direct: Optional[float] = Field(default=None, description="Direct distance to drone")
    area_pixels: Optional[int] = Field(default=0, description="Area of lit region in pixels² (≥ 15% intensity)")

    class Config:
        use_enum_values = True

    @field_validator('status', mode='before')
    @classmethod
    def validate_status(cls, v):
        """Convert status to uppercase to match enum (case-insensitive)"""
        if v and isinstance(v, str):
            return v.upper()
        return v


class FrameMeasurementData(BaseModel):
    """Complete frame measurement data structure"""
    # Frame identification
    frame_number: int = Field(..., description="Frame sequence number")
    timestamp: float = Field(..., description="Time offset in video (seconds)")

    # Drone position and orientation
    drone_latitude: float = Field(..., description="Drone GPS latitude")
    drone_longitude: float = Field(..., description="Drone GPS longitude")
    drone_elevation: float = Field(..., description="Drone elevation/altitude")
    gimbal_pitch: Optional[float] = Field(default=None, description="Camera gimbal pitch angle")
    gimbal_roll: Optional[float] = Field(default=None, description="Camera gimbal roll angle")
    gimbal_yaw: Optional[float] = Field(default=None, description="Camera gimbal yaw angle")

    # PAPI lights data
    papi_a: Optional[PAPILightData] = Field(default=None, description="PAPI A light data")
    papi_b: Optional[PAPILightData] = Field(default=None, description="PAPI B light data")
    papi_c: Optional[PAPILightData] = Field(default=None, description="PAPI C light data")
    papi_d: Optional[PAPILightData] = Field(default=None, description="PAPI D light data")

    class Config:
        json_schema_extra = {
            "example": {
                "frame_number": 100,
                "timestamp": 3.33,
                "drone_latitude": 48.12345678,
                "drone_longitude": 17.98765432,
                "drone_elevation": 50.5,
                "gimbal_pitch": -15.0,
                "gimbal_roll": 0.5,
                "gimbal_yaw": 90.0,
                "papi_a": {
                    "status": "RED",
                    "rgb": {"r": 255, "g": 0, "b": 0},
                    "intensity": 0.85,
                    "angle": 2.5,
                    "horizontal_angle": 0.3,
                    "distance_ground": 100.5,
                    "distance_direct": 102.3
                }
            }
        }


def convert_flat_dict_to_nested(flat_dict: dict) -> dict:
    """
    Convert flat dictionary structure to nested format for JSON storage

    Converts:
        {papi_a_status: "red", papi_a_angle: 2.76, ...}
    To:
        {papi_a: {status: "red", angle: 2.76}, ...}

    Args:
        flat_dict: Dictionary with flat field names (papi_a_status, papi_a_angle, etc.)

    Returns:
        Dictionary with nested PAPI data structure
    """
    # Start with basic fields
    data = {
        "frame_number": flat_dict.get("frame_number"),
        "timestamp": flat_dict.get("timestamp"),
        "drone_latitude": flat_dict.get("drone_latitude"),
        "drone_longitude": flat_dict.get("drone_longitude"),
        "drone_elevation": flat_dict.get("drone_elevation"),
        "gimbal_pitch": flat_dict.get("gimbal_pitch"),
        "gimbal_roll": flat_dict.get("gimbal_roll"),
        "gimbal_yaw": flat_dict.get("gimbal_yaw"),
    }

    # Convert each PAPI light from flat to nested
    for papi_name in ["papi_a", "papi_b", "papi_c", "papi_d"]:
        status_key = f"{papi_name}_status"
        if status_key in flat_dict and flat_dict[status_key]:
            data[papi_name] = {
                "status": flat_dict[status_key],
                "rgb": flat_dict.get(f"{papi_name}_rgb"),
                "intensity": flat_dict.get(f"{papi_name}_intensity"),
                "angle": flat_dict.get(f"{papi_name}_angle"),
                "horizontal_angle": flat_dict.get(f"{papi_name}_horizontal_angle"),
                "distance_ground": flat_dict.get(f"{papi_name}_distance_ground"),
                "distance_direct": flat_dict.get(f"{papi_name}_distance_direct"),
                "area_pixels": flat_dict.get(f"{papi_name}_area_pixels")
            }

    return data


def parse_frame_measurements(json_data: list) -> list[FrameMeasurementData]:
    """
    Parse frame measurements from JSON with robust error handling

    Args:
        json_data: List of dictionaries from JSON

    Returns:
        List of validated FrameMeasurementData objects

    Note:
        This function handles missing attributes gracefully using Pydantic defaults
    """
    validated_measurements = []

    for i, item in enumerate(json_data):
        try:
            # Pydantic will handle missing fields with defaults
            measurement = FrameMeasurementData(**item)
            validated_measurements.append(measurement)
        except Exception as e:
            # Log warning but continue processing
            import logging
            logger = logging.getLogger(__name__)
            sys.stderr.write(f"[WARNING] Failed to parse frame measurement {i}: {e}. Skipping this frame.\n"); sys.stderr.flush()
            continue

    return validated_measurements
