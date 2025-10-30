"""
Pydantic schemas for light position data structure
"""
from typing import Dict, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class LightPosition(BaseModel):
    """
    Represents the position and dimensions of a single PAPI light in the video frame.
    All coordinates and sizes are expressed as percentages of the frame dimensions (0-100).
    """
    x: float = Field(..., ge=0, le=100, description="X coordinate as percentage of frame width (0-100)")
    y: float = Field(..., ge=0, le=100, description="Y coordinate as percentage of frame height (0-100)")
    size: float = Field(..., ge=0, le=100, description="Size (width) as percentage of frame width (0-100)")

    # Optional fields for more detailed dimensions
    width: Optional[float] = Field(None, ge=0, le=100, description="Width as percentage of frame width (0-100)")
    height: Optional[float] = Field(None, ge=0, le=100, description="Height as percentage of frame height (0-100)")

    # Optional confidence score from detection
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Detection confidence score (0-1)")

    @model_validator(mode='after')
    def ensure_width_height(self):
        """
        Ensure width and height are set. If they're not provided, derive them from size.
        This ensures backward compatibility with data that only has 'size'.
        """
        if self.width is None:
            self.width = self.size
        if self.height is None:
            # Assume square by default, or use width if available
            self.height = self.width
        return self

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary format for database storage"""
        result = {
            "x": self.x,
            "y": self.y,
            "size": self.size,
            "width": self.width,
            "height": self.height,
        }
        if self.confidence is not None:
            result["confidence"] = self.confidence
        return result


class LightPositions(BaseModel):
    """
    Container for all PAPI light positions in a measurement session.
    Keys are light names (e.g., "PAPI_A", "PAPI_B", "PAPI_C", "PAPI_D").
    """
    PAPI_A: Optional[LightPosition] = Field(None, description="Position of PAPI light A (leftmost)")
    PAPI_B: Optional[LightPosition] = Field(None, description="Position of PAPI light B")
    PAPI_C: Optional[LightPosition] = Field(None, description="Position of PAPI light C")
    PAPI_D: Optional[LightPosition] = Field(None, description="Position of PAPI light D (rightmost)")

    @classmethod
    def from_dict(cls, data: Dict[str, Dict[str, float]]) -> "LightPositions":
        """
        Create LightPositions from a raw dictionary.
        Handles various input formats and normalizes them.

        Args:
            data: Dictionary with light names as keys and position dicts as values

        Returns:
            LightPositions instance with validated data
        """
        positions = {}
        for light_name in ["PAPI_A", "PAPI_B", "PAPI_C", "PAPI_D"]:
            if light_name in data:
                positions[light_name] = LightPosition(**data[light_name])
        return cls(**positions)

    def to_dict(self) -> Dict[str, Dict[str, float]]:
        """
        Convert to dictionary format for database storage.
        Only includes lights that have been defined.

        Returns:
            Dictionary with light names as keys and position dicts as values
        """
        result = {}
        for light_name in ["PAPI_A", "PAPI_B", "PAPI_C", "PAPI_D"]:
            position = getattr(self, light_name)
            if position is not None:
                result[light_name] = position.to_dict()
        return result

    def __len__(self) -> int:
        """Return the number of defined light positions"""
        return sum(1 for light_name in ["PAPI_A", "PAPI_B", "PAPI_C", "PAPI_D"]
                   if getattr(self, light_name) is not None)


def validate_and_normalize_light_positions(data: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    """
    Validate and normalize light position data.

    This function:
    1. Validates the structure and values
    2. Ensures all required fields are present
    3. Fills in missing width/height from size
    4. Returns a normalized dictionary

    Args:
        data: Raw light positions dictionary

    Returns:
        Normalized and validated light positions dictionary

    Raises:
        ValidationError: If data is invalid
    """
    positions = LightPositions.from_dict(data)
    return positions.to_dict()
