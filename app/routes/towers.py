from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import (
    Tower,
    TowerCreate,
    TowerUpdate,
    TowerWithRelations,
    TowersNearbyRequest,
    PaginationParams,
)
from app.services import HasuraClient, get_hasura_client

router = APIRouter(prefix="/towers", tags=["towers"])

TOWER_FIELDS = """
    id
    external_id
    provider_id
    rat
    rat_subtype
    tower_type
    site_id
    region_id
    latitude
    longitude
    visible
    first_seen_at
    last_seen_at
    tower_mover
    tower_mover_id
    generator
    generator_time
    has_bandwidth_data
    has_frequency_data
    endc_available
    contributors
    raw_channels
    raw_bandwidths
    raw_band_numbers
    created_at
"""

TOWER_WITH_RELATIONS = f"""
    {TOWER_FIELDS}
    provider {{
        id
        country_id
        provider_id
        name
        visible
    }}
    cells {{
        id
        tower_id
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
    }}
    tower_bands {{
        id
        tower_id
        band_number
        band_name
        channel
        bandwidth
        modulation
    }}
"""


@router.get("", response_model=list[Tower])
async def list_towers(
    pagination: PaginationParams = Depends(),
    rat: Optional[str] = Query(None, description="Filter by RAT type"),
    tower_type: Optional[str] = Query(None, description="Filter by tower type"),
    provider_id: Optional[int] = Query(None, description="Filter by provider ID"),
    visible: Optional[bool] = Query(None, description="Filter by visibility"),
    hasura: HasuraClient = Depends(get_hasura_client),
):
    where_clauses = []
    variables: dict = {"limit": pagination.limit, "offset": pagination.offset}

    if rat:
        where_clauses.append("rat: {_eq: $rat}")
        variables["rat"] = rat
    if tower_type:
        where_clauses.append("tower_type: {_eq: $tower_type}")
        variables["tower_type"] = tower_type
    if provider_id:
        where_clauses.append("provider_id: {_eq: $provider_id}")
        variables["provider_id"] = provider_id
    if visible is not None:
        where_clauses.append("visible: {_eq: $visible}")
        variables["visible"] = visible

    where = ", ".join(where_clauses) if where_clauses else ""
    where_clause = f"where: {{{where}}}, " if where else ""

    var_defs = ["$limit: Int!", "$offset: Int!"]
    if rat:
        var_defs.append("$rat: String!")
    if tower_type:
        var_defs.append("$tower_type: String!")
    if provider_id:
        var_defs.append("$provider_id: Int!")
    if visible is not None:
        var_defs.append("$visible: Boolean!")

    query = f"""
    query ListTowers({", ".join(var_defs)}) {{
        towers({where_clause}limit: $limit, offset: $offset, order_by: {{id: asc}}) {{
            {TOWER_FIELDS}
        }}
    }}
    """
    data = await hasura.execute(query, variables)
    return data.get("towers", [])


@router.get("/nearby", response_model=list[Tower])
async def get_towers_nearby(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_meters: float = Query(1000, ge=1, le=100000),
    limit: int = Query(100, ge=1, le=1000),
    rat: Optional[str] = None,
    tower_type: Optional[str] = None,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    """Find towers within a given radius of a point using PostGIS ST_DWithin."""
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
        where_parts.append("rat: {_eq: $rat}")
        variables["rat"] = rat
        var_defs.append("$rat: String!")
    if tower_type:
        where_parts.append("tower_type: {_eq: $tower_type}")
        variables["tower_type"] = tower_type
        var_defs.append("$tower_type: String!")

    where = ", ".join(where_parts)

    query = f"""
    query TowersNearby({", ".join(var_defs)}) {{
        towers(
            where: {{{where}}},
            limit: $limit,
            order_by: {{id: asc}}
        ) {{
            {TOWER_FIELDS}
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
    query = f"""
    query GetTower($id: Int!) {{
        towers_by_pk(id: $id) {{
            {TOWER_WITH_RELATIONS}
        }}
    }}
    """
    data = await hasura.execute(query, {"id": tower_id})
    tower = data.get("towers_by_pk")
    if not tower:
        raise HTTPException(status_code=404, detail="Tower not found")
    return tower


@router.post("", response_model=Tower, status_code=201)
async def create_tower(
    tower: TowerCreate,
    hasura: HasuraClient = Depends(get_hasura_client),
):
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
