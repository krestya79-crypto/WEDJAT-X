"""Pydantic schemas for the WEDJAT-X FastAPI adapter."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    system: str = "WEDJAT-X"
    backend_version: str = "1.0.0"
    timestamp: str
    disclaimer: str


class NasaAnalysisRequest(BaseModel):
    participant_id: Optional[str] = Field(default="C001", description="Participant ID: C001, C002, C003, or C004")
    data: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional custom NASA assay records")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Execution metadata")


class WearableAnalysisRequest(BaseModel):
    scenario_name: Optional[str] = Field(default="normal_scenario.csv", description="Synthetic scenario filename")
    data: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional custom synthetic stream records")
    subject_id: Optional[str] = Field(default="SYNTHETIC_ASTRONAUT", description="Subject identifier")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Execution metadata")


class ScenarioSummary(BaseModel):
    filename: str
    scenario_name: str
    total_samples: int
    sensor_types: List[str]
    missing_count: int
    is_synthetic: bool = True


class ParticipantSummary(BaseModel):
    participant_id: str
    display_name: str
    role: str
    mission: str = "Inspiration4 (OSD-575)"
    total_observations: int
    total_biomarkers: int
