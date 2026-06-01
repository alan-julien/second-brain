# Second Brain Bot - prochaines etapes

Ce document explique comment passer du code actuel a un bot Telegram fonctionnel en local, puis deploye.

## 1. Ce qui est deja pret

- Le code Python du bot est cree.
- Les dependances sont listees dans `requirements.txt`.
- Les tests unitaires passent avec `py -m pytest tests/ -v`.
- Le fichier `.env.example` liste les variables a renseigner.
- La configuration Railway est presente dans `railway.toml`.

## 2. Base Notion

La base Notion doit contenir une table `Taches` avec ces proprietes :

| Propriete | Type Notion | Valeurs |
|---|---|---|
| `Nom` | Title | Texte libre |
| `Statut` | Select | `A faire`, `En cours`, `Bloque`, `Fait` |
| `Importance` | Select | `Haute`, `Moyenne`, `Basse` |
| `Date limite` | Date | Date optionnelle |
| `Categorie` | Select | `Conferences`, `Social`, `Code` |
| `Sous-categorie` | Select | Valeurs libres |

Codex peut creer cette base via MCP Notion. En revanche, le bot ne peut pas utiliser l'acces MCP de Codex en production : il lui faut un token d'integration Notion.

Base creee via MCP :

- URL : `https://www.notion.so/7107986c47cc40e38e0923c1138bc1b9`
- `NOTION_DATABASE_ID` conseille : `7107986c47cc40e38e0923c1138bc1b9`
- Data source MCP : `collection://c0ad7aed-eb90-4779-b05e-9ef013e827ac`

## 3. Integration Notion pour le bot

1. Aller sur `https://www.notion.so/my-integrations`.
2. Creer une nouvelle integration.
3. Copier le `NOTION_TOKEN`.
4. Ouvrir la base `Taches` dans Notion.
5. Cliquer sur `Share` / `Partager`.
6. Ajouter l'integration a la base.
7. Utiliser `7107986c47cc40e38e0923c1138bc1b9` comme `NOTION_DATABASE_ID`, sauf si tu recrees une autre base.

Le `NOTION_DATABASE_ID` est la longue chaine d'identifiant dans l'URL Notion.

## 4. Bot Telegram

1. Dans Telegram, ouvrir `@BotFather`.
2. Envoyer `/newbot`.
3. Donner un nom et un username au bot.
4. Copier le `TELEGRAM_TOKEN`.
5. Ouvrir `@userinfobot`.
6. Lui envoyer un message.
7. Copier ton `TELEGRAM_USER_ID`.

Le bot est volontairement limite a un seul utilisateur via `TELEGRAM_USER_ID`.

## 5. Fichier `.env`

Creer un fichier `.env` a la racine du projet, sur le modele de `.env.example` :

```env
TELEGRAM_TOKEN=...
TELEGRAM_USER_ID=...
ANTHROPIC_API_KEY=...
NOTION_TOKEN=...
NOTION_DATABASE_ID=...
DIGEST_HOUR=8
DIGEST_MINUTE=0
```

Ne pas envoyer `.env` sur GitHub. Il contient des secrets et il est ignore par `.gitignore`.

## 6. Test local

Installer les dependances si ce n'est pas deja fait :

```powershell
py -m pip install -r requirements.txt
```

Lancer les tests :

```powershell
py -m pytest tests/ -v
```

Lancer le bot :

```powershell
py bot.py
```

Resultat attendu dans le terminal :

```text
Bot demarre
```

Test Telegram conseille :

1. Envoyer `je dois preparer ma conference pour juin`.
2. Repondre a la question d'importance.
3. Repondre a la question de date limite.
4. Repondre a la question de categorie.
5. Verifier que la tache apparait dans Notion.
6. Envoyer `quelles sont mes taches urgentes ?`.

## 7. Deploiement Railway

Quand le test local fonctionne :

1. Initialiser Git si besoin.
2. Creer un repo GitHub.
3. Pousser le projet sur GitHub.
4. Creer un projet Railway depuis ce repo.
5. Ajouter les variables d'environnement dans Railway.
6. Verifier les logs Railway.

Les logs doivent afficher :

```text
Bot demarre
```

## 8. Points a retenir

- MCP Notion sert a Codex pendant cette session.
- Le bot, lui, utilise l'API Notion avec `NOTION_TOKEN`.
- Telegram utilise `TELEGRAM_TOKEN`.
- Claude utilise `ANTHROPIC_API_KEY`.
- Railway utilise les memes variables d'environnement que le fichier `.env`.
