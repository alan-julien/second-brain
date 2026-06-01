import json
import re
from datetime import date
from typing import Optional

from anthropic import Anthropic

from conversation import TaskDraft


QUESTIONS = {
    "name": "Quelle est la tache ?",
    "importance": "Quelle importance ? (Haute / Moyenne / Basse)",
    "due_date": "Une date limite ? (ou 'aucune')",
    "category": "Une categorie ? (Conferences / Social / Code / Pro - ou 'aucune')",
    "subcategory": "Une sous-categorie ? (TSE / Labo - ou 'aucune')",
}

CLASSIFY_PROMPT = """Tu es un assistant de gestion de taches personnel.
Analyse le message et retourne UNIQUEMENT du JSON valide, sans texte avant ou apres.

Format requis :
{{
  "intent": "new_task" ou "query",
  "draft": {{
    "name": "titre concis ou null",
    "importance": "Haute" ou "Moyenne" ou "Basse" ou null,
    "due_date": "YYYY-MM-DD ou null",
    "category": "Conferences" ou "Social" ou "Code" ou "Pro" ou null,
    "subcategory": "TSE" ou "Labo" ou null
  }},
  "query": "question reformulee si intent=query, sinon null"
}}

Regles :
- intent=new_task si le message decrit quelque chose a faire
- intent=query si le message pose une question sur les taches existantes
- due_date : convertis les dates relatives en YYYY-MM-DD. Aujourd'hui = {today}
- importance : deduis du contexte ("urgent" -> Haute, "quand possible" -> Basse)
- draft est toujours present meme si intent=query (null pour tous les champs)"""

DIGEST_SYSTEM = """Tu generes un digest matinal de taches. Sois concis.
Commence par "Bonjour - voici tes taches :"
Maximum 5 taches, priorisees par importance puis date limite.
Reponds uniquement avec le digest, en francais."""


def get_next_question(draft: TaskDraft) -> Optional[tuple[str, str]]:
    if not draft.name:
        return ("name", QUESTIONS["name"])
    if not draft.importance:
        return ("importance", QUESTIONS["importance"])
    if draft.due_date is None:
        return ("due_date", QUESTIONS["due_date"])
    if draft.category is None:
        return ("category", QUESTIONS["category"])
    if draft.category == "Pro" and draft.subcategory is None:
        return ("subcategory", QUESTIONS["subcategory"])
    return None


def _parse_json_response(text: str) -> dict:
    stripped = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1).strip()
    return json.loads(stripped)


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
        return _parse_json_response(response.content[0].text)

    def extract_field(self, field: str, question: str, answer: str) -> str:
        today = date.today().isoformat()
        prompt = (
            f'L utilisateur repondait a : "{question}"\n'
            f'Sa reponse : "{answer}"\n'
            f"Champ a extraire : {field}\n"
            f"Aujourd'hui = {today}\n"
            'Retourne UNIQUEMENT du JSON : {"value": "valeur ou vide"}\n'
            'Pour "aucune", "non", "pas de", "skip" -> retourne {"value": ""}\n'
            "Pour importance -> valide parmi : Haute, Moyenne, Basse\n"
            "Pour category -> valide parmi : Conferences, Social, Code, Pro\n"
            "Pour subcategory -> valide parmi : TSE, Labo\n"
            "Pour due_date -> format YYYY-MM-DD"
        )
        response = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        result = _parse_json_response(response.content[0].text)
        return result.get("value", "")

    def answer_query(self, query: str, tasks: list[dict]) -> str:
        tasks_text = json.dumps(tasks, ensure_ascii=False, indent=2)
        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=(
                "Tu es un assistant de gestion de taches personnel. "
                "Reponds en francais, de facon concise (5 lignes max)."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Question : {query}\n\nTaches :\n{tasks_text}",
                }
            ],
        )
        return response.content[0].text

    def generate_digest(self, tasks: list[dict]) -> str:
        if not tasks:
            return "Bonjour - aucune tache active pour l'instant."

        tasks_text = json.dumps(tasks, ensure_ascii=False, indent=2)
        response = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=DIGEST_SYSTEM,
            messages=[{"role": "user", "content": tasks_text}],
        )
        return response.content[0].text
