# Lacunes — second_brain bot — 2026-06-03

## À retravailler
- **`pending` (état conversationnel)** : confusion initiale entre historique de messages et fiche structurée de décision partielle. Le `pending` est un dict avec `intent`, `draft`, `target_ref`, `last_question` — il encode ce que l'IA avait déjà déduit, pour ne pas recalculer au tour suivant. Analogie : feature store en ML.
- **Garde-fous Python** : confusion entre "Notion rejetterait de toute façon" et la vraie raison — l'IA probabiliste peut dire `ready=true` avec des champs invalides (date non normalisée, catégorie inventée). Python valide indépendamment, pas pour rattraper Notion, mais pour ne jamais déléguer la garantie d'intégrité à un modèle probabiliste.

## Bien maîtrisé
- But du bot : second cerveau, Telegram = interface fluide, Notion = stockage/affichage
- Pourquoi l'IA ne voit pas les IDs Notion : nature probabiliste → risque d'hallucination d'ID
- Flag `ready` : produit par l'IA, lu par `bot.py` pour décider d'agir ou de continuer la conversation
- Les 5 intentions : `new_task`, `complete_task`, `update_task`, `query`, `smalltalk`
- `pending` en RAM : pas grave si perdu au redémarrage, l'utilisateur re-formule
- Single call IA : cohérence garantie — le `reply` est généré dans le même raisonnement que la décision
- `bot.py` comme orchestrateur central : il coordonne les 3 autres modules sans penser lui-même
