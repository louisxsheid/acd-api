from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import (
    Tower,
    TowerCreate,
    TowerUpdate,
    TowerWithRelations,
    TowerWithProviders,
    TowerProviderWithDetails,
    TowerExpanded,
    TowersNearbyRequest,
    PaginationParams,
)
from app.services import HasuraClient, get_hasura_client

router = APIRouter(prefix="/towers", tags=["towers"])

# Tower fields (new schema - provider-agnostic location)
TOWER_FIELDS = """
    id
    location_hash
    latitude
    longitude
    tower_type
    first_seen_at
    last_seen_at
    generator
    generator_time
    tower_mover_id
    contributors
    has_bandwidth_data
    has_frequency_data
    endc_available
    provider_count
    visible
    created_at
"""

# Provider fields for nested queries
PROVIDER_FIELDS = """
    id
    country_id
    provider_id
    name
    visible
"""

# Tower-Provider junction fields
TOWER_PROVIDER_FIELDS = """
    id
    tower_id
    provider_id
    external_id
    rat
    rat_subtype
    site_id
    region_id
    first_seen_at
    last_seen_at
    tower_mover
    has_bandwidth_data
    has_frequency_data
    endc_available
    visible
    created_at
"""

# Cell fields (now with provider attribution)
CELL_FIELDS = """
    id
    tower_id
    provider_id
    cell_id
    pci
    sector
    bearing
    bandwidth
    signal
    subsystem
    first_seen_at
    last_seen_at
    lte_snr_max
    lte_rsrq_max
    max_speed_down_mbps
    avg_speed_down_mbps
    max_speed_up_mbps
    avg_speed_up_mbps
    endc_available
"""

# Tower band fields (now with provider attribution)
TOWER_BAND_FIELDS = """
    id
    tower_id
    provider_id
    band_number
    band_name
    channel
    bandwidth
    modulation
"""

# Tower with all providers
TOWER_WITH_PROVIDERS = f"""
    {TOWER_FIELDS}
    tower_providers {{
        {TOWER_PROVIDER_FIELDS}
        provider {{
            {PROVIDER_FIELDS}
        }}
    }}
"""

# Full tower with all relations
TOWER_WITH_RELATIONS_QUERY = f"""
    {TOWER_FIELDS}
    tower_providers {{
        {TOWER_PROVIDER_FIELDS}
        provider {{
            {PROVIDER_FIELDS}
        }}
    }}
    cells {{
        {CELL_FIELDS}
        provider {{
            {PROVIDER_FIELDS}
        }}
    }}
    tower_bands {{
        {TOWER_BAND_FIELDS}
        provider {{
            {PROVIDER_FIELDS}
        }}
    }}
"""


