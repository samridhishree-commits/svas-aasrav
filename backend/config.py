from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / '.env', ROOT / 'backend' / '.env'), extra='ignore')
    photon_base_url: str = 'https://photon.komoot.io'
    osrm_base_url: str = 'https://routing.openstreetmap.de/routed-car'
    maps_user_agent: str = 'svas-aasrav/1.0 (Delhi NCR hackathon route planner)'
    gemini_api_key: str = ''
    gemini_model: str = 'gemini-3.5-flash-lite'
    neo4j_uri: str = ''
    neo4j_username: str = 'neo4j'
    neo4j_password: str = ''
    neo4j_database: str = 'neo4j'
    cors_origins: str = 'http://localhost:5173,http://127.0.0.1:5173'
    open_meteo_base_url: str = 'https://air-quality-api.open-meteo.com/v1/air-quality'
    waqi_api_token: str = ''
    station_max_distance_km: float = Field(10, ge=1, le=30)
    route_target_count: int = Field(4, ge=2, le=5)
    route_sample_count: int = Field(10, ge=2, le=20)
    pollution_weight: float = Field(1.0, ge=0, le=10)
    high_aqi_threshold: int = Field(200, ge=0, le=500)
    graph_retention_minutes: int = Field(60, ge=5, le=1440)

    @property
    def allowed_origins(self):
        return [s.strip().rstrip('/') for s in self.cors_origins.split(',') if s.strip()]
