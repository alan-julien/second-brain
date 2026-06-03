from unittest.mock import MagicMock, patch

from conversation import TaskDraft
from notion import NotionClient


def _make_page() -> dict:
    return {
        "id": "page-123",
        "properties": {
            "Nom": {"title": [{"text": {"content": "Ma tache"}}]},
            "Statut": {"select": {"name": "A faire"}},
            "Importance": {"select": {"name": "Haute"}},
            "Date limite": {"date": {"start": "2026-06-15"}},
            "Categorie": {"select": {"name": "Code"}},
            "Sous-categorie": {"select": None},
        }
    }


def _make_client() -> tuple[NotionClient, MagicMock]:
    with patch("notion.Client") as MockClient:
        mock_instance = MockClient.return_value
        client = NotionClient(token="fake", database_id="db123")
        return client, mock_instance


def test_create_task_sets_mandatory_properties():
    client, mock_instance = _make_client()
    draft = TaskDraft(
        name="Appeler comptable",
        importance="Haute",
        due_date="",
        category="",
        subcategory="",
    )

    client.create_task(draft)

    props = mock_instance.pages.create.call_args.kwargs["properties"]
    assert props["Nom"]["title"][0]["text"]["content"] == "Appeler comptable"
    assert props["Importance"]["select"]["name"] == "Haute"
    assert props["Statut"]["select"]["name"] == "A faire"


def test_create_task_includes_due_date_when_present():
    client, mock_instance = _make_client()
    draft = TaskDraft(
        name="Test",
        importance="Basse",
        due_date="2026-06-15",
        category="",
        subcategory="",
    )

    client.create_task(draft)

    props = mock_instance.pages.create.call_args.kwargs["properties"]
    assert props["Date limite"]["date"]["start"] == "2026-06-15"


def test_create_task_includes_category_and_subcategory_when_present():
    client, mock_instance = _make_client()
    draft = TaskDraft(
        name="Point projet",
        importance="Moyenne",
        due_date="",
        category="Pro",
        subcategory="TSE",
    )

    client.create_task(draft)

    props = mock_instance.pages.create.call_args.kwargs["properties"]
    assert props["Categorie"]["select"]["name"] == "Pro"
    assert props["Sous-categorie"]["select"]["name"] == "TSE"


def test_create_task_skips_empty_optional_fields():
    client, mock_instance = _make_client()
    draft = TaskDraft(
        name="Test",
        importance="Basse",
        due_date="",
        category="",
        subcategory="",
    )

    client.create_task(draft)

    props = mock_instance.pages.create.call_args.kwargs["properties"]
    assert "Date limite" not in props
    assert "Categorie" not in props
    assert "Sous-categorie" not in props


def test_query_active_tasks_filters_done_and_maps_results():
    with patch("notion.Client") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.databases.query.return_value = {"results": [_make_page()]}
        client = NotionClient(token="fake", database_id="db123")

        result = client.query_active_tasks()

        mock_instance.databases.query.assert_called_once_with(
            database_id="db123",
            filter={"property": "Statut", "select": {"does_not_equal": "Fait"}},
            sorts=[{"property": "Date limite", "direction": "ascending"}],
        )
        assert result[0]["nom"] == "Ma tache"


def test_page_to_dict_extracts_fields():
    with patch("notion.Client"):
        client = NotionClient(token="fake", database_id="db123")

        result = client._page_to_dict(_make_page())

        assert result["id"] == "page-123"
        assert result["nom"] == "Ma tache"
        assert result["statut"] == "A faire"
        assert result["importance"] == "Haute"
        assert result["date_limite"] == "2026-06-15"
        assert result["categorie"] == "Code"
        assert result["sous_categorie"] is None
