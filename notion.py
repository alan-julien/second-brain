from notion_client import Client


TITLE_FIELDS = ("Nom", "Name", "Tache", "Tâche", "Task")
STATUS_FIELDS = ("Statut", "Status")
IMPORTANCE_FIELDS = ("Importance", "Priorite", "Priorité", "Priority")
DATE_FIELDS = ("Date limite", "Date Limite", "Deadline", "Due date", "Due")
CATEGORY_FIELDS = ("Categorie", "Catégorie", "Category")
SUBCATEGORY_FIELDS = ("Sous-categorie", "Sous-catégorie", "Subcategory")
EFFORT_FIELDS = ("Effort",)


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
            "status": ("Statut", {"select": {"name": value}}),
        }
        if field not in field_map:
            return
        notion_field, notion_value = field_map[field]
        self._client.pages.update(
            page_id=page_id,
            properties={notion_field: notion_value},
        )

    def query_active_tasks(self) -> list[dict]:
        # Filtrer/trier côté Python évite qu'un changement de schéma Notion
        # (colonne renommée ou absente) casse tout le bot au moment de recevoir
        # un message Telegram.
        tasks = [self._page_to_dict(page) for page in self._query_pages()]
        active_tasks = [task for task in tasks if task.get("statut") != "Fait"]
        return _sort_tasks_by_due_date(active_tasks)

    def query_reference_tasks(self) -> list[dict]:
        """Retourne assez de contexte pour cibler une tache.

        Les actions de correction peuvent viser une tache deja marquee Fait
        (ex. « finalement marque-la bloquee »). Le digest reste base sur
        query_active_tasks(), mais le flux conversationnel donne a l'IA une
        liste de reference incluant les taches terminees afin que Python puisse
        remapper un numero vers l'ID Notion reel.
        """
        tasks = [self._page_to_dict(page) for page in self._query_pages()]
        return _sort_tasks_by_due_date(tasks)

    def _query_pages(self) -> list[dict]:
        results = []
        start_cursor = None
        while True:
            kwargs = {"database_id": self._db_id}
            if start_cursor:
                kwargs["start_cursor"] = start_cursor
            response = self._client.databases.query(**kwargs)
            results.extend(response.get("results", []))
            if not response.get("has_more"):
                return results
            start_cursor = response.get("next_cursor")

    def _page_to_dict(self, page: dict) -> dict:
        props = page.get("properties", {})
        return {
            "id": page["id"],
            "nom": _title_value(_first_prop(props, TITLE_FIELDS)),
            "statut": _select_value(_first_prop(props, STATUS_FIELDS)) or "",
            "importance": _select_value(_first_prop(props, IMPORTANCE_FIELDS)) or "",
            "date_limite": _date_value(_first_prop(props, DATE_FIELDS)),
            "categorie": _select_value(_first_prop(props, CATEGORY_FIELDS)),
            "sous_categorie": _select_value(_first_prop(props, SUBCATEGORY_FIELDS)),
            "effort": _select_value(_first_prop(props, EFFORT_FIELDS)),
        }


def _first_prop(props: dict, names: tuple[str, ...]) -> dict:
    for name in names:
        if name in props:
            return props[name] or {}
    return {}


def _sort_tasks_by_due_date(tasks: list[dict]) -> list[dict]:
    return sorted(tasks, key=lambda task: task.get("date_limite") or "9999-12-31")


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
