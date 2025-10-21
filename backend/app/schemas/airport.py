from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.airport import ComplianceFramework


class AirportBase(BaseModel):
    icao_code: str = Field(..., min_length=4, max_length=4)
    iata_code: Optional[str] = Field(None, min_length=3, max_length=3)
    name: str
    full_name: Optional[str] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    elevation: Optional[float] = None
    timezone: str = "UTC"
    country: str
    city: Optional[str] = None
    operational_hours: Optional[Dict[str, Any]] = None
    runway_count: int = 0
    terminal_count: int = 0
    compliance_framework: ComplianceFramework = ComplianceFramework.ICAO
    settings: Optional[Dict[str, Any]] = None
    inspection_schedule: Optional[Dict[str, Any]] = None
    notification_settings: Optional[Dict[str, Any]] = None


class AirportCreate(AirportBase):
    pass


class AirportUpdate(BaseModel):
    name: Optional[str] = None
    full_name: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    elevation: Optional[float] = None
    timezone: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    operational_hours: Optional[Dict[str, Any]] = None
    runway_count: Optional[int] = None
    terminal_count: Optional[int] = None
    compliance_framework: Optional[ComplianceFramework] = None
    settings: Optional[Dict[str, Any]] = None
    inspection_schedule: Optional[Dict[str, Any]] = None
    notification_settings: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class AirportResponse(AirportBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class AirportListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    airports: List[AirportResponse]


class ItemTypeBase(BaseModel):
    name: str
    category: str
    subcategory: Optional[str] = None
    icao_reference: Optional[str] = None
    requirements: Optional[Dict[str, Any]] = None
    default_properties: Optional[Dict[str, Any]] = None
    inspection_frequency_days: int = 30
    inspection_procedures: Optional[Dict[str, Any]] = None
    icon: Optional[str] = None
    default_color: Optional[str] = None
    flight_template: Optional[Dict[str, Any]] = None


class ItemTypeCreate(ItemTypeBase):
    pass


class ItemTypeUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    icao_reference: Optional[str] = None
    requirements: Optional[Dict[str, Any]] = None
    default_properties: Optional[Dict[str, Any]] = None
    inspection_frequency_days: Optional[int] = None
    inspection_procedures: Optional[Dict[str, Any]] = None
    icon: Optional[str] = None
    default_color: Optional[str] = None
    flight_template: Optional[Dict[str, Any]] = None


class ItemTypeResponse(ItemTypeBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AirportItemBase(BaseModel):
    name: str
    code: Optional[str] = None
    serial_number: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    elevation: Optional[float] = None
    properties: Optional[Dict[str, Any]] = None
    specifications: Optional[Dict[str, Any]] = None
    status: str = "operational"
    installation_date: Optional[datetime] = None


class AirportItemCreate(AirportItemBase):
    airport_id: str
    item_type_id: str
    runway_id: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None  # GeoJSON geometry


class AirportItemUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    serial_number: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    elevation: Optional[float] = None
    geometry: Optional[Dict[str, Any]] = None
    properties: Optional[Dict[str, Any]] = None
    specifications: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    status: Optional[str] = None
    installation_date: Optional[datetime] = None
    last_maintenance_date: Optional[datetime] = None
    next_maintenance_date: Optional[datetime] = None


class AirportItemResponse(AirportItemBase):
    id: str
    airport_id: str
    item_type_id: str
    runway_id: Optional[str] = None
    geometry: Optional[Dict[str, Any]] = None
    is_active: bool
    compliance_status: str
    last_inspection_date: Optional[datetime] = None
    next_inspection_date: Optional[datetime] = None
    last_maintenance_date: Optional[datetime] = None
    next_maintenance_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class RunwayBase(BaseModel):
    name: str
    heading: float = Field(..., ge=0, le=360)
    length: float = Field(..., gt=0)
    width: float = Field(..., gt=0)
    surface_type: Optional[str] = None
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None


class RunwayCreate(RunwayBase):
    airport_id: str
    geometry: Optional[Dict[str, Any]] = None  # GeoJSON LineString
    boundary: Optional[Dict[str, Any]] = None  # GeoJSON Polygon


class RunwayUpdate(BaseModel):
    name: Optional[str] = None
    heading: Optional[float] = Field(None, ge=0, le=360)
    length: Optional[float] = Field(None, gt=0)
    width: Optional[float] = Field(None, gt=0)
    surface_type: Optional[str] = None
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    geometry: Optional[Dict[str, Any]] = None
    boundary: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class RunwayResponse(RunwayBase):
    id: str
    airport_id: str
    geometry: Optional[Dict[str, Any]] = None
    boundary: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # end_lat and end_lon are calculated properties in the model
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)