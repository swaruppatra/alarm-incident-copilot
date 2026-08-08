from pydantic import BaseModel


class CalculationFilters(BaseModel):
    unit: str | None = None
    start_time: str | None = None
    end_time: str | None = None

class GenerateCalculationRequest(BaseModel):
    calculation_type: str          # e.g. "alarm_flood_index"
    filters: CalculationFilters

class GenerateCalculationResponse(BaseModel):
    calculation_id: str
    calculation_type: str

class ExecuteCalculationRequest(BaseModel):
    calculation_id: str
    filters: CalculationFilters

class ExecuteCalculationResponse(BaseModel):
    calculation_id: str
    result: dict