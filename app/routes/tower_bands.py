from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import TowerBand, TowerBandCreate, TowerBandUpdate, PaginationParams
from app.services import HasuraClient, get_hasura_client

router = APIRouter(prefix="/tower-bands", tags=["tower_bands"])

TOWER_BAND_FIELDS = """
    id
    tower_id
    band_number
    band_name
    channel
    bandwidth
    modulation
"""


@router.get("", response_model=list[TowerBand])
async def list_tower_bands(
    pagination: PaginationParams = Depends(),
    tower_id: Optional[int] = Query(None, description="Filter by tower ID"),
    band_number: Optional[int] = Query(None, description="Filter by band number"),
    hasura: HasuraClient = Depends(get_hasura_client),
):
    where_clauses = []
    variables: dict = {"limit": pagination.limit, "offset": pagination.offset}
    var_defs = ["$limit: Int!", "$offset: Int!"]

    if tower_id:
        where_clauses.append("tower_id: {_eq: $tower_id}")
        variables["tower_id"] = tower_id
        var_defs.append("$tower_id: Int!")
    if band_number:
        where_clauses.append("band_number: {_eq: $band_number}")
        variables["band_number"] = band_number
        var_defs.append("$band_number: Int!")

    where = ", ".join(where_clauses) if where_clauses else ""
    where_clause = f"where: {{{where}}}, " if where else ""

    query = f"""
    query ListTowerBands({", ".join(var_defs)}) {{
        tower_bands({where_clause}limit: $limit, offset: $offset, order_by: {{id: asc}}) {{
            {TOWER_BAND_FIELDS}
        }}
    }}
    """
    data = await hasura.execute(query, variables)
    return data.get("tower_bands", [])


@router.get("/{tower_band_id}", response_model=TowerBand)
async def get_tower_band(
    tower_band_id: int,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    query = f"""
    query GetTowerBand($id: Int!) {{
        tower_bands_by_pk(id: $id) {{
            {TOWER_BAND_FIELDS}
        }}
    }}
    """
    data = await hasura.execute(query, {"id": tower_band_id})
    band = data.get("tower_bands_by_pk")
    if not band:
        raise HTTPException(status_code=404, detail="Tower band not found")
    return band


@router.post("", response_model=TowerBand, status_code=201)
async def create_tower_band(
    band: TowerBandCreate,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    query = f"""
    mutation CreateTowerBand($object: tower_bands_insert_input!) {{
        insert_tower_bands_one(object: $object) {{
            {TOWER_BAND_FIELDS}
        }}
    }}
    """
    obj = band.model_dump(exclude_none=True)
    data = await hasura.execute(query, {"object": obj})
    return data["insert_tower_bands_one"]


@router.patch("/{tower_band_id}", response_model=TowerBand)
async def update_tower_band(
    tower_band_id: int,
    band: TowerBandUpdate,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    query = f"""
    mutation UpdateTowerBand($id: Int!, $changes: tower_bands_set_input!) {{
        update_tower_bands_by_pk(pk_columns: {{id: $id}}, _set: $changes) {{
            {TOWER_BAND_FIELDS}
        }}
    }}
    """
    changes = band.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")

    data = await hasura.execute(query, {"id": tower_band_id, "changes": changes})
    updated = data.get("update_tower_bands_by_pk")
    if not updated:
        raise HTTPException(status_code=404, detail="Tower band not found")
    return updated


@router.delete("/{tower_band_id}", status_code=204)
async def delete_tower_band(
    tower_band_id: int,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    query = """
    mutation DeleteTowerBand($id: Int!) {
        delete_tower_bands_by_pk(id: $id) {
            id
        }
    }
    """
    data = await hasura.execute(query, {"id": tower_band_id})
    if not data.get("delete_tower_bands_by_pk"):
        raise HTTPException(status_code=404, detail="Tower band not found")
