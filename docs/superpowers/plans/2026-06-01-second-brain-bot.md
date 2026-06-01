# Second Brain Bot — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bot Telegram conversationnel qui capture des tâches via dialogue IA, les stocke dans Notion, et envoie un digest quotidien.

**Architecture:** Bot Python (python-telegram-bot) qui reçoit les messages, utilise Claude pour détecter l'intention et extraire les champs, puis écrit dans Notion via son API. L'état de conversation est maintenu en mémoire (dict Python). Le digest quotidien est déclenché par le job_queue intégré à python-telegram-bot.

**Tech Stack:** Python 3.11+, python-telegram-bot 21.x, anthropic SDK, notion-client, pytest

---

## Structure des fichiers

```
second_brain/
├── bot.py            ← point d'entrée, handlers Telegram, scheduler
├── conversation.py   ← état de conversation en mémoire
├── ai.py             ← appels Claude (classification, extraction, digest)
├── notion.py         ← CRUD Notion
├── config.py         ← chargement des variables d'environnement
├── pytest.ini        ← configuration pytest
├── requirements.txt
├── .env.example
├── railway.toml      ← déploiement Railway
└── tests/
    ├── test_conversation.py
    ├── test_ai.py
    └── test_notion.py
```

---

## Task 1 : Setup du projet

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Create: `pytest.ini`
- Create: `.env.example`
- Create: `railway.toml`

- [ ] **Step 1 : Créer requirements.txt**

```
python-telegram-bot[job-queue]==21.6
anthropic==0.40.0
notion-client==2.2.1
python-dotenv==1.0.1
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 2 : Créer config.py**

```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    telegram_token: str
    telegram_user_id: int
    anthropic_api_key: str
    notion_token: str
    notion_database_id: str
    digest_hour: int
    digest_minute: int

def load_config() -> Config:
    return Config(
        telegram_token=os.environ["TELEGRAM_TOKEN"],
        telegram_user_id=int(os.environ["TELEGRAM_USER_ID"]),
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        notion_token=os.environ["NOTION_TOKEN"],
        notion_database_id=os.environ["NOTION_DATABASE_ID"],
        digest_hour=int(os.environ.get("DIGEST_HOUR", "8")),
        digest_minute=int(os.environ.get("DIGEST_MINUTE", "0")),
    )
```

- [ ] **Step 3 : Créer pytest.ini**

```ini
[pytest]
pythonpath = .
asyncio_mode = auto
```

- [ ] **Step 4 : Créer .env.example**

```
TELEGRAM_TOKEN=your_bot_token_from_botfather
TELEGRAM_USER_ID=your_telegram_user_id
ANTHROPIC_API_KEY=your_anthropic_api_key
NOTION_TOKEN=your_notion_integration_token
NOTION_DATABASE_ID=your_notion_database_id
DIGEST_HOUR=8
DIGEST_MINUTE=0
```

- [ ] **Step 5 : Créer railway.toml**

```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "python bot.py"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

- [ ] **Step 6 : Installer les dépendances**

```bash
pip install -r requirements.txt
```

Résultat attendu : installation sans erreur.

- [ ] **Step 7 : Commit**

```bash
git init
git add requirements.txt config.py pytest.ini .env.example railway.toml
git commit -m "feat: setup initial du projet"
```

---

## Task 2 : ConversationManager

**Files:**
- Create: `conversation.py`
- Create: `tests/test_conversation.py`

- [ ] **Step 1 : Écrire les tests**

Créer `tests/test_conversation.py` :

```python
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
    mgr.start_capture(1, TaskDraft(name="Tâche A"), awaiting="importance")
    state_2 = mgr.get(2)
    assert state_2.mode == ConversationMode.IDLE
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
pytest tests/test_conversation.py -v
```

Résultat attendu : `ModuleNotFoundError: No module named 'conversation'`

- [ ] **Step 3 : Implémenter conversation.py**

