# Second Brain Bot

## Stack
Python 3.11+, python-telegram-bot 21.6, Anthropic SDK, notion-client, pytest, Railway/Render.

## Architecture
Doctrine : **l'IA decide, le Python valide et execute**. L'IA ne touche jamais Notion directement.
`bot.py` : point d'entree Telegram. Pour chaque message -> `AiClient.decide(...)`, puis validation
deterministe (ref->ID, enums, date) avant toute ecriture Notion.
`ai.py` : classe l'intention, choisit la tache cible dans la liste numerotee fournie, normalise les
champs et redige la reponse naturelle.
`conversation.py` : un `pending` en memoire par utilisateur.
`notion.py` : cree/interroge/modifie les taches ; les proprietes optionnelles absentes de Notion
(`Sous-categorie`, `Effort`) sont tolerees a la lecture.

## Etat actuel
Bot conversationnel base sur un appel IA unique par message.
Railway peut tourner en polling si `WEBHOOK_BASE_URL` est vide/absent.
Render peut tourner en webhook si `WEBHOOK_BASE_URL` pointe vers l'URL publique Render.
Ne garder qu'une seule instance Telegram active a la fois (Railway ou Render).
Base Notion : `https://www.notion.so/7107986c47cc40e38e0923c1138bc1b9`.
Categories : `Conferences`, `Social`, `Code`, `Pro`, `Perso`, `Materiel`.
Sous-categories : `TSE`, `Labo`. Efforts : `Haut`, `Moyen`, `Bas`.
Tests : `py -m pytest tests/ -v` -> 21 tests.

## Prochaines etapes
1. Regenerer le token Telegram via BotFather si un token a ete expose dans des logs ou conversations.
2. Redeployer sur Railway avec `WEBHOOK_BASE_URL` vide pour revenir au polling.
3. Suspendre Render tant que Railway est l'instance active.
4. Verifier les logs apres un message Telegram ; attendre une reponse sans `KeyError`.
