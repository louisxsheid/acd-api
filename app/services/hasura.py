import os
from typing import Any, Optional

import httpx
from fastapi import HTTPException


class HasuraClient:
    def __init__(self, endpoint: str, admin_secret: Optional[str] = None):
        self.endpoint = endpoint
        self.admin_secret = admin_secret
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.admin_secret:
            headers["x-hasura-admin-secret"] = self.admin_secret
        return headers

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.endpoint,
                headers=self.headers,
                timeout=30.0,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def execute(
        self,
        query: str,
        variables: Optional[dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> dict[str, Any]:
        client = await self.get_client()

        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        if operation_name:
            payload["operationName"] = operation_name

        try:
            response = await client.post("/v1/graphql", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Hasura request failed: {e.response.text}",
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Could not connect to Hasura: {str(e)}",
            )

        result = response.json()

        if "errors" in result:
            raise HTTPException(
                status_code=400,
                detail={"graphql_errors": result["errors"]},
            )

        return result.get("data", {})


_hasura_client: Optional[HasuraClient] = None


def get_hasura_client() -> HasuraClient:
    global _hasura_client
    if _hasura_client is None:
        endpoint = os.getenv("HASURA_GRAPHQL_ENDPOINT", "http://localhost:8080")
        admin_secret = os.getenv("HASURA_GRAPHQL_ADMIN_SECRET")
        _hasura_client = HasuraClient(endpoint, admin_secret)
    return _hasura_client
