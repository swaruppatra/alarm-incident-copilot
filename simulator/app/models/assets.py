from pydantic import BaseModel


class Asset(BaseModel):
    asset_id: str
    asset_name: str
    site: str          # e.g. "EastRefinery"
    unit: str          # e.g. "Unit 2"
    asset_type: str    # e.g. "pump", "compressor", "motor"


class AssetSearchResponse(BaseModel):
    results: list[Asset]


class AssetMetadata(Asset):
    manufacturer: str
    install_date: str
    criticality: str    # "low" | "medium" | "high" | "critical"