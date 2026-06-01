from conversation import TaskDraft
from ai import QUESTIONS, _parse_json_response, get_next_question


def test_get_next_question_asks_name_first():
    draft = TaskDraft(name=None, importance=None)

    field, question = get_next_question(draft)

    assert field == "name"
    assert question == QUESTIONS["name"]


def test_get_next_question_asks_importance_when_name_present():
    draft = TaskDraft(name="Appeler comptable", importance=None)

    field, question = get_next_question(draft)

    assert field == "importance"
    assert "Haute" in question


def test_get_next_question_asks_due_date_after_importance():
    draft = TaskDraft(name="Appeler comptable", importance="Haute")

    field, _ = get_next_question(draft)

    assert field == "due_date"


def test_get_next_question_asks_category_after_due_date():
    draft = TaskDraft(
        name="Appeler comptable",
        importance="Haute",
        due_date="2026-06-15",
    )

    field, _ = get_next_question(draft)

    assert field == "category"


def test_get_next_question_returns_none_when_complete():
    draft = TaskDraft(
        name="Appeler comptable",
        importance="Haute",
        due_date="",
        category="",
    )

    result = get_next_question(draft)

    assert result is None


def test_get_next_question_asks_subcategory_when_category_is_pro():
    draft = TaskDraft(
        name="Appeler client",
        importance="Haute",
        due_date="",
        category="Pro",
        subcategory=None,
    )

    field, question = get_next_question(draft)

    assert field == "subcategory"
    assert "TSE" in question
    assert "Labo" in question


def test_get_next_question_returns_none_with_all_optional_skipped():
    draft = TaskDraft(
        name="Tâche",
        importance="Basse",
        due_date="2026-07-01",
        category="Code",
        subcategory="",
    )

    result = get_next_question(draft)

    assert result is None


def test_questions_dict_covers_all_fields():
    for field in ["name", "importance", "due_date", "category", "subcategory"]:
        assert field in QUESTIONS


def test_parse_json_response_accepts_markdown_json_fence():
    result = _parse_json_response(
        '```json\n{"intent": "new_task", "draft": {}, "query": null}\n```'
    )

    assert result["intent"] == "new_task"