```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class ConversationMode(Enum):
    IDLE = "idle"
    CAPTURING = "capturing"


@dataclass
class TaskDraft:
    name: Optional[str] = None
    importance: Optional[str] = None
    due_date: Optional[str] = None      # None=pas encore demandé, ""=ignoré
    category: Optional[str] = None     # None=pas encore demandé, ""=ignoré
    subcategory: Optional[str] = None  # None=pas encore demandé, ""=ignoré


@dataclass
class ConversationState:
    mode: ConversationMode = ConversationMode.IDLE
    draft: Optional[TaskDraft] = None
    awaiting: Optional[str] = None


class ConversationManager:
    def __init__(self):
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
        setattr(state.draft, field, value)
        state.awaiting = None
        return state.draft

    def clear(self, user_id: int) -> None:
        self._states[user_id] = ConversationState()
```

- [ ] **Step 4 : Vérifier que les tests passent**

```bash
pytest tests/test_conversation.py -v
```

Résultat attendu : `5 passed`

- [ ] **Step 5 : Commit**

```bash
git add conversation.py tests/test_conversation.py
git commit -m "feat: ConversationManager avec état en mémoire"
```

---

## Task 3 : Client Notion

**Files:**
- Create: `notion.py`
- Create: `tests/test_notion.py`

- [ ] **Step 1 : Écrire les tests**

Créer `tests/test_notion.py` :

```python
from unittest.mock import MagicMock, patch
from notion import NotionClient
from conversation import TaskDraft


def _make_client() -> tuple[NotionClient, MagicMock]:
    with patch("notion.Client") as MockClient:
        mock_instance = MockClient.return_value
        client = NotionClient(token="fake", database_id="db123")
        return client, mock_instance


def test_create_task_sets_mandatory_properties():
    with patch("notion.Client") as MockClient:
        mock_instance = MockClient.return_value
        client = NotionClient(token="fake", database_id="db123")
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
        assert props["Statut"]["select"]["name"] == "À faire"


def test_create_task_includes_due_date_when_present():
    with patch("notion.Client") as MockClient:
        mock_instance = MockClient.return_value
        client = NotionClient(token="fake", database_id="db123")
        draft = TaskDraft(name="Test", importance="Basse", due_date="2026-06-15", category="", subcategory="")
        client.create_task(draft)
        props = mock_instance.pages.create.call_args.kwargs["properties"]
        assert props["Date limite"]["date"]["start"] == "2026-06-15"


def test_create_task_skips_empty_optional_fields():
    with patch("notion.Client") as MockClient:
        mock_instance = MockClient.return_value
        client = NotionClient(token="fake", database_id="db123")
        draft = TaskDraft(name="Test", importance="Basse", due_date="", category="", subcategory="")
        client.create_task(draft)
        props = mock_instance.pages.create.call_args.kwargs["properties"]
        assert "Date limite" not in props
        assert "Catégorie" not in props


def test_page_to_dict_extracts_fields():
    with patch("notion.Client"):
        client = NotionClient(token="fake", database_id="db123")
        page = {
            "properties": {
                "Nom": {"title": [{"text": {"content": "Ma tâche"}}]},
                "Statut": {"select": {"name": "À faire"}},
                "Importance": {"select": {"name": "Haute"}},
                "Date limite": {"date": {"start": "2026-06-15"}},
                "Catégorie": {"select": {"name": "Code"}},
                "Sous-catégorie": {"select": None},
            }
        }
        result = client._page_to_dict(page)
        assert result["nom"] == "Ma tâche"
        assert result["importance"] == "Haute"
        assert result["date_limite"] == "2026-06-15"
        assert result["categorie"] == "Code"
        assert result["sous_categorie"] is None
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
pytest tests/test_notion.py -v
```

Résultat attendu : `ModuleNotFoundError: No module named 'notion'`

- [ ] **Step 3 : Implémenter notion.py**

