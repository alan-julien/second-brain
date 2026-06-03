from unittest.mock import MagicMock, patch

from ai import AiClient, _format_tasks, _parse_json_response


def test_parse_json_response_accepts_markdown_json_fence():
    result = _parse_json_response(
        '```json\n{"intent": "new_task", "ready": true, "reply": "ok"}\n```'
    )

    assert result["intent"] == "new_task"


def test_format_tasks_numbers_from_one_and_hides_ids():
    tasks = [
        {"id": "abc", "nom": "Tache A", "importance": "Haute", "date_limite": "2026-06-03", "categorie": "Code"},
        {"id": "def", "nom": "Tache B", "importance": "Basse", "date_limite": None, "categorie": None},
    ]

    text = _format_tasks(tasks)

    assert text.startswith("1 | Tache A")
    assert "2 | Tache B" in text
    assert "sans date" in text and "sans categorie" in text
    assert "abc" not in text and "def" not in text  # les ID Notion ne fuitent jamais vers l'IA


def test_format_tasks_handles_empty_list():
    assert _format_tasks([]) == "(aucune tache active)"


def test_decide_parses_structured_decision():
    with patch("ai.Anthropic") as MockAnthropic:
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"intent": "complete_task", "target_ref": 2, "ready": true, "reply": "Fait !"}')]
        MockAnthropic.return_value.messages.create.return_value = mock_msg
        client = AiClient(api_key="fake", model="claude-haiku-4-5")

        decision = client.decide("termine la tache 2", tasks=[{"id": "x", "nom": "T"}], pending=None)

        assert decision["intent"] == "complete_task"
        assert decision["target_ref"] == 2
        assert decision["ready"] is True
