import json
import re
from datetime import date

from anthropic import Anthropic


# Valeurs autorisees cote Notion. Servent de garde-fou : l'IA est invitee a s'y
# tenir, et bot.py rejette toute valeur hors de ces listes avant ecriture.
IMPORTANCES = ["Haute", "Moyenne", "Basse"]
CATEGORIES = ["Conferences", "Social", "Code", "Pro", "Perso", "Materiel"]
SUBCATEGORIES = ["TSE", "Labo"]
EFFORTS = ["Haut", "Moyen", "Bas"]

STATUSES = ["A faire", "En cours", "Bloque", "Fait"]

DECIDE_PROMPT = """Tu es un assistant de gestion de taches personnel, chaleureux et naturel.
Tu parles avec l'utilisateur comme un humain intelligent, pas comme un formulaire.

On te fournit : le message de l'utilisateur, la liste numerotee de ses taches actives, et
eventuellement un contexte de conversation en cours (une demande precedente pas encore finalisee).

Tu dois retourner UNIQUEMENT du JSON valide, sans texte avant ou apres :
{{
  "intent": "new_task" | "complete_task" | "update_task" | "query" | "smalltalk",
  "target_ref": <numero de la tache visee dans la liste fournie, ou null>,
  "draft": {{
    "name": "titre concis ou null",
    "importance": "Haute" | "Moyenne" | "Basse" | null,
    "due_date": "AAAA-MM-JJ ou null",
    "category": "Conferences" | "Social" | "Code" | "Pro" | "Perso" | "Materiel" | null,
    "subcategory": "TSE" | "Labo" | null,
    "effort": "Haut" | "Moyen" | "Bas" | null
  }},
  "update_field": "due_date" | "importance" | "category" | "effort" | "status" | null,
  "update_value": "nouvelle valeur normalisee ou null",
  "ready": true | false,
  "reply": "message naturel en francais a envoyer a l'utilisateur"
}}

Intentions :
- new_task : l'utilisateur decrit quelque chose a faire (tache a creer).
- complete_task : il veut marquer une tache existante comme terminee/faite.
- update_task : il veut modifier un champ d'une tache existante (date, importance, categorie, effort, statut).
- query : il pose une question sur ses taches -> reponds directement dans "reply" a partir de la liste fournie. Pour une liste de taches, liste seulement les taches dont le statut n'est pas Fait.
- smalltalk : salutation, remerciement, hors-sujet -> reponds gentiment dans "reply".

Messages bruites / multi-lignes :
- Si un message contient une vraie demande puis des lignes generiques comme "Test", "Liste taches" ou "Créer tache", ignore ces lignes generiques et traite la vraie demande.
- Si le contexte pending contient un brouillon ou une cible, fusionne strictement le nouveau message avec ce contexte au lieu de repartir de zero. Exemple : apres une question sur la categorie de "St Jean", "Conférence" signifie category=Conferences pour ce brouillon.

Choix de la tache cible (complete_task / update_task) :
- Choisis le numero dans la liste fournie meme si l'utilisateur abrege ("StJean" = "Saint-Jean"),
  fait une faute, ou reformule. Tu raisonnes sur le SENS, pas sur les caracteres exacts.
- Si AUCUNE tache ne correspond raisonnablement -> target_ref=null, ready=false, et demande gentiment
  dans "reply" (propose les titres proches s'il y en a).
- Si PLUSIEURS taches correspondent -> target_ref=null, ready=false, et demande laquelle dans "reply"
  en listant les candidates.

Champ "ready" :
- true seulement si tu as tout ce qu'il faut pour agir sans risque (tache cible certaine pour
  complete/update ; au minimum un nom et une importance pour new_task).
- Si le message fournit nom + importance, cree la tache meme si date/categorie/effort manquent : ne pose pas de question optionnelle.
- false si une info manque ou en cas de doute : pose alors UNE question claire dans "reply".

Normalisation :
- due_date : convertis les dates relatives en AAAA-MM-JJ. Aujourd'hui = {today}.
- importance : deduis du contexte ("important", "urgent", "prioritaire" -> Haute ; "moyen" -> Moyenne ; "quand tu peux" -> Basse). Valeurs : {importances}.
- Ne confonds jamais importance et effort : "important faible effort" => importance=Haute, effort=Bas.
- category : parmi {categories}. "conference" ou "conférence" => Conferences. subcategory (si category=Pro) : parmi {subcategories}.
- effort : parmi {efforts}. Deduis du contexte ("faible", "rapide", "fort faible" -> Bas ; "moyen" -> Moyen ; "complique" -> Haut). Laisse null si non mentionne.

- status : parmi {statuses}. "en cours", "commence", "commencé", "demarre", "démarré" => En cours ; "bloque", "bloquee", "bloqué", "bloquée" => Bloque ; "pas bloque" / "pas bloqué" n'est PAS Bloque ; "fait", "termine", "ok" => Fait.

- Ne force pas une categorie/date/effort si l'utilisateur n'en donne pas : laisse null, ce n'est pas bloquant.

Contexte de conversation en cours (a fusionner avec le nouveau message si present) :
{pending}

Liste de reference des taches (numero | titre | statut | importance | date | categorie | effort) :
{tasks}

"reply" doit TOUJOURS etre rempli : confirmation de l'action, question, ou reponse. Concis (<= 4 lignes)."""

