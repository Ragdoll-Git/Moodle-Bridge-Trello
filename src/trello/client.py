"""
MoodleAPI-Bridge — Cliente de la API REST de Trello.

Cliente con rate limiting para interactuar con boards, listas y tarjetas.
Soporta detección de duplicados para sincronización idempotente.
"""

import logging
import time
import re
import requests
from datetime import datetime
from typing import Optional

from .models import TrelloBoard, TrelloList, TrelloCard

logger = logging.getLogger("moodle-bridge.trello")

BASE_URL = "https://api.trello.com/1"


class TrelloAPIError(Exception):
    """Error en una llamada a la API de Trello"""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message)


class TrelloClient:
    """
    Cliente de la API REST de Trello con rate limiting.

    Uso:
        client = TrelloClient(api_key, token)
        boards = client.get_boards()
        client.create_card(list_id, "Mi tarea", desc="...", due="2026-06-01")
    """

    def __init__(
        self,
        api_key: str,
        token: str,
        request_delay: float = 0.1,
    ):
        self.api_key = api_key
        self.token = token
        self.request_delay = request_delay
        self._last_request_time: float = 0

        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "MoodleAPI-Bridge/0.1.0 (Moodle-Trello Sync)",
        })

    # ============================================================
    # Autenticación params
    # ============================================================

    @property
    def _auth_params(self) -> dict:
        """Parámetros de autenticación para todas las requests"""
        return {"key": self.api_key, "token": self.token}

    # ============================================================
    # Boards
    # ============================================================

    def get_boards(self) -> list[TrelloBoard]:
        """
        Obtiene todos los boards del usuario autenticado.

        Returns:
            Lista de TrelloBoard
        """
        logger.info("Obteniendo boards de Trello...")
        data = self._get("/members/me/boards", {"filter": "open"})
        boards = [TrelloBoard(**b) for b in data]
        logger.info(f"Se encontraron {len(boards)} boards")
        return boards

    def find_board_by_name(self, name: str) -> Optional[TrelloBoard]:
        """
        Busca un board por nombre (case-insensitive).

        Args:
            name: Nombre del board a buscar

        Returns:
            TrelloBoard si se encuentra, None si no
        """
        boards = self.get_boards()
        name_lower = name.lower()
        for board in boards:
            if board.name.lower() == name_lower:
                logger.info(f"Board encontrado: '{board.name}' (id: {board.id})")
                return board
        logger.warning(f"No se encontró board con nombre '{name}'")
        return None

    def create_board(self, name: str, desc: str = "") -> TrelloBoard:
        """Crea un nuevo board"""
        logger.info(f"Creando board '{name}'...")
        data = self._post("/boards", {"name": name, "desc": desc})
        board = TrelloBoard(**data)
        logger.info(f"Board creado: '{board.name}' (id: {board.id})")
        return board

    # ============================================================
    # Lists
    # ============================================================

    def get_board_lists(self, board_id: str, filter_status: str = "all") -> list[TrelloList]:
        """
        Obtiene las listas de un board.

        Args:
            board_id: ID del board
            filter_status: 'open', 'closed', 'all' (default: 'all')

        Returns:
            Lista de TrelloList
        """
        logger.info(f"Obteniendo listas del board {board_id} con filtro {filter_status}...")
        data = self._get(f"/boards/{board_id}/lists", {"filter": filter_status})
        lists = [TrelloList(**lst) for lst in data]
        logger.info(f"Board tiene {len(lists)} listas")
        return lists

    def find_list_by_name(
        self, board_id: str, name: str
    ) -> Optional[TrelloList]:
        """Busca una lista por nombre en un board (case-insensitive)"""
        lists = self.get_board_lists(board_id)
        name_lower = name.lower()
        for lst in lists:
            if lst.name.lower() == name_lower:
                return lst
        return None

    def create_list(self, board_id: str, name: str) -> TrelloList:
        """Crea una nueva lista en un board"""
        logger.info(f"Creando lista '{name}' en board {board_id}...")
        data = self._post("/lists", {"name": name, "idBoard": board_id})
        lst = TrelloList(**data)
        logger.info(f"Lista creada: '{lst.name}' (id: {lst.id})")
        return lst

    def get_or_create_list(self, board_id: str, name: str) -> TrelloList:
        """
        Busca una lista por nombre; si no existe, la crea.

        Args:
            board_id: ID del board
            name: Nombre de la lista

        Returns:
            TrelloList existente o recién creada
        """
        existing = self.find_list_by_name(board_id, name)
        if existing and not existing.closed:
            logger.info(f"Lista existente encontrada: '{existing.name}'")
            return existing
        return self.create_list(board_id, name)

    # ============================================================
    # Cards
    # ============================================================

    def get_list_cards(self, list_id: str) -> list[TrelloCard]:
        """Obtiene las tarjetas de una lista"""
        data = self._get(f"/lists/{list_id}/cards")
        return [TrelloCard(**c) for c in data]

    def get_board_cards(self, board_id: str) -> list[TrelloCard]:
        """Obtiene todas las tarjetas de un board (incluyendo archivadas)"""
        data = self._get(f"/boards/{board_id}/cards", {"filter": "all"})
        return [TrelloCard(**c) for c in data]

    def create_card(
        self,
        list_id: str,
        name: str,
        desc: str = "",
        due: Optional[str] = None,
        dueComplete: Optional[bool] = None,
        labels: Optional[list[str]] = None,
    ) -> TrelloCard:
        """
        Crea una nueva tarjeta.

        Args:
            list_id: ID de la lista destino
            name: Nombre de la tarjeta
            desc: Descripción (soporta Markdown)
            due: Fecha de vencimiento ISO 8601 (ej: "2026-06-15T23:59:00.000Z")
            dueComplete: Indica si el vencimiento está completado (check verde)
            labels: Lista de IDs de labels

        Returns:
            TrelloCard creada
        """
        params: dict = {"idList": list_id, "name": name, "desc": desc}
        if due:
            params["due"] = due
        if dueComplete is not None:
            params["dueComplete"] = dueComplete
        if labels:
            params["idLabels"] = ",".join(labels)

        logger.info(f"Creando tarjeta '{name}' en lista {list_id}...")
        data = self._post("/cards", params)
        card = TrelloCard(**data)
        logger.info(f"Tarjeta creada: '{card.name}' (id: {card.id})")
        return card

    def update_card(
        self,
        card_id: str,
        name: Optional[str] = None,
        desc: Optional[str] = None,
        due: Optional[str] = None,
        dueComplete: Optional[bool] = None,
        idList: Optional[str] = None,
    ) -> TrelloCard:
        """
        Actualiza una tarjeta existente. Solo actualiza los campos pasados.

        Args:
            card_id: ID de la tarjeta
            name: Nuevo nombre (None = no cambiar)
            desc: Nueva descripción (None = no cambiar)
            due: Nueva fecha de vencimiento (None = no cambiar)
            dueComplete: Completar o descompletar el vencimiento (None = no cambiar)
            idList: Mover a otra lista (None = no cambiar)

        Returns:
            TrelloCard actualizada
        """
        params: dict = {}
        if name is not None:
            params["name"] = name
        if desc is not None:
            params["desc"] = desc
        if due is not None:
            params["due"] = due
        if dueComplete is not None:
            params["dueComplete"] = dueComplete
        if idList is not None:
            params["idList"] = idList

        if not params:
            logger.debug(f"No hay cambios para tarjeta {card_id}")
            data = self._get(f"/cards/{card_id}")
            return TrelloCard(**data)

        logger.info(f"Actualizando tarjeta {card_id}: {list(params.keys())}...")
        data = self._put(f"/cards/{card_id}", params)
        card = TrelloCard(**data)
        logger.info(f"Tarjeta actualizada: '{card.name}'")
        return card

    def find_card_by_name(
        self, board_id: str, name: str, cards_cache: Optional[list[TrelloCard]] = None
    ) -> Optional[TrelloCard]:
        """
        Busca una tarjeta por nombre en un board.
        Usa cache si se proporciona para evitar requests múltiples.

        Args:
            board_id: ID del board
            name: Nombre de la tarjeta a buscar
            cards_cache: Lista pre-cargada de tarjetas (opcional)

        Returns:
            TrelloCard si existe, None si no
        """
        cards = cards_cache if cards_cache is not None else self.get_board_cards(board_id)
        name_lower = name.lower().strip()
        for card in cards:
            if card.name.lower().strip() == name_lower:
                return card
        return None

    # ============================================================
    # HTTP internals con rate limiting
    # ============================================================

    def _rate_limit(self):
        """Aplica delay entre requests"""
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            remaining = self.request_delay - elapsed
            if remaining > 0:
                time.sleep(remaining)

    def _get(self, path: str, params: Optional[dict] = None) -> any:
        """GET request a la API de Trello"""
        self._rate_limit()
        url = f"{BASE_URL}{path}"
        all_params = {**self._auth_params, **(params or {})}

        try:
            response = self._session.get(url, params=all_params, timeout=30)
            self._last_request_time = time.time()
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise TrelloAPIError(
                f"Error HTTP {response.status_code} en GET {path}: {response.text[:300]}",
                status_code=response.status_code,
            ) from e
        except requests.exceptions.RequestException as e:
            raise TrelloAPIError(f"Error de conexión en GET {path}: {e}") from e

    def _post(self, path: str, params: Optional[dict] = None) -> any:
        """POST request a la API de Trello. Auth va en URL, data en body."""
        self._rate_limit()
        url = f"{BASE_URL}{path}"

        try:
            response = self._session.post(
                url,
                params=self._auth_params,
                json=params or {},
                timeout=30,
            )
            self._last_request_time = time.time()
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise TrelloAPIError(
                f"Error HTTP {response.status_code} en POST {path}: {response.text[:300]}",
                status_code=response.status_code,
            ) from e
        except requests.exceptions.RequestException as e:
            raise TrelloAPIError(f"Error de conexión en POST {path}: {e}") from e

    def _put(self, path: str, params: Optional[dict] = None) -> any:
        """PUT request a la API de Trello. Auth va en URL, data en body."""
        self._rate_limit()
        url = f"{BASE_URL}{path}"

        try:
            response = self._session.put(
                url,
                params=self._auth_params,
                json=params or {},
                timeout=30,
            )
            self._last_request_time = time.time()
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise TrelloAPIError(
                f"Error HTTP {response.status_code} en PUT {path}: {response.text[:300]}",
                status_code=response.status_code,
            ) from e
        except requests.exceptions.RequestException as e:
            raise TrelloAPIError(f"Error de conexión en PUT {path}: {e}") from e

    # ============================================================
    # Cleanup
    # ============================================================

    def close(self):
        """Cierra la sesión HTTP"""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
