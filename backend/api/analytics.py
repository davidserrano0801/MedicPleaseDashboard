"""Validación del saveFile.json de Unity y cálculo de métricas del dashboard.

Este módulo no depende de Django ni de MongoDB para poder probarlo fácilmente.

Formato actual del save:
    {
      "playerName": "Dario",
      "actualCase": "Situacion1",
      "caseHistory": [
        {
          "caseId": "Situacion1",
          "attempts": [
            {
              "attemptNumber": 1,
              "isFinished": true,
              "isAbandoned": false,
              "diagnosedCorrectly": true,
              "decisions": [{"decision": "Trigémino", "isRelevant": true}]
            }
          ]
        }
      ]
    }

Compatibilidad: el formato anterior (decisionsMade + relevantDecisionsMade /
relevantDecisionMade) se convierte automáticamente a un único intento "en curso"
del caso actual, tanto al recibirlo como al leer partidas viejas de la base.
"""
import re

MAX_NAME = 60
MAX_CASE = 100
MAX_CASES = 100
MAX_ATTEMPTS = 500
MAX_DECISIONS = 2000
MAX_TEXT = 500


class ValidationError(ValueError):
    pass


# ------------------------------------------------------------- validación

def _text(value, field, limit):
    if not isinstance(value, str):
        raise ValidationError(f"{field} debe ser texto")
    return value.strip()[:limit]


