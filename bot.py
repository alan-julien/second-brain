import logging
from datetime import time as dt_time

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from ai import AiClient, QUESTIONS, get_next_question
from config import load_config
from conversation import ConversationManager, ConversationMode, TaskDraft
from notion import NotionClient


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = load_config()
conversation_manager = ConversationManager()
ai_client = AiClient(api_key=config.anthropic_api_key)
notion_client = NotionClient(
    token=config.notion_token,
    database_id=config.notion_database_id,
)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return

    user_id = update.effective_user.id
    if user_id != config.telegram_user_id:
        logger.warning("Unauthorized Telegram user ignored: %s", user_id)
        return

    text = update.message.text or ""
    state = conversation_manager.get(user_id)

    if state.mode == ConversationMode.CAPTURING:
        await _handle_capture_reply(update, text, user_id, state)
        return

    await _handle_new_message(update, text, user_id)


async def _handle_new_message(update: Update, text: str, user_id: int) -> None:
    result = ai_client.classify(text)
    if result.get("intent") == "new_task":
        draft = _draft_from_payload(result.get("draft") or {})
        next_q = get_next_question(draft)
        if next_q is None:
            await _save_and_confirm(update, draft)
            return

        field, question = next_q
        conversation_manager.start_capture(user_id, draft, awaiting=field)
        await update.message.reply_text(question)
        return

    if result.get("intent") == "complete_task":
        task_name = result.get("task_name") or ""
        page_id = notion_client.find_task_by_name(task_name)
        if page_id:
            notion_client.complete_task(page_id)
            await update.message.reply_text(f"Tache \"{task_name}\" marquee comme terminee.")
        else:
            await update.message.reply_text(f"Aucune tache active trouvee pour \"{task_name}\".")
        return

    if result.get("intent") == "update_task":
        task_name = result.get("task_name") or ""
        field = result.get("update_field") or ""
        value = result.get("update_value") or ""
        page_id = notion_client.find_task_by_name(task_name)
        if page_id and field and value:
            notion_client.update_task_field(page_id, field, value)
            field_labels = {"due_date": "date limite", "importance": "importance", "category": "categorie"}
            label = field_labels.get(field, field)
            await update.message.reply_text(f"Tache \"{task_name}\" : {label} mise a jour -> {value}.")
        else:
            await update.message.reply_text(f"Je n'ai pas pu effectuer la modification sur \"{task_name}\".")
        return

    tasks = notion_client.query_active_tasks()
    answer = ai_client.answer_query(result.get("query") or text, tasks)
    await update.message.reply_text(answer)


async def _handle_capture_reply(update: Update, text: str, user_id: int, state) -> None:
    if state.awaiting is None:
        conversation_manager.clear(user_id)
        await update.message.reply_text("Je reprends depuis le debut. Quelle est la tache ?")
        return

    question = QUESTIONS.get(state.awaiting, f"Valeur pour {state.awaiting} ?")
    value = ai_client.extract_field(state.awaiting, question, text)
    draft = conversation_manager.update_field(user_id, state.awaiting, value)
    next_q = get_next_question(draft)

    if next_q is None:
        conversation_manager.clear(user_id)
        await _save_and_confirm(update, draft)
        return

    field, question = next_q
    conversation_manager.start_capture(user_id, draft, awaiting=field)
    await update.message.reply_text(question)


def _draft_from_payload(payload: dict) -> TaskDraft:
    return TaskDraft(
        name=payload.get("name") or None,
        importance=payload.get("importance") or None,
        due_date=payload.get("due_date"),
        category=payload.get("category"),
        subcategory=payload.get("subcategory"),
    )


async def _save_and_confirm(update: Update, draft: TaskDraft) -> None:
    notion_client.create_task(draft)
    await update.message.reply_text(_confirmation_message(draft))


def _confirmation_message(draft: TaskDraft) -> str:
    parts = [f"Tache creee - {draft.name}", draft.importance or ""]
    if draft.due_date:
        parts.append(draft.due_date)
    if draft.category:
        parts.append(draft.category)
    return " - ".join(part for part in parts if part)


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
