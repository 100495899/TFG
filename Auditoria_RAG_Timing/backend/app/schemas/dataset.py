import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

Frequency = Literal["high", "medium", "low"]
Length = Literal["short", "medium", "long"]
QueryText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class LengthGroups(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corta: list[QueryText]
    media: list[QueryText]
    larga: list[QueryText]


class DatasetContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alta_frecuencia: LengthGroups
    media_frecuencia: LengthGroups
    baja_frecuencia: LengthGroups


class DatasetQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: QueryText
    frequency: Frequency
    length: Length


class DatasetRead(BaseModel):
    id: uuid.UUID
    name: str
    original_filename: str
    total_queries: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DatasetPreview(BaseModel):
    dataset: DatasetRead
    preview: list[DatasetQuery]
    distribution: dict[str, dict[str, int]]
