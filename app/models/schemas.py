from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


# Provider models
class ProviderBase(BaseModel):
    country_id: int
    provider_id: int
    name: Optional[str] = None
    visible: bool = True


class ProviderCreate(ProviderBase):
    pass


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    visible: Optional[bool] = None


class Provider(ProviderBase):
    id: int

    class Config:
        from_attributes = True


# Cell models
class CellBase(BaseModel):
    cell_id: str
    pci: Optional[int] = None
    sector: Optional[int] = None
    bearing: Optional[int] = None
    bandwidth: Optional[int] = None
    signal: Optional[int] = None
    subsystem: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    lte_snr_max: Optional[Decimal] = None
    lte_rsrq_max: Optional[Decimal] = None
    max_speed_down_mbps: Optional[Decimal] = None
    avg_speed_down_mbps: Optional[Decimal] = None
    max_speed_up_mbps: Optional[Decimal] = None
    avg_speed_up_mbps: Optional[Decimal] = None
    endc_available: bool = False


class CellCreate(CellBase):
    tower_id: int


class CellUpdate(BaseModel):
    pci: Optional[int] = None
    sector: Optional[int] = None
    bearing: Optional[int] = None
    bandwidth: Optional[int] = None
    signal: Optional[int] = None
    subsystem: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    lte_snr_max: Optional[Decimal] = None
    lte_rsrq_max: Optional[Decimal] = None
    max_speed_down_mbps: Optional[Decimal] = None
    avg_speed_down_mbps: Optional[Decimal] = None
    max_speed_up_mbps: Optional[Decimal] = None
    avg_speed_up_mbps: Optional[Decimal] = None
    endc_available: Optional[bool] = None


class Cell(CellBase):
    id: int
    tower_id: int

    class Config:
        from_attributes = True


# Tower Band models
class TowerBandBase(BaseModel):
    band_number: int
    band_name: Optional[str] = None
    channel: Optional[int] = None
    bandwidth: Optional[int] = None
    modulation: Optional[str] = None


class TowerBandCreate(TowerBandBase):
    tower_id: int


class TowerBandUpdate(BaseModel):
    band_name: Optional[str] = None
    channel: Optional[int] = None
    bandwidth: Optional[int] = None
    modulation: Optional[str] = None


class TowerBand(TowerBandBase):
    id: int
    tower_id: int

    class Config:
        from_attributes = True


# Tower models
class TowerBase(BaseModel):
    external_id: Optional[str] = None
    provider_id: Optional[int] = None
    rat: Optional[str] = None
    rat_subtype: Optional[str] = None
    tower_type: Optional[str] = None
    site_id: Optional[str] = None
    region_id: Optional[str] = None
    latitude: float
    longitude: float
    visible: bool = True
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    tower_mover: Optional[int] = None
    tower_mover_id: Optional[str] = None
    generator: Optional[str] = None
    generator_time: Optional[int] = None
    has_bandwidth_data: bool = False
    has_frequency_data: bool = False
    endc_available: bool = False
    contributors: Optional[list[int]] = None
    raw_channels: Optional[dict] = None
    raw_bandwidths: Optional[dict] = None
    raw_band_numbers: Optional[dict] = None


class TowerCreate(TowerBase):
    pass


class TowerUpdate(BaseModel):
    external_id: Optional[str] = None
    provider_id: Optional[int] = None
    rat: Optional[str] = None
    rat_subtype: Optional[str] = None
    tower_type: Optional[str] = None
    site_id: Optional[str] = None
    region_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    visible: Optional[bool] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    tower_mover: Optional[int] = None
    tower_mover_id: Optional[str] = None
    generator: Optional[str] = None
    generator_time: Optional[int] = None
    has_bandwidth_data: Optional[bool] = None
    has_frequency_data: Optional[bool] = None
    endc_available: Optional[bool] = None
    contributors: Optional[list[int]] = None
    raw_channels: Optional[dict] = None
    raw_bandwidths: Optional[dict] = None
    raw_band_numbers: Optional[dict] = None


class Tower(TowerBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TowerWithRelations(Tower):
    cells: list[Cell] = []
    tower_bands: list[TowerBand] = []
    provider: Optional[Provider] = None


# Geospatial query models
class TowersNearbyRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_meters: float = Field(default=1000, ge=1, le=100000)
    limit: int = Field(default=100, ge=1, le=1000)
    rat: Optional[str] = None
    tower_type: Optional[str] = None
