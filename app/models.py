from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Sensitivity(StrEnum):
    SAFE = "safe"
    INTERNAL_ONLY = "internal_only"
    REVIEW_REQUIRED = "review_required"


class PresentationDateSource(StrEnum):
    FILENAME = "filename"
    MODEL = "model"
    UNKNOWN = "unknown"


class AnalysisResult(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    synopsis: str = Field(min_length=1, max_length=2_000)
    sensitivity: Sensitivity
    sensitivity_reason: str = Field(min_length=1, max_length=1_000)
    presentation_date: date | None = None
    presentation_date_evidence: str | None = None


class TranscriptionMetadata(StrictModel):
    model: str
    device: str
    compute_type: str
    duration_seconds: float = Field(ge=0)
    processing_seconds: float = Field(ge=0)
    realtime_factor: float = Field(ge=0)


class ProcessingResult(StrictModel):
    success: bool = True
    source_filename: str
    presentation_date: date | None
    presentation_date_source: PresentationDateSource
    title: str
    synopsis: str
    sensitivity: Sensitivity
    sensitivity_reason: str
    transcription: TranscriptionMetadata
    total_processing_seconds: float = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class ProcessingFailure(StrictModel):
    success: bool = False
    source_filename: str
    error: str
    warnings: list[str] = Field(default_factory=list)
