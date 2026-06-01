from dataclasses import dataclass
from enum import Enum


class ConversationMode(Enum):
    IDLE = "idle"
    CAPTURING = "capturing"


@dataclass
class TaskDraft:
    name: str | None = None
    importance: str | None = None
    due_date: str | None = None
    category: str | None = None
    subcategory: str | None = None


@dataclass
class ConversationState:
    mode: ConversationMode = ConversationMode.IDLE
    draft: TaskDraft | None = None
    awaiting: str | None = None


class ConversationManager:
    def __init__(self) -> None:
        self._states: dict[int, ConversationState] = {}

    def get(self, user_id: int) -> ConversationState:
        if user_id not in self._states:
            self._states[user_id] = ConversationState()
        return self._states[user_id]

    def start_capture(self, user_id: int, draft: TaskDraft, awaiting: str) -> None:
        self._states[user_id] = ConversationState(
            mode=ConversationMode.CAPTURING,
            draft=draft,
            awaiting=awaiting,
        )

    def update_field(self, user_id: int, field: str, value: str) -> TaskDraft:
        state = self.get(user_id)
        if state.draft is None:
            state.draft = TaskDraft()
        setattr(state.draft, field, value)
        state.awaiting = None
        return state.draft

    def clear(self, user_id: int) -> None:
        self._states[user_id] = ConversationState()
