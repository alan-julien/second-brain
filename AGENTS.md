# Second Brain Bot

## Stack
Python 3.11+, python-telegram-bot 21.6, Anthropic SDK, notion-client, pytest, Railway.

## Architecture
Doctrine : **l'IA decide, le Python valide et execute**. L'IA ne touche jamais Notion directement.
`bot.py` : point d'entree Telegram. Pour chaque message -> 1 appel `AiClient.decide(...)` (cerveau
unique), puis validation deterministe (ref->ID, enums, date) avant toute ecriture Notion.
`ai.py` : `decide()` classe l'intention, choisit la tache cible **dans la liste numerotee fournie**
(matching semantique : "StJean" = "Saint-Jean"), normalise les champs et redige la reponse naturelle.
Modele via `config.anthropic_model` (defaut `claude-haiku-4-5`). `generate_digest` conserve.
`conversation.py` : etat en memoire = un `pending` (contexte d'une demande en cours) par utilisateur.
`notion.py` : cree/interroge/modifie les taches ; `query_active_tasks` expose l'`id` de chaque page.

Garde-fou : l'IA renvoie un numero de reference (1,2,3...), jamais l'ID Notion brut ; `bot.py` le
remappe vers l'ID reel. Ref invalide / enum hors-liste / date mal formee -> aucune ecriture, on redemande.

## Etat actuel
Bot conversationnel base sur un appel IA unique par message. Plus de matching par sous-chaine.
Les tests passent avec `py -m pytest tests/ -v` : 20 tests.
Base Notion creee : `https://www.notion.so/7107986c47cc40e38e0923c1138bc1b9`.
Les proprietes Notion utilisent des noms ASCII : `A faire`, `Categorie`, `Sous-categorie`.
Categories : `Conferences`, `Social`, `Code`, `Pro`; sous-categories : `TSE`, `Labo`.
Variable d'env optionnelle `ANTHROPIC_MODEL` (defaut `claude-haiku-4-5`; mettre `claude-sonnet-4-6`
si le matching est trop juste).
Depot GitHub : `https://github.com/alan-julien/second-brain`.
Le fichier `.env` est configure et le bot a deja ete lance en local.

## Prochaines etapes
1. Creer un projet Railway depuis le repo GitHub.
2. Ajouter les variables d'environnement dans Railway.
3. Verifier les logs Railway jusqu'a `Bot demarre`.
4. Arreter le bot local pour eviter deux instances Telegram.
