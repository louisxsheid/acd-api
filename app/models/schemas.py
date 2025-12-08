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


# Cell models (now includes provider attribution)
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
    provider_id: Optional[int] = None  # Which provider reported this cell


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
    provider_id: Optional[int] = None  # Which provider reported this cell

    class Config:
        from_attributes = True


class CellWithProvider(Cell):
    """Cell with full provider details"""
    provider: Optional[Provider] = None


# Tower Band models (now includes provider attribution)
class TowerBandBase(BaseModel):
    band_number: int
    band_name: Optional[str] = None
    channel: Optional[int] = None
    bandwidth: Optional[int] = None
    modulation: Optional[str] = None


class TowerBandCreate(TowerBandBase):
    tower_id: int
    provider_id: Optional[int] = None  # Which provider reported this band


class TowerBandUpdate(BaseModel):
    band_name: Optional[str] = None
    channel: Optional[int] = None
    bandwidth: Optional[int] = None
    modulation: Optional[str] = None


class TowerBand(TowerBandBase):
    id: int
    tower_id: int
    provider_id: Optional[int] = None  # Which provider reported this band

    class Config:
        from_attributes = True


class TowerBandWithProvider(TowerBand):
    """Tower band with full provider details"""
    provider: Optional[Provider] = None


# Tower-Provider junction model
# Links towers to providers with provider-specific metadata
class TowerProviderBase(BaseModel):
    external_id: Optional[str] = None  # Original MongoDB _id
    rat: Optional[str] = None  # LTE, NR, GSM, CDMA, UMTS
    rat_subtype: Optional[str] = None
    site_id: Optional[str] = None
    region_id: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    tower_mover: Optional[int] = None
    has_bandwidth_data: bool = False
    has_frequency_data: bool = False
    endc_available: bool = False
    visible: bool = True


class TowerProviderCreate(TowerProviderBase):
    tower_id: int
    provider_id: int


class TowerProviderUpdate(BaseModel):
    external_id: Optional[str] = None
    rat: Optional[str] = None
    rat_subtype: Optional[str] = None
    site_id: Optional[str] = None
    region_id: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    tower_mover: Optional[int] = None
    has_bandwidth_data: Optional[bool] = None
    has_frequency_data: Optional[bool] = None
    endc_available: Optional[bool] = None
    visible: Optional[bool] = None


class TowerProvider(TowerProviderBase):
    id: int
    tower_id: int
    provider_id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TowerProviderWithDetails(TowerProvider):
    """Tower-provider link with full provider details"""
    provider: Optional[Provider] = None


# Tower models (now provider-agnostic, representing physical locations)
class TowerBase(BaseModel):
    location_hash: Optional[str] = None  # Hash of lat/lng for dedup
    latitude: float
    longitude: float
    tower_type: Optional[str] = None  # MACRO, MICRO, PICO, DAS, COW, DECOMMISSIONED
    first_seen_at: Optional[datetime] = None  # Earliest across all providers
    last_seen_at: Optional[datetime] = None  # Latest across all providers
    generator: Optional[str] = None
    generator_time: Optional[int] = None
    tower_mover_id: Optional[str] = None
    contributors: Optional[list[int]] = None  # All contributors merged
    has_bandwidth_data: bool = False
    has_frequency_data: bool = False
    endc_available: bool = False  # True if ANY provider reports EN-DC
    provider_count: int = 1  # Number of providers at this location
    visible: bool = True


class TowerCreate(TowerBase):
    pass


class TowerUpdate(BaseModel):
    location_hash: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    tower_type: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    generator: Optional[str] = None
    generator_time: Optional[int] = None
    tower_mover_id: Optional[str] = None
    contributors: Optional[list[int]] = None
    has_bandwidth_data: Optional[bool] = None
    has_frequency_data: Optional[bool] = None
    endc_available: Optional[bool] = None
    provider_count: Optional[int] = None
    visible: Optional[bool] = None


class Tower(TowerBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TowerWithProviders(Tower):
    """Tower with all its provider relationships"""
    tower_providers: list[TowerProviderWithDetails] = []


class TowerWithRelations(Tower):
    """Tower with all related data: providers, cells, and bands"""
    tower_providers: list[TowerProviderWithDetails] = []
    cells: list[CellWithProvider] = []
    tower_bands: list[TowerBandWithProvider] = []


# Backward compatibility: Tower view that looks like old format
# (for queries expecting single provider per tower)
class TowerExpanded(BaseModel):
    """
    Expanded tower view - one row per tower-provider combination.
    Mimics the old schema where each tower had a single provider.
    """
    tower_id: int
    tower_provider_id: int
    external_id: Optional[str] = None
    provider_id: int
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
    created_at: Optional[datetime] = None
    provider: Optional[Provider] = None

    class Config:
        from_attributes = True


# Geospatial query models
class TowersNearbyRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_meters: float = Field(default=1000, ge=1, le=100000)
    limit: int = Field(default=100, ge=1, le=1000)
    rat: Optional[str] = None
    tower_type: Optional[str] = None


# Summary/stats models
class TowerProviderSummary(BaseModel):
    """Summary of a provider's presence at a tower"""
    provider: Provider
    rat: Optional[str] = None
    cell_count: int = 0
    band_count: int = 0
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    endc_available: bool = False


class TowerSummary(BaseModel):
    """Summary view of a tower with aggregated provider info"""
    id: int
    latitude: float
    longitude: float
    tower_type: Optional[str] = None
    provider_count: int = 1
    providers: list[TowerProviderSummary] = []
    total_cells: int = 0
    total_bands: int = 0
    rats: list[str] = []  # All RAT types at this tower
    endc_available: bool = False
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None


# Dashboard metrics models
class BandDistributionEntry(BaseModel):
    """Single entry in band distribution: how many towers have X bands"""
    band_count: int
    tower_count: int


class ProviderBandDistribution(BaseModel):
    """Band distribution for a specific provider"""
    provider_id: int
    provider_name: Optional[str] = None
    distribution: list[BandDistributionEntry] = []
    total_towers: int = 0
    endc_towers: int = 0
    non_endc_towers: int = 0


class BandDistributionMetric(BaseModel):
    """
    Dashboard metric showing how many towers have how many bands,
    grouped by provider and EN-DC status.
    """
    by_provider: list[ProviderBandDistribution] = []
    overall: list[BandDistributionEntry] = []
    total_towers: int = 0
    endc_summary: dict[str, int] = {}  # {"endc_enabled": X, "endc_disabled": Y}
