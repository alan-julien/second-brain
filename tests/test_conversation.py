from conversation import ConversationManager


def test_new_manager_returns_empty_state():
    mgr = ConversationManager()
    state = mgr.get(42)
    assert state.pending is None


def test_set_pending_stores_context():
    mgr = ConversationManager()
    mgr.set_pending(42, {"intent": "new_task", "draft": {"name": "Tache"}})
    state = mgr.get(42)
    assert state.pending["intent"] == "new_task"
    assert state.pending["draft"]["name"] == "Tache"


def test_clear_resets_pending():
    mgr = ConversationManager()
    mgr.set_pending(42, {"intent": "update_task"})
    mgr.clear(42)
    assert mgr.get(42).pending is None


def test_two_users_have_independent_states():
    mgr = ConversationManager()
    mgr.set_pending(1, {"intent": "new_task"})
    assert mgr.get(2).pending is None
