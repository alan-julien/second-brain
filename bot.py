import logging
import re
from datetime import time as dt_time

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ai import AiClient, IMPORTANCES, CATEGORIES, SUBCATEGORIES
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    user_id = update.effective_user.id
    if user_id != config.telegram_user_id:
        logger.warning("Unauthorized Telegram user ignored: %s", user_id)
        return

    text = update.message.text or ""
    await _handle(update, text, user_id)


async def _handle(update: Update, text: str, user_id: int) -> None:
    """Flux 'cerveau unique' : un appel IA decide tout, puis Python valide et execute."""
    state = conversation_manager.get(user_id)
    tasks = notion_client.query_active_tasks()
    decision = ai_client.decide(text, tasks, state.pending)

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
    )


def _pending_from(decision: dict) -> dict:
    """Contexte transmis a l'IA au tour suivant pour reprendre la conversation."""
    return {
        "intent": decision.get("intent"),
        "draft": decision.get("draft"),
        "target_ref": decision.get("target_ref"),
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

    digest_time = dt_time(hour=config.digest_hour, minute=config.digest_minute)
    app.job_queue.run_daily(_send_digest, time=digest_time)

    logger.info("Bot demarre")
    app.run_polling()


if __name__ == "__main__":
    main()
