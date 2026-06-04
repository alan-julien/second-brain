from notion_client import Client


class NotionClient:
    def __init__(self, token: str, database_id: str):
        self._client = Client(auth=token)
        self._db_id = database_id

    def create_task(self, draft) -> None:
        properties = {
            "Nom": {"title": [{"text": {"content": draft.name}}]},
            "Statut": {"select": {"name": "A faire"}},
            "Importance": {"select": {"name": draft.importance}},
        }

        if draft.due_date:
            properties["Date limite"] = {"date": {"start": draft.due_date}}
        if draft.category:
            properties["Categorie"] = {"select": {"name": draft.category}}
        if draft.subcategory:
            properties["Sous-categorie"] = {"select": {"name": draft.subcategory}}
        if draft.effort:
            properties["Effort"] = {"select": {"name": draft.effort}}

        self._client.pages.create(
            parent={"database_id": self._db_id},
            properties=properties,
        )

    def complete_task(self, page_id: str) -> None:
        self._client.pages.update(
            page_id=page_id,
            properties={"Statut": {"select": {"name": "Fait"}}},
        )

    def update_task_field(self, page_id: str, field: str, value: str) -> None:
        field_map = {
            "due_date": ("Date limite", {"date": {"start": value}}),
            "importance": ("Importance", {"select": {"name": value}}),
            "category": ("Categorie", {"select": {"name": value}}),
            "effort": ("Effort", {"select": {"name": value}}),
        }
        if field not in field_map:
            return
        notion_field, notion_value = field_map[field]
        self._client.pages.update(
            page_id=page_id,
            properties={notion_field: notion_value},
        )

    def query_active_tasks(self) -> list[dict]:
        response = self._client.databases.query(
            database_id=self._db_id,
            filter={"property": "Statut", "select": {"does_not_equal": "Fait"}},
            sorts=[{"property": "Date limite", "direction": "ascending"}],
        )
        return [self._page_to_dict(page) for page in response["results"]]

    def _page_to_dict(self, page: dict) -> dict:
        props = page["properties"]
        return {
            "id": page["id"],
            "nom": _title_value(props["Nom"]),
            "statut": _select_value(props["Statut"]) or "",
            "importance": _select_value(props["Importance"]) or "",
            "date_limite": _date_value(props["Date limite"]),
            "categorie": _select_value(props["Categorie"]),
            "sous_categorie": _select_value(props["Sous-categorie"]),
            "effort": _select_value(props["Effort"]),
        }


def _title_value(property_value: dict) -> str:
    title = property_value.get("title") or []
    if not title:
        return ""
    return title[0].get("text", {}).get("content", "")


def _select_value(property_value: dict) -> str | None:
    selected = property_value.get("select")
    if not selected:
        return None
    return selected.get("name")


def _date_value(property_value: dict) -> str | None:
    date_value = property_value.get("date")
    if not date_value:
        return None
    return date_value.get("start")
