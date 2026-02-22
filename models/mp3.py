"""Pydantic request model for the /mp3 endpoint."""

from typing import Optional
from pydantic import BaseModel, HttpUrl


class MP3Request(BaseModel):
    url: HttpUrl
    filename: Optional[str] = None  # suggested download filename (without .mp3 extension)
