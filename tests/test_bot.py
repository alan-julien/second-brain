import bot


def test_resolve_ref_maps_number_to_real_task():
    tasks = [{"id": "a", "nom": "T1"}, {"id": "b", "nom": "T2"}]
    assert bot._resolve_ref(2, tasks)["id"] == "b"


def test_resolve_ref_rejects_out_of_range():
    tasks = [{"id": "a"}]
    assert bot._resolve_ref(5, tasks) is None
    assert bot._resolve_ref(0, tasks) is None


def test_resolve_ref_rejects_non_numeric():
    assert bot._resolve_ref(None, [{"id": "a"}]) is None
    assert bot._resolve_ref("abc", [{"id": "a"}]) is None


def test_valid_update_checks_enums_and_date():
    assert bot._valid_update("importance", "Haute") is True
    assert bot._valid_update("importance", "Critique") is False
    assert bot._valid_update("category", "Code") is True
    assert bot._valid_update("category", "Perso") is True
    assert bot._valid_update("category", "Inconnue") is False
    assert bot._valid_update("status", "Bloque") is True
    assert bot._valid_update("status", "Archive") is False
    assert bot._valid_update("due_date", "2026-06-15") is True
    assert bot._valid_update("due_date", "demain") is False
    assert bot._valid_update("name", "x") is False  # champ non modifiable


def test_validated_draft_drops_invalid_values():
    draft = bot._validated_draft(
        {
            "name": "Tache",
            "importance": "n'importe quoi",
            "due_date": "pas une date",
            "category": "Inconnue",
            "subcategory": "XYZ",
        }
    )
    assert draft.name == "Tache"
    assert draft.importance is None
    assert draft.due_date is None
    assert draft.category is None
    assert draft.subcategory is None


def test_validated_draft_keeps_valid_values():
    draft = bot._validated_draft(
        {
            "name": "Tache",
            "importance": "Haute",
            "due_date": "2026-06-15",
            "category": "Pro",
            "subcategory": "TSE",
        }
    )
    assert draft.importance == "Haute"
    assert draft.due_date == "2026-06-15"
    assert draft.category == "Pro"
    assert draft.subcategory == "TSE"
