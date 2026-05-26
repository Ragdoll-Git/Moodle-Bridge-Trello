"""
MoodleAPI-Bridge — Modelos de Trello.

Estructuras de datos Pydantic para boards, listas, tarjetas y
resultados de sincronización.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
# Modelos de la API de Trello
# ============================================================

class TrelloBoard(BaseModel):
    """Board de Trello"""
    id: str
    name: str = ""
    desc: str = ""
    url: str = ""
    closed: bool = False
    shortUrl: Optional[str] = None

    model_config = {"extra": "allow"}


class TrelloList(BaseModel):
    """Lista dentro de un board de Trello"""
    id: str
    name: str = ""
    idBoard: str = ""
    closed: bool = False
    pos: Optional[float] = None

    model_config = {"extra": "allow"}


class TrelloCard(BaseModel):
    """Tarjeta de Trello"""
    id: str
    name: str = ""
    desc: str = ""
    idList: str = ""
    idBoard: str = ""
    due: Optional[str] = None
    dueComplete: bool = False
    url: str = ""
    closed: bool = False
    shortUrl: Optional[str] = None
    labels: list[dict] = Field(default_factory=list)

    model_config = {"extra": "allow"}


# ============================================================
# Modelos de sincronización
# ============================================================

class SyncedCard(BaseModel):
    """Resultado de sincronización de una tarjeta individual"""
    assignment_name: str
    course_name: str
    card_id: str
    card_url: str
    action: str  # "created", "updated", "skipped"
    due_date: Optional[str] = None
    due_complete: Optional[bool] = None



class TrelloSyncResult(BaseModel):
    """Resultado completo de la sincronización Moodle → Trello"""
    success: bool
    message: str
    board_id: str = ""
    board_name: str = ""
    board_url: str = ""
    total_synced: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    cards: list[SyncedCard] = Field(default_factory=list)
    error: Optional[str] = None
