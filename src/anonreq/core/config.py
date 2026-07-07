from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum
from typing import Optional

class DeploymentMode(str, Enum):
    REVERSE = "reverse"
    TRANSPARENT = "transparent"
    VIRTUAL = "virtual"
    PHYSICAL = "physical"

class Settings(BaseSettings):
    deployment_mode: DeploymentMode = DeploymentMode.REVERSE
    proxy_port: int = 8443
    api_port: int = 8080
    host: str = "0.0.0.0"
    
    # Prometheus Metrics
    metrics_port: int = 9090
    
    # AI Firewall Settings
    firewall_max_latency_ms: int = 20
    firewall_model_path: Optional[str] = None
    
    # Voice Settings
    voice_max_latency_ms: int = 150
    whisper_model_size: str = "tiny"
    
    # Redis Cache Manager
    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_prefix="ANONREQ_", env_file=".env", env_file_encoding="utf-8")

settings = Settings()
