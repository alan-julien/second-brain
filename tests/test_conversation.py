from conversation import ConversationManager, ConversationMode, TaskDraft


def test_new_manager_returns_idle_state():
    mgr = ConversationManager()
    state = mgr.get(42)
    assert state.mode == ConversationMode.IDLE
    assert state.draft is None
    assert state.awaiting is None


def test_start_capture_sets_mode_draft_and_awaiting():
    mgr = ConversationManager()
    draft = TaskDraft(name="Appeler comptable", importance=None)
    mgr.start_capture(42, draft, awaiting="importance")
    state = mgr.get(42)
    assert state.mode == ConversationMode.CAPTURING
    assert state.draft.name == "Appeler comptable"
    assert state.awaiting == "importance"


def test_update_field_sets_value_and_clears_awaiting():
    mgr = ConversationManager()
    draft = TaskDraft(name="Appeler comptable", importance=None)
    mgr.start_capture(42, draft, awaiting="importance")
    updated = mgr.update_field(42, "importance", "Haute")
    assert updated.importance == "Haute"
    assert mgr.get(42).awaiting is None


def test_clear_resets_to_idle():
    mgr = ConversationManager()
    mgr.start_capture(42, TaskDraft(name="x"), awaiting="importance")
    mgr.clear(42)
    state = mgr.get(42)
    assert state.mode == ConversationMode.IDLE
    assert state.draft is None


def test_two_users_have_independent_states():
    mgr = ConversationManager()
    mgr.start_capture(1, TaskDraft(name="Tache A"), awaiting="importance")
    state_2 = mgr.get(2)
    assert state_2.mode == ConversationMode.IDLE
