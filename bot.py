import logging
import re
import unicodedata
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ai import AiClient, IMPORTANCES, CATEGORIES, SUBCATEGORIES, EFFORTS, STATUSES
from config import load_config
from conversation import ConversationManager, TaskDraft
from notion import NotionClient


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = load_config()
conversation_manager = ConversationManager()
ai_client = AiClient(api_key=config.anthropic_api_key, model=config.anthropic_model)
notion_client = NotionClient(
    token=config.notion_token,
    database_id=config.notion_database_id,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CONFIRMATION_RE = re.compile(r"\b(oui|yes|ok|confirme|c'est ca|cest ca|exact|exactement)\b")
_COMPLETION_RE = re.compile(r"\b(fait|faits|faite|faites|fini|finie|finis|finies|termine|terminee|termines|terminees|ok)\b")
_OVERDUE_ACTION_RE = re.compile(r"\b(supprime|supprimer|enleve|enlever|retire|retirer|efface|effacer|termine|terminer|marque|marquer)\w*\b")

_TASK_STOPWORDS = {
    "a",
    "au",
    "aux",
    "de",
    "des",
    "du",
    "la",
    "le",
    "les",
    "l",
    "un",
    "une",
    "pour",
    "avec",
    "chez",
    "dans",
    "sur",
    "et",
    "ou",
    "faire",
    "fait",
    "faite",
    "fini",
    "finie",
    "termine",
    "terminee",
    "terminer",
    "marquer",
    "marque",
    "supprimer",
    "supprime",
    "retirer",
    "retire",
    "envoyer",
    "venir",
    "chercher",
    "ramener",
    "prendre",
    "demander",
    "appeler",
    "contacter",
    "repondre",
    "reserver",
    "organiser",
}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    user_id = update.effective_user.id
    if user_id != config.telegram_user_id:
        logger.warning("Unauthorized Telegram user ignored: %s", user_id)
        return

    text = update.message.text or ""
    try:
        await _handle(update, text, user_id)
    except Exception as exc:
        await _reply_technical_error(update, exc)


async def _handle(update: Update, text: str, user_id: int) -> None:
    """Flux 'cerveau unique' : Python execute les cas a risque, l'IA gere le reste."""
    state = conversation_manager.get(user_id)
    try:
        tasks = notion_client.query_reference_tasks()
        if await _try_handle_deterministic_task_action(update, user_id, text, tasks, state.pending):
            return

        decision = ai_client.decide(text, tasks, state.pending)
        decision = _apply_status_text_hints(text, decision)
    except Exception as exc:
        await _reply_technical_error(update, exc)
        return

    intent = decision.get("intent")
    reply = decision.get("reply") or "C'est note."

    # L'IA n'est pas sure / il manque une info -> on pose la question et on garde le fil.
    if not decision.get("ready"):
        conversation_manager.set_pending(user_id, _pending_from(decision))
        await update.message.reply_text(reply)
        return

    if intent == "new_task":
        await _do_new_task(update, user_id, decision, reply)
        return

    if intent in ("complete_task", "update_task"):
        await _do_task_action(update, user_id, decision, tasks, intent, reply)
        return

    # query / smalltalk : l'IA a deja redige la reponse a partir de la liste fournie.
    conversation_manager.clear(user_id)
    await update.message.reply_text(reply)


async def _reply_technical_error(update: Update, exc: Exception) -> None:
    logger.error("Erreur lors du traitement du message: %s", exc, exc_info=True)
    details = _safe_error_details(exc)
    await update.message.reply_text(f"Erreur technique: {details}")


def _safe_error_details(exc: Exception) -> str:
    details = f"{exc.__class__.__name__}: {exc}"
    for secret in (
        config.telegram_token,
        config.anthropic_api_key,
        config.notion_token,
        config.notion_database_id,
    ):
        if secret:
            details = details.replace(secret, "[secret]")
    return details[:700]


async def _try_handle_deterministic_task_action(
    update: Update, user_id: int, text: str, tasks: list[dict], pending: dict | None
) -> bool:
    """Execute les actions simples et dangereuses sans laisser l'IA tergiverser.

    Cas couverts :
    - « supprime les 3 en retard » : marque les taches en retard comme Fait.
    - « Vigne rouge et Castelli terminé » : complete plusieurs taches en une fois.
    - « oui » apres une confirmation multi-taches : execute vraiment l'action.
    """
    normalized = _normalize_text(text)

    if pending and pending.get("intent") == "bulk_complete" and _is_confirmation(normalized):
        selected = _tasks_from_pending(pending, tasks)
        if selected:
            _complete_tasks(selected)
            conversation_manager.clear(user_id)
            await update.message.reply_text(_completed_reply(selected))
            return True

    overdue = _overdue_tasks_to_complete(normalized, tasks)
    if overdue:
        _complete_tasks(overdue)
        conversation_manager.clear(user_id)
        await update.message.reply_text(_completed_reply(overdue, prefix="J'ai retire les taches en retard de ta liste active"))
        return True

    matched = _explicit_completed_tasks(normalized, tasks)
    if len(matched) >= 1:
        _complete_tasks(matched)
        conversation_manager.clear(user_id)
        await update.message.reply_text(_completed_reply(matched))
        return True

    return False


def _complete_tasks(tasks: list[dict]) -> None:
    seen_ids = set()
    for task in tasks:
        task_id = task.get("id")
        if not task_id or task_id in seen_ids:
            continue
        notion_client.complete_task(task_id)
        seen_ids.add(task_id)


def _completed_reply(tasks: list[dict], prefix: str = "J'ai marque comme terminee") -> str:
    names = [task.get("nom", "").strip() for task in tasks if task.get("nom")]
    if not names:
        return "C'est fait."
    if len(names) == 1:
        return f"{prefix} « {names[0]} ». ✓"

    bullet_list = "\n".join(f"- {name}" for name in names)
    return f"{prefix} ces {len(names)} taches :\n{bullet_list}\n✓"


def _tasks_from_pending(pending: dict, tasks: list[dict]) -> list[dict]:
    pending_ids = set(pending.get("target_ids") or [])
    if pending_ids:
        return [task for task in tasks if task.get("id") in pending_ids and task.get("statut") != "Fait"]

    refs = pending.get("target_refs") or []
    resolved = [_resolve_ref(ref, tasks) for ref in refs]
    return [task for task in resolved if task and task.get("statut") != "Fait"]


def _overdue_tasks_to_complete(normalized_message: str, tasks: list[dict]) -> list[dict]:
    if "retard" not in normalized_message or not _OVERDUE_ACTION_RE.search(normalized_message):
        return []

    overdue = _active_overdue_tasks(tasks)
    if not overdue:
        return []

    requested_count = _requested_count(normalized_message)
    if requested_count is None:
        return overdue

    return overdue[:requested_count] if requested_count > 0 else []


def _active_overdue_tasks(tasks: list[dict]) -> list[dict]:
    today = _today_iso()
    return [
        task
        for task in tasks
        if task.get("statut") != "Fait"
        and task.get("date_limite")
        and task["date_limite"] < today
    ]


def _today_iso() -> str:
    try:
        return datetime.now(ZoneInfo(config.digest_timezone)).date().isoformat()
    except Exception:
        return datetime.now().date().isoformat()


def _requested_count(normalized_message: str) -> int | None:
    match = re.search(r"\b(\d{1,2})\b", normalized_message)
    if match:
        return int(match.group(1))

    words = {
        "un": 1,
        "une": 1,
        "deux": 2,
        "trois": 3,
        "quatre": 4,
        "cinq": 5,
        "six": 6,
        "sept": 7,
        "huit": 8,
        "neuf": 9,
        "dix": 10,
    }
    for word, value in words.items():
        if re.search(rf"\b{word}\b", normalized_message):
            return value
    return None


def _explicit_completed_tasks(normalized_message: str, tasks: list[dict]) -> list[dict]:
    if not _COMPLETION_RE.search(normalized_message):
        return []
    if _looks_like_question(normalized_message):
        return []
    return _matching_active_tasks(normalized_message, tasks)


def _looks_like_question(normalized_message: str) -> bool:
    return normalized_message.startswith(("est ce que", "est-ce que", "quelles", "quelle", "quels", "quel"))


def _matching_active_tasks(normalized_message: str, tasks: list[dict]) -> list[dict]:
    message_tokens = set(_tokenize(normalized_message))
    if not message_tokens:
        return []

    matches: list[dict] = []
    for task in tasks:
        if task.get("statut") == "Fait":
            continue
        title_tokens = set(_task_title_tokens(task.get("nom", "")))
        if not title_tokens:
            continue

        overlap = title_tokens & message_tokens
        if _is_confident_task_match(overlap, title_tokens):
            matches.append(task)

    return matches


def _is_confident_task_match(overlap: set[str], title_tokens: set[str]) -> bool:
    if len(overlap) >= 2:
        return True
    if not overlap:
        return False

    token = next(iter(overlap))
    # Un nom propre ou mot distinctif suffit pour les taches courtes :
    # « Castelli termine », « Charlie termine », etc.
    if len(token) >= 6 and len(title_tokens) <= 4:
        return True

    return len(title_tokens) == 1 and len(token) >= 4


def _task_title_tokens(title: str) -> list[str]:
    return [token for token in _tokenize(_normalize_text(title)) if token not in _TASK_STOPWORDS and len(token) >= 3]


def _tokenize(normalized_text: str) -> list[str]:
    return [token for token in normalized_text.split() if token]


def _is_confirmation(normalized_message: str) -> bool:
    return bool(_CONFIRMATION_RE.search(normalized_message))


async def _do_new_task(update: Update, user_id: int, decision: dict, reply: str) -> None:
    draft = _validated_draft(decision.get("draft") or {})
    # Garde-fou : on ne cree pas sans nom ET importance, meme si l'IA s'est dite prete.
    if not draft.name or not draft.importance:
        conversation_manager.set_pending(user_id, _pending_from(decision))
        await update.message.reply_text(reply)
        return

    notion_client.create_task(draft)
    conversation_manager.clear(user_id)
    await update.message.reply_text(reply)


async def _do_task_action(
    update: Update, user_id: int, decision: dict, tasks: list[dict], intent: str, reply: str
) -> None:
    task = _resolve_ref(decision.get("target_ref"), tasks)
    # Garde-fou : reference de tache invalide -> on n'ecrit rien, on redemande.
    if task is None:
        conversation_manager.set_pending(user_id, _pending_from(decision))
        await update.message.reply_text(reply)
        return

    if intent == "complete_task":
        notion_client.complete_task(task["id"])
        conversation_manager.clear(user_id)
        await update.message.reply_text(reply)
        return

    # update_task
    field = decision.get("update_field") or ""
    value = decision.get("update_value") or ""
    # Garde-fou : champ/valeur invalide -> on n'ecrit rien, on redemande.
    if not _valid_update(field, value):
        conversation_manager.set_pending(user_id, _pending_from(decision))
        await update.message.reply_text(reply)
        return

    notion_client.update_task_field(task["id"], field, value)
    conversation_manager.clear(user_id)
    await update.message.reply_text(reply)


def _apply_status_text_hints(message: str, decision: dict) -> dict:
    """Corrige deterministiquement les confusions de statut les plus risquées.

    L'IA peut confondre « en cours » avec « bloque » parce que le prompt parle de
    « contexte de conversation en cours ». Avant toute ecriture Notion, Python
    force donc le statut explicitement exprime par l'utilisateur.
    """
    if decision.get("intent") != "update_task" or decision.get("update_field") != "status":
        return decision

    explicit_status = _status_from_message(message)
    if explicit_status is None:
        return decision

    return {**decision, "update_value": explicit_status}


def _status_from_message(message: str) -> str | None:
    text = _normalize_text(message)
    # Priorite a l'etat positif : « commence, pas bloque » doit rester En cours.
    if "en cours" in text or re.search(r"\b(commence|demarre|lance)\w*\b", text):
        return "En cours"
    if "pas bloque" in text or re.search(r"\bdebloqu\w*\b", text):
        return "A faire"
    if re.search(r"\bbloqu\w*\b", text):
        return "Bloque"
    if re.search(r"\b(fait|fini|termine|ok)\b", text):
        return "Fait"
    return None


def _normalize_text(text: str) -> str:
    without_accents = "".join(
        char for char in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"[^a-z0-9 ]+", " ", without_accents)


def _resolve_ref(target_ref, tasks: list[dict]) -> dict | None:
    """Remappe le numero de reference (1-based) renvoye par l'IA vers la tache reelle."""
    try:
        index = int(target_ref)
    except (TypeError, ValueError):
        return None
    if 1 <= index <= len(tasks):
        return tasks[index - 1]
    return None


def _valid_update(field: str, value: str) -> bool:
    if field == "importance":
        return value in IMPORTANCES
    if field == "category":
        return value in CATEGORIES
    if field == "effort":
        return value in EFFORTS
    if field == "status":
        return value in STATUSES
    if field == "due_date":
        return bool(_DATE_RE.match(value))
    return False


def _validated_draft(payload: dict) -> TaskDraft:
    """Construit un brouillon en filtrant les valeurs hors enum / dates mal formees :
    rien d'invalide n'atteint Notion."""
    due_date = payload.get("due_date")
    if due_date and not _DATE_RE.match(due_date):
        due_date = None
    return TaskDraft(
        name=payload.get("name") or None,
        importance=payload.get("importance") if payload.get("importance") in IMPORTANCES else None,
        due_date=due_date,
        category=payload.get("category") if payload.get("category") in CATEGORIES else None,
        subcategory=payload.get("subcategory") if payload.get("subcategory") in SUBCATEGORIES else None,
        effort=payload.get("effort") if payload.get("effort") in EFFORTS else None,
    )


def _pending_from(decision: dict) -> dict:
    """Contexte transmis a l'IA au tour suivant pour reprendre la conversation."""
    return {
        "intent": decision.get("intent"),
        "draft": decision.get("draft"),
        "target_ref": decision.get("target_ref"),
        "target_refs": decision.get("target_refs"),
        "target_ids": decision.get("target_ids"),
        "update_field": decision.get("update_field"),
        "update_value": decision.get("update_value"),
        "last_question": decision.get("reply"),
    }


async def _send_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    tasks = notion_client.query_active_tasks()
    digest = ai_client.generate_digest(tasks)
    await context.bot.send_message(chat_id=config.telegram_user_id, text=digest)


def main() -> None:
    app = Application.builder().token(config.telegram_token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    digest_time = dt_time(
        hour=config.digest_hour,
        minute=config.digest_minute,
        tzinfo=ZoneInfo(config.digest_timezone),
    )
    app.job_queue.run_daily(_send_digest, time=digest_time)

    if config.webhook_base_url:
        # Mode production (Render/Railway) : Telegram pousse les messages via HTTPS
        webhook_url = f"{config.webhook_base_url}/{config.telegram_token}"
        logger.info("Mode webhook — %s (port %s)", webhook_url, config.port)
        app.run_webhook(
            listen="0.0.0.0",
            port=config.port,
            url_path=config.telegram_token,
            webhook_url=webhook_url,
        )
    else:
        # Mode développement local : le bot appelle Telegram en boucle
        logger.info("Mode polling (local)")
        app.run_polling()


if __name__ == "__main__":
    main()