@router.get("", response_model=list[Tower])
async def list_towers(
    pagination: PaginationParams = Depends(),
    tower_type: Optional[str] = Query(None, description="Filter by tower type"),
    provider_id: Optional[int] = Query(None, description="Filter by provider ID (towers with this provider)"),
    rat: Optional[str] = Query(None, description="Filter by RAT type (via tower_providers)"),
    visible: Optional[bool] = Query(None, description="Filter by visibility"),
    multi_provider: Optional[bool] = Query(None, description="Filter to towers with multiple providers"),
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    List towers (physical locations).
    Use provider_id or rat filters to find towers that have a specific provider or RAT.
    """
    where_clauses = []
    variables: dict = {"limit": pagination.limit, "offset": pagination.offset}

    if tower_type:
        where_clauses.append("tower_type: {_eq: $tower_type}")
        variables["tower_type"] = tower_type
    if visible is not None:
        where_clauses.append("visible: {_eq: $visible}")
        variables["visible"] = visible
    if multi_provider is True:
        where_clauses.append("provider_count: {_gt: 1}")
    elif multi_provider is False:
        where_clauses.append("provider_count: {_eq: 1}")

    # Filter by provider or RAT requires joining to tower_providers
    if provider_id:
        where_clauses.append("tower_providers: {provider_id: {_eq: $provider_id}}")
        variables["provider_id"] = provider_id
    if rat:
        where_clauses.append("tower_providers: {rat: {_eq: $rat}}")
        variables["rat"] = rat

    where = ", ".join(where_clauses) if where_clauses else ""
    where_clause = f"where: {{{where}}}, " if where else ""

    var_defs = ["$limit: Int!", "$offset: Int!"]
    if tower_type:
        var_defs.append("$tower_type: String!")
    if visible is not None:
        var_defs.append("$visible: Boolean!")
    if provider_id:
        var_defs.append("$provider_id: Int!")
    if rat:
        var_defs.append("$rat: String!")

    query = f"""
    query ListTowers({", ".join(var_defs)}) {{
        towers({where_clause}limit: $limit, offset: $offset, order_by: {{id: asc}}) {{
            {TOWER_FIELDS}
        }}
    }}
    """
    data = await hasura.execute(query, variables)
    return data.get("towers", [])


@router.get("/nearby", response_model=list[TowerWithProviders])
async def get_towers_nearby(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_meters: float = Query(1000, ge=1, le=100000),
    limit: int = Query(100, ge=1, le=1000),
    rat: Optional[str] = None,
    tower_type: Optional[str] = None,
    provider_id: Optional[int] = None,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Find towers within a given radius of a point using PostGIS ST_DWithin.
    Returns towers with their provider information.
    """
    where_parts = [
        "location: {_st_d_within: {distance: $radius, from: {type: \"Point\", coordinates: [$longitude, $latitude]}}}"
    ]
    variables: dict = {
        "latitude": latitude,
        "longitude": longitude,
        "radius": radius_meters,
        "limit": limit,
    }
    var_defs = [
        "$latitude: float8!",
        "$longitude: float8!",
        "$radius: float8!",
        "$limit: Int!",
    ]

    if rat:
        where_parts.append("tower_providers: {rat: {_eq: $rat}}")
        variables["rat"] = rat
        var_defs.append("$rat: String!")
    if tower_type:
        where_parts.append("tower_type: {_eq: $tower_type}")
        variables["tower_type"] = tower_type
        var_defs.append("$tower_type: String!")
    if provider_id:
        where_parts.append("tower_providers: {provider_id: {_eq: $provider_id}}")
        variables["provider_id"] = provider_id
        var_defs.append("$provider_id: Int!")

    where = ", ".join(where_parts)

    query = f"""
    query TowersNearby({", ".join(var_defs)}) {{
        towers(
            where: {{{where}}},
            limit: $limit,
            order_by: {{id: asc}}
        ) {{
            {TOWER_WITH_PROVIDERS}
        }}
    }}
    """
    data = await hasura.execute(query, variables)
    return data.get("towers", [])


@router.get("/{tower_id}", response_model=TowerWithRelations)
async def get_tower(
    tower_id: int,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Get a single tower with all its providers, cells, and bands.
    """
    query = f"""
    query GetTower($id: Int!) {{
        towers_by_pk(id: $id) {{
            {TOWER_WITH_RELATIONS_QUERY}
        }}
    }}
    """
    data = await hasura.execute(query, {"id": tower_id})
    tower = data.get("towers_by_pk")
    if not tower:
        raise HTTPException(status_code=404, detail="Tower not found")
    return tower


@router.get("/{tower_id}/providers", response_model=list[TowerProviderWithDetails])
async def get_tower_providers(
    tower_id: int,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Get all providers for a specific tower.
    """
    query = f"""
    query GetTowerProviders($tower_id: Int!) {{
        tower_providers(where: {{tower_id: {{_eq: $tower_id}}}}, order_by: {{last_seen_at: desc_nulls_last}}) {{
            {TOWER_PROVIDER_FIELDS}
            provider {{
                {PROVIDER_FIELDS}
            }}
        }}
    }}
    """
    data = await hasura.execute(query, {"tower_id": tower_id})
    return data.get("tower_providers", [])


@router.post("", response_model=Tower, status_code=201)
async def create_tower(
    tower: TowerCreate,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Create a new tower (physical location).
    """
    query = f"""
    mutation CreateTower($object: towers_insert_input!) {{
        insert_towers_one(object: $object) {{
            {TOWER_FIELDS}
        }}
    }}
    """
    obj = tower.model_dump(exclude_none=True)
    data = await hasura.execute(query, {"object": obj})
    return data["insert_towers_one"]


@router.patch("/{tower_id}", response_model=Tower)
async def update_tower(
    tower_id: int,
    tower: TowerUpdate,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Update a tower's properties.
    """
    query = f"""
    mutation UpdateTower($id: Int!, $changes: towers_set_input!) {{
        update_towers_by_pk(pk_columns: {{id: $id}}, _set: $changes) {{
            {TOWER_FIELDS}
        }}
    }}
    """
    changes = tower.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")

    data = await hasura.execute(query, {"id": tower_id, "changes": changes})
    updated = data.get("update_towers_by_pk")
    if not updated:
        raise HTTPException(status_code=404, detail="Tower not found")
    return updated


@router.delete("/{tower_id}", status_code=204)
async def delete_tower(
    tower_id: int,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """
    Delete a tower and all its associated data.
    """
    query = """
    mutation DeleteTower($id: Int!) {
        delete_towers_by_pk(id: $id) {
            id
        }
    }
    """
    data = await hasura.execute(query, {"id": tower_id})
    if not data.get("delete_towers_by_pk"):
        raise HTTPException(status_code=404, detail="Tower not found")


