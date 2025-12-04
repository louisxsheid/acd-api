from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import Cell, CellCreate, CellUpdate, PaginationParams
from app.services import HasuraClient, get_hasura_client

router = APIRouter(prefix="/cells", tags=["cells"])

CELL_FIELDS = """
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
"""


@router.get("", response_model=list[Cell])
async def list_cells(
    pagination: PaginationParams = Depends(),
    tower_id: Optional[int] = Query(None, description="Filter by tower ID"),
    subsystem: Optional[str] = Query(None, description="Filter by subsystem"),
    hasura: HasuraClient = Depends(get_hasura_client),
):
    where_clauses = []
    variables: dict = {"limit": pagination.limit, "offset": pagination.offset}
    var_defs = ["$limit: Int!", "$offset: Int!"]

    if tower_id:
        where_clauses.append("tower_id: {_eq: $tower_id}")
        variables["tower_id"] = tower_id
        var_defs.append("$tower_id: Int!")
    if subsystem:
        where_clauses.append("subsystem: {_eq: $subsystem}")
        variables["subsystem"] = subsystem
        var_defs.append("$subsystem: String!")

    where = ", ".join(where_clauses) if where_clauses else ""
    where_clause = f"where: {{{where}}}, " if where else ""

    query = f"""
    query ListCells({", ".join(var_defs)}) {{
        cells({where_clause}limit: $limit, offset: $offset, order_by: {{id: asc}}) {{
            {CELL_FIELDS}
        }}
    }}
    """
    data = await hasura.execute(query, variables)
    return data.get("cells", [])


@router.get("/{cell_id}", response_model=Cell)
async def get_cell(
    cell_id: int,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    query = f"""
    query GetCell($id: Int!) {{
        cells_by_pk(id: $id) {{
            {CELL_FIELDS}
        }}
    }}
    """
    data = await hasura.execute(query, {"id": cell_id})
    cell = data.get("cells_by_pk")
    if not cell:
        raise HTTPException(status_code=404, detail="Cell not found")
    return cell


@router.post("", response_model=Cell, status_code=201)
async def create_cell(
    cell: CellCreate,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    query = f"""
    mutation CreateCell($object: cells_insert_input!) {{
        insert_cells_one(object: $object) {{
            {CELL_FIELDS}
        }}
    }}
    """
    obj = cell.model_dump(exclude_none=True)
    data = await hasura.execute(query, {"object": obj})
    return data["insert_cells_one"]


@router.patch("/{cell_id}", response_model=Cell)
async def update_cell(
    cell_id: int,
    cell: CellUpdate,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    query = f"""
    mutation UpdateCell($id: Int!, $changes: cells_set_input!) {{
        update_cells_by_pk(pk_columns: {{id: $id}}, _set: $changes) {{
            {CELL_FIELDS}
        }}
    }}
    """
    changes = cell.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")

    data = await hasura.execute(query, {"id": cell_id, "changes": changes})
    updated = data.get("update_cells_by_pk")
    if not updated:
        raise HTTPException(status_code=404, detail="Cell not found")
    return updated


@router.delete("/{cell_id}", status_code=204)
async def delete_cell(
    cell_id: int,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    query = """
    mutation DeleteCell($id: Int!) {
        delete_cells_by_pk(id: $id) {
            id
        }
    }
    """
    data = await hasura.execute(query, {"id": cell_id})
    if not data.get("delete_cells_by_pk"):
        raise HTTPException(status_code=404, detail="Cell not found")