```python
from notion_client import Client
from conversation import TaskDraft


class NotionClient:
    def __init__(self, token: str, database_id: str):
        self._client = Client(auth=token)
        self._db_id = database_id

    def create_task(self, draft: TaskDraft) -> None:
        properties = {
            "Nom": {"title": [{"text": {"content": draft.name}}]},
            "Statut": {"select": {"name": "À faire"}},
            "Importance": {"select": {"name": draft.importance}},
        }
        if draft.due_date:
            properties["Date limite"] = {"date": {"start": draft.due_date}}
        if draft.category:
            properties["Catégorie"] = {"select": {"name": draft.category}}
        if draft.subcategory:
            properties["Sous-catégorie"] = {"select": {"name": draft.subcategory}}

        self._client.pages.create(
            parent={"database_id": self._db_id},
            properties=properties,
        )

    def query_active_tasks(self) -> list[dict]:
        response = self._client.databases.query(
            database_id=self._db_id,
            filter={"property": "Statut", "select": {"does_not_equal": "Fait"}},
            sorts=[{"property": "Date limite", "direction": "ascending"}],
        )
        return [self._page_to_dict(p) for p in response["results"]]

    def _page_to_dict(self, page: dict) -> dict:
        props = page["properties"]
        return {
            "nom": props["Nom"]["title"][0]["text"]["content"] if props["Nom"]["title"] else "",
            "statut": props["Statut"]["select"]["name"] if props["Statut"]["select"] else "",
            "importance": props["Importance"]["select"]["name"] if props["Importance"]["select"] else "",
            "date_limite": props["Date limite"]["date"]["start"] if props["Date limite"]["date"] else None,
            "categorie": props["Catégorie"]["select"]["name"] if props["Catégorie"]["select"] else None,
            "sous_categorie": props["Sous-catégorie"]["select"]["name"] if props["Sous-catégorie"]["select"] else None,
        }
```

- [ ] **Step 4 : Vérifier que les tests passent**

```bash
pytest tests/test_notion.py -v
```

Résultat attendu : `4 passed`

- [ ] **Step 5 : Commit**

```bash
git add notion.py tests/test_notion.py
git commit -m "feat: client Notion (create + query)"
```

---

## Task 4 : Client IA (ai.py)

**Files:**
- Create: `ai.py`
- Create: `tests/test_ai.py`

