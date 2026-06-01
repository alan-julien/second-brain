# Second Brain Bot

## Stack
Python 3.11+, python-telegram-bot 21.6, Anthropic SDK, notion-client, pytest, Railway.

## Architecture
`bot.py` est le point d'entree Telegram et orchestre la conversation, Claude et Notion.
`conversation.py` garde l'etat en memoire par utilisateur.
`ai.py` gere classification, extraction, reponses et digest.
`notion.py` cree et interroge les taches dans la base Notion.

## Etat actuel
Projet initialise avec configuration, dependances, bot, clients IA/Notion et tests unitaires.
Les tests passent avec `py -m pytest tests/ -v` : 17 tests.
Base Notion creee : `https://www.notion.so/7107986c47cc40e38e0923c1138bc1b9`.
Les proprietes Notion utilisent des noms ASCII : `A faire`, `Categorie`, `Sous-categorie`.
Categories : `Conferences`, `Social`, `Code`, `Pro`; sous-categories : `TSE`, `Labo`.
Le dossier n'est pas encore initialise comme depot Git.
Le fichier `.env` est configure et le bot a deja ete lance en local.

## Prochaines etapes
1. Creer `.env` depuis `.env.example` avec les tokens Telegram, Anthropic et Notion.
2. Partager la base Notion avec l'integration Notion du bot.
3. Lancer `py bot.py` et tester la capture de tache dans Telegram.
4. Initialiser Git/GitHub puis connecter Railway pour le deploiement.
