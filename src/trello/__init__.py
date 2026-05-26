"""
MoodleAPI-Bridge — Módulo Trello.

Cliente y modelos para la integración con la API de Trello.
"""

from .client import TrelloClient, TrelloAPIError

__all__ = ["TrelloClient", "TrelloAPIError"]