- [ ] **Step 1 : Écrire les tests (fonctions pures uniquement — pas d'appels API)**

Créer `tests/test_ai.py` :

```python
from conversation import TaskDraft
from ai import get_next_question, QUESTIONS


def test_get_next_question_asks_name_first():
    draft = TaskDraft(name=None, importance=None)
    field, question = get_next_question(draft)
    assert field == "name"


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
    draft = TaskDraft(name="Appeler comptable", importance="Haute", due_date="2026-06-15")
    field, _ = get_next_question(draft)
    assert field == "category"


def test_get_next_question_returns_none_when_complete():
    draft = TaskDraft(name="Appeler comptable", importance="Haute", due_date="", category="")
    result = get_next_question(draft)
    assert result is None


def test_get_next_question_returns_none_with_all_optional_skipped():
    draft = TaskDraft(name="Tâche", importance="Basse", due_date="2026-07-01", category="Code", subcategory="")
    result = get_next_question(draft)
    assert result is None


def test_questions_dict_covers_all_fields():
    for field in ["name", "importance", "due_date", "category"]:
        assert field in QUESTIONS
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
pytest tests/test_ai.py -v
```

Résultat attendu : `ModuleNotFoundError: No module named 'ai'`

- [ ] **Step 3 : Implémenter ai.py**

```python
import json
from datetime import date
from typing import Optional
from anthropic import Anthropic
from conversation import TaskDraft

QUESTIONS = {
    "name": "Quelle est la tâche ?",
    "importance": "Quelle importance ? (Haute / Moyenne / Basse)",
    "due_date": "Une date limite ? (ou 'aucune')",
    "category": "Une catégorie ? (Conférences / Social / Code — ou 'aucune')",
}

CLASSIFY_PROMPT = """Tu es un assistant de gestion de tâches personnel.
Analyse le message et retourne UNIQUEMENT du JSON valide, sans texte avant ou après.

Format requis :
{{
  "intent": "new_task" ou "query",
  "draft": {{
    "name": "titre concis ou null",
    "importance": "Haute" ou "Moyenne" ou "Basse" ou null,
    "due_date": "YYYY-MM-DD ou null",
    "category": "Conférences" ou "Social" ou "Code" ou null,
    "subcategory": null
  }},
  "query": "question reformulée si intent=query, sinon null"
}}

Règles :
- intent=new_task si le message décrit quelque chose à faire
- intent=query si le message pose une question sur les tâches existantes
- due_date : convertis les dates relatives en YYYY-MM-DD. Aujourd'hui = {today}
- importance : déduis du contexte ("urgent" → Haute, "quand possible" → Basse)
- draft est toujours présent même si intent=query (null pour tous les champs)"""

DIGEST_SYSTEM = """Tu génères un digest matinal de tâches. Sois concis.
Commence par "Bonjour — voici tes tâches :"
🔴 Haute importance  🟡 Moyenne  ⚪ Basse
Maximum 5 tâches, priorisées par importance puis date limite.
Réponds uniquement avec le digest, en français."""


def get_next_question(draft: TaskDraft) -> Optional[tuple[str, str]]:
    if not draft.name:
        return ("name", QUESTIONS["name"])
    if not draft.importance:
        return ("importance", QUESTIONS["importance"])
    if draft.due_date is None:
        return ("due_date", QUESTIONS["due_date"])
    if draft.category is None:
        return ("category", QUESTIONS["category"])
    return None


class AiClient:
    def __init__(self, api_key: str):
        self._client = Anthropic(api_key=api_key)

    def classify(self, message: str) -> dict:
        today = date.today().isoformat()
        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=CLASSIFY_PROMPT.format(today=today),
            messages=[{"role": "user", "content": message}],
        )
        return json.loads(response.content[0].text)

    def extract_field(self, field: str, question: str, answer: str) -> str:
        today = date.today().isoformat()
        prompt = (
            f'L\'utilisateur répondait à : "{question}"\n'
            f'Sa réponse : "{answer}"\n'
            f"Champ à extraire : {field}\n"
            f"Aujourd'hui = {today}\n"
            "Retourne UNIQUEMENT du JSON : {\"value\": \"valeur ou vide\"}\n"
            "Pour 'aucune', 'non', 'pas de', 'skip' → retourne {\"value\": \"\"}\n"
            "Pour importance → valide parmi : Haute, Moyenne, Basse\n"
            "Pour due_date → format YYYY-MM-DD"
        )
        response = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        result = json.loads(response.content[0].text)
        return result.get("value", "")

    def answer_query(self, query: str, tasks: list[dict]) -> str:
        tasks_text = json.dumps(tasks, ensure_ascii=False, indent=2)
        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system="Tu es un assistant de gestion de tâches personnel. Réponds en français, de façon concise (5 lignes max).",
            messages=[{"role": "user", "content": f"Question : {query}\n\nTâches :\n{tasks_text}"}],
        )
        return response.content[0].text

    def generate_digest(self, tasks: list[dict]) -> str:
        if not tasks:
            return "Bonjour — aucune tâche active pour l'instant. 🎉"
        tasks_text = json.dumps(tasks, ensure_ascii=False, indent=2)
        response = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=DIGEST_SYSTEM,
            messages=[{"role": "user", "content": tasks_text}],
        )
        return response.content[0].text
```

- [ ] **Step 4 : Vérifier que les tests passent**

```bash
pytest tests/test_ai.py -v
```

Résultat attendu : `7 passed`

- [ ] **Step 5 : Commit**

```bash
git add ai.py tests/test_ai.py
git commit -m "feat: client IA — classification, extraction, digest"
```

---

## Task 5 : Bot Telegram (bot.py)

**Files:**
- Create: `bot.py`

Pas de tests automatisés pour le handler Telegram (dépend de l'API Telegram). Le test est manuel.

- [ ] **Step 1 : Créer bot.py**

```python
import logging
from datetime import time as dt_time
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from config import load_config
from conversation import ConversationManager, ConversationMode, TaskDraft
from ai import AiClient, get_next_question, QUESTIONS
from notion import NotionClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = load_config()
conversation_manager = ConversationManager()
ai_client = AiClient(api_key=config.anthropic_api_key)
notion_client = NotionClient(token=config.notion_token, database_id=config.notion_database_id)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.telegram_user_id:
        return
    text = update.message.text
    user_id = update.effective_user.id
    state = conversation_manager.get(user_id)

    if state.mode == ConversationMode.CAPTURING:
        await _handle_capture_reply(update, text, user_id, state)
    else:
        await _handle_new_message(update, text, user_id)


async def _handle_new_message(update: Update, text: str, user_id: int) -> None:
    result = ai_client.classify(text)
    if result["intent"] == "new_task":
        raw = result.get("draft", {})
        draft = TaskDraft(
            name=raw.get("name") or None,
            importance=raw.get("importance") or None,
            due_date=raw.get("due_date"),
            category=raw.get("category"),
            subcategory=raw.get("subcategory"),
        )
        next_q = get_next_question(draft)
        if next_q is None:
            await _save_and_confirm(update, draft, user_id)
        else:
            field, question = next_q
            conversation_manager.start_capture(user_id, draft, awaiting=field)
            await update.message.reply_text(question)
    else:
        tasks = notion_client.query_active_tasks()
        answer = ai_client.answer_query(result.get("query") or text, tasks)
        await update.message.reply_text(answer)


async def _handle_capture_reply(update: Update, text: str, user_id: int, state) -> None:
    field = state.awaiting
    question = QUESTIONS.get(field, f"Valeur pour {field} ?")
    value = ai_client.extract_field(field, question, text)
    draft = conversation_manager.update_field(user_id, field, value)
    next_q = get_next_question(draft)
    if next_q is None:
        conversation_manager.clear(user_id)
        await _save_and_confirm(update, draft, user_id)
    else:
        field2, question2 = next_q
        state.awaiting = field2
        await update.message.reply_text(question2)


async def _save_and_confirm(update: Update, draft: TaskDraft, user_id: int) -> None:
    notion_client.create_task(draft)
    parts = [f"✓ {draft.name}", draft.importance or ""]
    if draft.due_date:
        parts.append(draft.due_date)
    if draft.category:
        parts.append(draft.category)
    await update.message.reply_text(" · ".join(p for p in parts if p))


async def _send_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    tasks = notion_client.query_active_tasks()
    digest = ai_client.generate_digest(tasks)
    await context.bot.send_message(chat_id=config.telegram_user_id, text=digest)


def main() -> None:
    app = Application.builder().token(config.telegram_token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    digest_time = dt_time(hour=config.digest_hour, minute=config.digest_minute)
    app.job_queue.run_daily(_send_digest, time=digest_time)
    logger.info("Bot démarré")
    app.run_polling()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2 : Préparer la base Notion**

Dans Notion :
1. Créer une page "Second Brain"
2. Créer une base de données "Tâches" avec les propriétés :
   - **Nom** : Title (déjà présent par défaut)
   - **Statut** : Select → ajouter : À faire, En cours, Bloqué, Fait
   - **Importance** : Select → ajouter : Haute, Moyenne, Basse
   - **Date limite** : Date
   - **Catégorie** : Select → ajouter : Conférences, Social, Code
   - **Sous-catégorie** : Select (laisser vide)
3. Récupérer l'ID de la base : dans l'URL Notion, c'est la chaîne de 32 caractères après le dernier `/` et avant le `?`

- [ ] **Step 3 : Créer le bot Telegram et obtenir les tokens**

1. Ouvrir Telegram → chercher **@BotFather**
2. Envoyer `/newbot` → donner un nom et un username → récupérer le `TELEGRAM_TOKEN`
3. Chercher **@userinfobot** → lui envoyer n'importe quel message → récupérer son `TELEGRAM_USER_ID`
4. Créer une intégration Notion : `notion.so/my-integrations` → New integration → récupérer le `NOTION_TOKEN`
5. Partager la base de données Notion avec l'intégration (bouton "Share" dans Notion → ajouter l'intégration)

- [ ] **Step 4 : Créer le fichier .env**

Copier `.env.example` en `.env` et remplir les valeurs :

```
TELEGRAM_TOKEN=<token_de_botfather>
TELEGRAM_USER_ID=<ton_id_telegram>
ANTHROPIC_API_KEY=<ta_clé_anthropic>
NOTION_TOKEN=<token_integration_notion>
NOTION_DATABASE_ID=<id_base_taches>
DIGEST_HOUR=8
DIGEST_MINUTE=0
```

- [ ] **Step 5 : Lancer le bot en local et tester manuellement**

```bash
python bot.py
```

Résultat attendu dans le terminal : `Bot démarré`

Tester dans Telegram :
- Envoyer "je dois préparer ma conférence pour juin" → le bot doit demander l'importance
- Répondre "haute" → le bot doit demander une date
- Répondre "aucune" → le bot doit demander une catégorie
- Répondre "Conférences" → le bot doit confirmer : `✓ Préparer ma conférence · Haute · Conférences`
- Vérifier que la tâche apparaît dans Notion
- Envoyer "quelles sont mes tâches urgentes ?" → le bot doit répondre avec les tâches Haute

Arrêter avec `Ctrl+C`.

- [ ] **Step 6 : Commit**

```bash
git add bot.py .env.example
git commit -m "feat: bot Telegram complet avec capture conversationnelle et digest"
```

---

## Task 6 : Déploiement Railway

**Files:**
- `railway.toml` (déjà créé en Task 1)
- `.gitignore` (à créer)

- [ ] **Step 1 : Créer .gitignore**

```
.env
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 2 : Pousser le code sur GitHub**

```bash
git add .gitignore
git commit -m "chore: gitignore"
# Créer un repo GitHub (via github.com ou gh CLI)
git remote add origin https://github.com/<ton-username>/second-brain-bot.git
git push -u origin main
```

- [ ] **Step 3 : Créer le projet Railway**

1. Aller sur [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
2. Sélectionner le repo `second-brain-bot`
3. Railway détecte le `railway.toml` automatiquement

- [ ] **Step 4 : Configurer les variables d'environnement dans Railway**

Dans Railway → ton projet → Variables → ajouter chaque variable de `.env` :
- `TELEGRAM_TOKEN`
- `TELEGRAM_USER_ID`
- `ANTHROPIC_API_KEY`
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID`
- `DIGEST_HOUR`
- `DIGEST_MINUTE`

- [ ] **Step 5 : Vérifier le déploiement**

Dans Railway → Deployments → voir les logs. Attendre le message `Bot démarré`.

Tester depuis Telegram : envoyer un message au bot et vérifier qu'il répond.

- [ ] **Step 6 : Commit final**

```bash
git add .
git commit -m "chore: configuration déploiement Railway"
git push
```

---

## Vérification finale

- [ ] Tous les tests passent : `pytest tests/ -v` → `16 passed`
- [ ] Le bot répond en local avant déploiement
- [ ] Les tâches créées apparaissent dans Notion
- [ ] Le bot déployé répond depuis Telegram
