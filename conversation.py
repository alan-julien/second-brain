from dataclasses import dataclass


@dataclass
class TaskDraft:
    name: str | None = None
    importance: str | None = None
    due_date: str | None = None
    category: str | None = None
    subcategory: str | None = None


@dataclass
class ConversationState:
    """Contexte d'une conversation en attente.

    `pending` est non-nul quand le bot a posé une question et attend la suite
    (information manquante a la creation, ou desambiguisation d'une tache cible).
    L'IA recoit ce contexte au tour suivant et reprend le fil.
    """

    pending: dict | None = None


class ConversationManager:
    def __init__(self) -> None:
        self._states: dict[int, ConversationState] = {}

    def get(self, user_id: int) -> ConversationState:
        if user_id not in self._states:
            self._states[user_id] = ConversationState()
        return self._states[user_id]

    def set_pending(self, user_id: int, pending: dict) -> None:
        self._states[user_id] = ConversationState(pending=pending)

    def clear(self, user_id: int) -> None:
        self._states[user_id] = ConversationState()
