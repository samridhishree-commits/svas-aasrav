from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Coordinate(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)

class RouteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pickup: str = Field(min_length=2, max_length=250)
    drop: str = Field(min_length=2, max_length=250)
    delivery_window_minutes: int = Field(90, ge=5, le=480)
    has_mask: bool = True
    travel_mode: Literal['DRIVE'] = 'DRIVE'
    max_aqi: int | None = Field(None, ge=1, le=501, description='Every sampled US AQI must be strictly below this value.')
    aqi_standard: Literal['US'] = 'US'

    @field_validator('pickup', 'drop')
    @classmethod
    def clean_address(cls, value):
        value = ' '.join(value.split())
        if len(value) < 2:
            raise ValueError('Enter a pickup and a drop location.')
        return value


class ParseTripRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str = Field(min_length=5, max_length=1500)
    delivery_window_minutes: int = Field(75, ge=5, le=480)
    has_mask: bool = True
    max_aqi: int | None = Field(None, ge=1, le=501)


class AnalyzeTripRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    trip_id: str = Field(min_length=1, max_length=64)
    route_id: str = Field(min_length=1, max_length=64)

class FleetSuggestionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str = Field(min_length=5,max_length=3000)
