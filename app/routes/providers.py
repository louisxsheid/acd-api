from fastapi import APIRouter, Depends, HTTPException

from app.models import Provider, ProviderCreate, ProviderUpdate, PaginationParams
from app.services import HasuraClient, get_hasura_client

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[Provider])
async def list_providers(
    pagination: PaginationParams = Depends(),
    hasura: HasuraClient = Depends(get_hasura_client),
):
    query = """
    query ListProviders($limit: Int!, $offset: Int!) {
        providers(limit: $limit, offset: $offset, order_by: {id: asc}) {
            id
            country_id
            provider_id
            name
            visible
        }
    }
    """
    data = await hasura.execute(query, {"limit": pagination.limit, "offset": pagination.offset})
    return data.get("providers", [])


@router.get("/{provider_id}", response_model=Provider)
async def get_provider(
    provider_id: int,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    query = """
    query GetProvider($id: Int!) {
        providers_by_pk(id: $id) {
            id
            country_id
            provider_id
            name
            visible
        }
    }
    """
    data = await hasura.execute(query, {"id": provider_id})
    provider = data.get("providers_by_pk")
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.post("", response_model=Provider, status_code=201)
async def create_provider(
    provider: ProviderCreate,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    query = """
    mutation CreateProvider($object: providers_insert_input!) {
        insert_providers_one(object: $object) {
            id
            country_id
            provider_id
            name
            visible
        }
    }
    """
    data = await hasura.execute(query, {"object": provider.model_dump()})
    return data["insert_providers_one"]


@router.patch("/{provider_id}", response_model=Provider)
async def update_provider(
    provider_id: int,
    provider: ProviderUpdate,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    query = """
    mutation UpdateProvider($id: Int!, $changes: providers_set_input!) {
        update_providers_by_pk(pk_columns: {id: $id}, _set: $changes) {
            id
            country_id
            provider_id
            name
            visible
        }
    }
    """
    changes = provider.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")

    data = await hasura.execute(query, {"id": provider_id, "changes": changes})
    updated = data.get("update_providers_by_pk")
    if not updated:
        raise HTTPException(status_code=404, detail="Provider not found")
    return updated


@router.delete("/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: int,
    hasura: HasuraClient = Depends(get_hasura_client),
):
    query = """
    mutation DeleteProvider($id: Int!) {
        delete_providers_by_pk(id: $id) {
            id
        }
    }
    """
    data = await hasura.execute(query, {"id": provider_id})
    if not data.get("delete_providers_by_pk"):
        raise HTTPException(status_code=404, detail="Provider not found")
