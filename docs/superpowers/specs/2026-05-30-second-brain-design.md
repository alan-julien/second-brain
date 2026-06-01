# Second Brain — Bot Telegram de gestion de tâches

## Contexte

Outil personnel pour capturer et organiser des tâches via une interface conversationnelle Telegram, avec stockage dans Notion.

## Stack

- **Python** — langage principal
- **python-telegram-bot** — interface Telegram
- **anthropic** (SDK Python) — intelligence IA (Claude)
- **notion-client** — lecture/écriture Notion
- **APScheduler** — digest quotidien automatique
- **Déploiement** — Railway.app (gratuit, connecté à GitHub)

## Architecture

```
Utilisateur (Telegram)
        │
        ▼
    bot.py  ←─────────── scheduler.py (digest quotidien)
        │                       │
        ├── conversation.py     │
        │   (état en mémoire)   │
        │                       │
        ├── ai.py ──────────────┘
        │   (détection d'intention, extraction, digest)
        │
        └── notion.py
            (CRUD tâches)
```

### Modules

| Fichier | Rôle |
|---|---|
| `bot.py` | Handler Telegram — reçoit messages, envoie réponses |
| `conversation.py` | Mémorise l'état de chaque conversation (champs manquants) |
| `ai.py` | Appelle Claude : détecte intention, extrait champs, génère digest |
| `notion.py` | Crée et interroge les tâches dans Notion |
| `scheduler.py` | Envoie le digest Telegram chaque matin à heure configurable |
| `config.py` | Variables d'environnement (tokens, IDs) |

## Schéma Notion

Table unique **Tâches** :

| Champ | Type Notion | Valeurs initiales |
|---|---|---|
| Nom | Title | texte libre |
| Statut | Select | À faire / En cours / Bloqué / Fait |
| Importance | Select | Haute / Moyenne / Basse |
| Date limite | Date | — |
| Catégorie | Select | Conférences / Social / Code (extensible dans Notion) |
| Sous-catégorie | Select | vide au départ (extensible dans Notion) |

Les catégories et sous-catégories sont gérées directement dans Notion — ajouter une nouvelle valeur ne nécessite aucune modification du code.

## Flux de conversation

### Détection d'intention

À chaque message, Claude détermine si l'utilisateur :
1. **Ajoute une tâche** → mode capture
2. **Pose une question** sur ses tâches existantes → requête Notion + réponse

### Mode capture (nouvelle tâche)

Claude extrait les champs disponibles dans le message initial, puis pose une question à la fois pour les champs manquants obligatoires (Nom, Importance). Date limite, Catégorie et Sous-catégorie sont demandés si non détectés — l'utilisateur peut répondre "aucune" pour les ignorer.

```
Utilisateur : "je dois préparer ma présentation pour le congrès de juin"

Bot : "Quelle importance ? (Haute / Moyenne / Basse)"
Utilisateur : "Haute"

Bot : "Une date limite ?"
Utilisateur : "15 juin"

Bot : "✓ Tâche créée — Préparer présentation congrès · Haute · 15 juin · Conférences"
```

### Mode question

```
Utilisateur : "qu'est-ce que j'ai d'urgent cette semaine ?"
Bot : "2 tâches Haute priorité avant vendredi :
  • Préparer présentation congrès (15 juin)
  • Appeler comptable (13 juin)"
```

### Digest quotidien (automatique)

Envoyé chaque matin dans Telegram à l'heure configurée :

```
Bonjour — voici tes tâches pour aujourd'hui :
🔴 Préparer présentation congrès (15 juin)
🟡 Appeler comptable
⚪ Répondre à Marie
```

## Variables d'environnement

```
TELEGRAM_TOKEN       — token du bot (BotFather)
TELEGRAM_USER_ID     — ton ID Telegram (pour restreindre l'accès)
ANTHROPIC_API_KEY    — clé API Claude
NOTION_TOKEN         — token d'intégration Notion
NOTION_DATABASE_ID   — ID de la table Tâches
DIGEST_HOUR          — heure du digest (ex: 8)
DIGEST_MINUTE        — minute du digest (ex: 0)
```

## Contraintes et décisions clés

- **Un seul utilisateur** : le bot est personnel, accès restreint par `TELEGRAM_USER_ID`
- **État en mémoire** : la conversation est mémorisée en RAM (dict Python) — suffisant pour un usage solo, pas besoin de base de données pour l'état
- **Catégories extensibles sans code** : gérées côté Notion uniquement
- **Champs obligatoires** : Nom + Importance. Les autres sont optionnels (l'utilisateur peut passer)
- **Pas de gestion d'erreur complexe** : si Notion est indisponible, le bot répond un message d'erreur simple

## Structure de fichiers

```
second_brain/
├── bot.py
├── conversation.py
├── ai.py
├── notion.py
├── scheduler.py
├── config.py
├── requirements.txt
├── railway.toml
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-05-30-second-brain-design.md
```