def _bool(value, field, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    raise ValidationError(f"{field} debe ser true o false")


def _list(value, field, limit):
    if not isinstance(value, list):
        raise ValidationError(f"{field} debe ser una lista")
    if len(value) > limit:
        raise ValidationError(f"{field} tiene demasiados elementos")
    return value


def _clean_decision(raw):
    if isinstance(raw, str):
        text, relevant = raw, None
    elif isinstance(raw, dict):
        text = raw.get("decision")
        if not isinstance(text, str):
            raise ValidationError("Cada decisión necesita el campo 'decision' (texto)")
        relevant = _bool(raw.get("isRelevant"), "isRelevant", default=None)
    else:
        raise ValidationError("Cada decisión debe ser un objeto o un texto")
    text = text.strip()
    if not text:
        return None
    return {"decision": text[:MAX_TEXT], "isRelevant": relevant}


def _clean_attempt(raw, index):
    if not isinstance(raw, dict):
        raise ValidationError("Cada intento debe ser un objeto")
    number = raw.get("attemptNumber")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        number = index + 1
    decisions_raw = _list(raw.get("decisions", []), "decisions", MAX_DECISIONS)
    decisions = [d for d in (_clean_decision(x) for x in decisions_raw) if d]
    return {
        "attemptNumber": number,
        "isFinished": _bool(raw.get("isFinished"), "isFinished"),
        "isAbandoned": _bool(raw.get("isAbandoned"), "isAbandoned"),
        "diagnosedCorrectly": _bool(raw.get("diagnosedCorrectly"), "diagnosedCorrectly"),
        "decisions": decisions,
    }


def _clean_case(raw):
    if not isinstance(raw, dict):
        raise ValidationError("Cada elemento de caseHistory debe ser un objeto")
    case_id = _text(raw.get("caseId"), "caseId", MAX_CASE)
    if not case_id:
        raise ValidationError("caseId es obligatorio en cada caso")
    attempts_raw = _list(raw.get("attempts", []), "attempts", MAX_ATTEMPTS)
    return {
        "caseId": case_id,
        "attempts": [_clean_attempt(a, i) for i, a in enumerate(attempts_raw)],
    }


def _legacy_history(case, decisions, relevant):
    """Convierte decisionsMade/relevantDecisionsMade en un caseHistory."""
    if not decisions:
        return []
    relevant_set = set(relevant) if relevant is not None else None
    return [{
        "caseId": case or "Sin caso",
        "attempts": [{
            "attemptNumber": 1,
            "isFinished": False,
            "isAbandoned": False,
            "diagnosedCorrectly": False,
            "decisions": [
                {"decision": d,
                 "isRelevant": None if relevant_set is None else d in relevant_set}
                for d in decisions
            ],
        }],
    }]


def _clean_text_list(raw, field):
    result = []
    for item in _list(raw, field, MAX_DECISIONS):
        if not isinstance(item, str):
            raise ValidationError(f"{field} solo admite textos")
        if item.strip():
            result.append(item.strip()[:MAX_TEXT])
    return result


def validate_save(payload):
    """Devuelve un dict limpio listo para guardar o lanza ValidationError."""
    if not isinstance(payload, dict):
        raise ValidationError("El cuerpo debe ser un objeto JSON")

    name = _text(payload.get("playerName", ""), "playerName", MAX_NAME)
    if not name:
        raise ValidationError("playerName es obligatorio")
    actual_case = _text(payload.get("actualCase", ""), "actualCase", MAX_CASE)

    if payload.get("caseHistory") is not None:
        history = [_clean_case(c) for c in
                   _list(payload["caseHistory"], "caseHistory", MAX_CASES)]
    elif payload.get("decisionsMade") is not None:  # formato anterior
        relevant_raw = payload.get("relevantDecisionsMade")
        if relevant_raw is None:
            relevant_raw = payload.get("relevantDecisionMade")
        history = _legacy_history(
            actual_case,
            _clean_text_list(payload["decisionsMade"], "decisionsMade"),
            None if relevant_raw is None
            else _clean_text_list(relevant_raw, "relevantDecisionsMade"),
        )
    else:
        history = []

    return {"playerName": name, "actualCase": actual_case, "caseHistory": history}


def normalize_doc(doc):
    """caseHistory de un documento guardado (convierte partidas del formato viejo)."""
    history = doc.get("caseHistory")
    if history is not None:
        return history
    return _legacy_history(
        doc.get("actualCase", ""),
        doc.get("decisionsMade") or [],
        doc.get("relevantDecisionsMade"),
    )


# ---------------------------------------------------------------- métricas

def natural_key(text):
    """'Situacion 10' va después de 'Situacion 2'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text or "")]


def attempt_status(attempt):
    if attempt.get("isAbandoned"):
        return "abandoned"
    if not attempt.get("isFinished"):
        return "in_progress"
    return "correct" if attempt.get("diagnosedCorrectly") else "incorrect"


def _acc():
    return {"attempts": 0, "abandoned": 0, "completed": 0, "correct": 0,
            "decisions": 0, "rated": 0, "relevant": 0, "to_success": []}


def _add_attempt(acc, attempt):
    status = attempt_status(attempt)
    acc["attempts"] += 1
    acc["abandoned"] += status == "abandoned"
    acc["completed"] += status in ("correct", "incorrect")
    acc["correct"] += status == "correct"
    for d in attempt.get("decisions", []):
        acc["decisions"] += 1
        if d.get("isRelevant") is not None:
            acc["rated"] += 1
            acc["relevant"] += bool(d["isRelevant"])


def _pct(part, whole):
    return round(100 * part / whole, 1) if whole else None


def _avg(values):
    return round(sum(values) / len(values), 2) if values else None


def _rates(acc):
    return {
        "attempts": acc["attempts"],
        "abandoned": acc["abandoned"],
        "completed": acc["completed"],
        "correct": acc["correct"],
        "success_rate": _pct(acc["correct"], acc["completed"]),
        "decisions": acc["decisions"],
        "relevant": acc["relevant"] if acc["rated"] else None,
        "precision": _pct(acc["relevant"], acc["rated"]),
        "avg_attempts_to_success": _avg(acc["to_success"]),
    }


def build_dashboard(saves, top_n=15):
    """`saves`: lista de documentos guardados en Mongo (con updated_at)."""
    total = _acc()
    per_case = {}
    players_per_case = {}
    outcomes = {"correct": 0, "incorrect": 0, "abandoned": 0, "in_progress": 0}
    taken_by, relevant_flag = {}, {}
    players = []

    for save in saves:
        name = save.get("playerName", "")
        current = save.get("actualCase") or "Sin caso"
        players_per_case[current] = players_per_case.get(current, 0) + 1
        mine = _acc()
        case_ids = set()

        for case in normalize_doc(save):
            case_id = case.get("caseId") or "Sin caso"
            case_ids.add(case_id)
            case_acc = per_case.setdefault(case_id, {"players": set(), "acc": _acc()})
            case_acc["players"].add(name)
            for index, attempt in enumerate(case.get("attempts", [])):
                outcomes[attempt_status(attempt)] += 1
                for acc in (total, mine, case_acc["acc"]):
                    _add_attempt(acc, attempt)
                for d in attempt.get("decisions", []):
                    text = d["decision"]
                    taken_by.setdefault(text, set()).add(name)
                    relevant_flag.setdefault(text, None)
                    if d.get("isRelevant") is not None:
                        relevant_flag[text] = bool(relevant_flag[text]) or bool(d["isRelevant"])
            # intentos que necesitó este jugador hasta acertar este caso
            first = next((i + 1 for i, a in enumerate(case.get("attempts", []))
                          if attempt_status(a) == "correct"), None)
            if first is not None:
                total["to_success"].append(first)
                mine["to_success"].append(first)
                case_acc["acc"]["to_success"].append(first)

        updated = save.get("updated_at")
        players.append({
            "playerName": name,
            "actualCase": current,
            "cases": len(case_ids),
            "updated_at": updated.isoformat() if updated else None,
            **_rates(mine),
        })

    n = len(players)
    overall = _rates(total)
    top = sorted(taken_by.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:top_n]

    return {
        "totals": {
            "players": n,
            "abandon_rate": _pct(total["abandoned"], total["attempts"]),
            **overall,
        },
        "outcomes": [
            {"label": "Diagnóstico correcto", "count": outcomes["correct"]},
            {"label": "Diagnóstico incorrecto", "count": outcomes["incorrect"]},
            {"label": "Abandonado", "count": outcomes["abandoned"]},
            {"label": "En curso", "count": outcomes["in_progress"]},
        ],
        "players_per_case": [
            {"case": c, "players": players_per_case[c]}
            for c in sorted(players_per_case, key=natural_key)
        ],
        "cases": [
            {"case": c, "players": len(per_case[c]["players"]), **_rates(per_case[c]["acc"])}
            for c in sorted(per_case, key=natural_key)
        ],
        "top_decisions": [
            {"decision": d, "players": len(who),
             "percent": _pct(len(who), n) or 0, "relevant": relevant_flag.get(d)}
            for d, who in top
        ],
        "players": sorted(players, key=lambda p: p["updated_at"] or "", reverse=True),
    }
