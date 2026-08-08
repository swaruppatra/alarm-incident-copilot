import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, status

from simulator.app.auth import require_bearer_token
from simulator.app.data.db import get_db
from simulator.app.models.assets import Asset, AssetMetadata, AssetSearchResponse

router = APIRouter(prefix="/assets", tags=["assets"], dependencies=[Depends(require_bearer_token)])


def _row_to_asset(row: sqlite3.Row) -> Asset:
    """Build the lightweight Asset shape from an assets table row.

    Args:
        row: a sqlite3.Row from the assets table.

    Returns:
        Asset: the lightweight asset representation.
    """
    return Asset(
        asset_id=row["asset_id"],
        asset_name=row["asset_name"],
        site=row["site"],
        unit=row["unit"],
        asset_type=row["asset_type"],
    )


def _row_to_asset_metadata(row: sqlite3.Row) -> AssetMetadata:
    """Build the full AssetMetadata shape from an assets table row.

    Args:
        row: a sqlite3.Row from the assets table.

    Returns:
        AssetMetadata: the full asset metadata representation.
    """
    return AssetMetadata(
        asset_id=row["asset_id"],
        asset_name=row["asset_name"],
        site=row["site"],
        unit=row["unit"],
        asset_type=row["asset_type"],
        manufacturer=row["manufacturer"],
        install_date=row["install_date"],
        criticality=row["criticality"],
    )


@router.get("/search", response_model=AssetSearchResponse)
def search_assets(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=100),
    unit: str | None = Query(default=None),
    db: sqlite3.Connection = Depends(get_db),
) -> AssetSearchResponse:
    """Search assets by name substring, optionally filtered by unit.

    Args:
        query: case-insensitive substring matched against asset_name.
        limit: maximum number of results to return.
        unit: optional exact-match unit filter, e.g. "Unit 5".
        db: request-scoped sqlite3 connection.

    Returns:
        AssetSearchResponse: matching assets in the lightweight Asset shape.
    """
    sql = "SELECT * FROM assets WHERE asset_name LIKE ?"
    params: list[object] = [f"%{query}%"]
    if unit is not None:
        sql += " AND unit = ?"
        params.append(unit)
    sql += " LIMIT ?"
    params.append(limit)
    rows = db.execute(sql, params).fetchall()
    return AssetSearchResponse(results=[_row_to_asset(row) for row in rows])


@router.get("/{asset_id}/metadata", response_model=AssetMetadata)
def get_asset_metadata(asset_id: str, db: sqlite3.Connection = Depends(get_db)) -> AssetMetadata:
    """Fetch full metadata for a single asset by ID.

    Args:
        asset_id: the asset identifier, e.g. "AST-0001".
        db: request-scoped sqlite3 connection.

    Returns:
        AssetMetadata: the full asset metadata.
    """
    row = db.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset {asset_id} not found")
    return _row_to_asset_metadata(row)