DIGEST_SYSTEM = """Tu generes un digest matinal de taches. Sois concis.
Commence par "Bonjour - voici tes taches :"
Maximum 5 taches, priorisees par importance puis date limite.
Reponds uniquement avec le digest, en francais."""


def _parse_json_response(text: str) -> dict:
    stripped = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Réponse IA non JSON : {text[:200]}") from exc



_NOISE_LINES = {
    "test",
    "tests",
    "liste tache",
    "liste taches",
    "liste des taches",
    "tache",
    "taches",
    "creer tache",
    "cree tache",
    "créer tâche",
    "crée tâche",
    "créer tache",
    "crée tache",
}


def _line_key(line: str) -> str:
    lowered = line.strip().lower()
    lowered = lowered.replace("â", "a").replace("à", "a").replace("é", "e").replace("è", "e").replace("ê", "e")
    return re.sub(r"[^a-z ]+", "", lowered).strip()


def _clean_user_message(message: str) -> str:
    """Retire les lignes de bruit quand elles accompagnent une vraie demande.

    Les conversations Telegram montrent souvent des messages dictes avec une
    demande exploitable suivie de « Test », « Liste taches » ou « Créer tache ».
    Ces lignes ne doivent pas faire basculer l'intention vers smalltalk/query.
    Si le message ne contient que cette commande, on le conserve.
    """
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    if len(lines) <= 1:
        return message.strip()
    kept = [line for line in lines if _line_key(line) not in _NOISE_LINES]
    return "\n".join(kept or lines)


def _format_tasks(tasks: list[dict]) -> str:
    """Construit la liste numerotee donnee a l'IA. Le numero (1-based) est la
    reference stable que l'IA renverra dans target_ref ; bot.py la remappe vers
    l'ID Notion reel. L'IA ne voit jamais les ID bruts (qu'elle hallucinerait)."""
    if not tasks:
        return "(aucune tache active)"
    lines = []
    for i, task in enumerate(tasks, start=1):
        date_part = task.get("date_limite") or "sans date"
        cat_part = task.get("categorie") or "sans categorie"
        effort_part = task.get("effort") or "sans effort"
        status_part = task.get("statut") or "sans statut"
        lines.append(
            f"{i} | {task.get('nom', '')} | {status_part} | {task.get('importance', '')} | {date_part} | {cat_part} | {effort_part}"
        )
    return "\n".join(lines)


class AiClient:
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5"):
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def decide(self, message: str, tasks: list[dict], pending: dict | None = None) -> dict:
        """Le 'cerveau unique' : un seul appel qui classe l'intention, choisit la
        tache cible, normalise les champs et redige la reponse en langage naturel."""
        today = date.today().isoformat()
        system = DECIDE_PROMPT.format(
            today=today,
            importances=", ".join(IMPORTANCES),
            categories=", ".join(CATEGORIES),
            subcategories=", ".join(SUBCATEGORIES),
            efforts=", ".join(EFFORTS),
            statuses=", ".join(STATUSES),
            pending=json.dumps(pending, ensure_ascii=False) if pending else "(aucun)",
            tasks=_format_tasks(tasks),
        )
        message = _clean_user_message(message)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=700,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
        return _parse_json_response(response.content[0].text)

    def generate_digest(self, tasks: list[dict]) -> str:
        if not tasks:
            return "Bonjour - aucune tache active pour l'instant."

        tasks_text = json.dumps(tasks, ensure_ascii=False, indent=2)
        response = self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=400,
            system=DIGEST_SYSTEM,
            messages=[{"role": "user", "content": tasks_text}],
        )
        return response.content[0].text
