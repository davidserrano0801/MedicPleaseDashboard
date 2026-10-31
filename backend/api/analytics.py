"""Validación del saveFile.json de Unity y cálculo de métricas del dashboard.

Este módulo no depende de Django ni de MongoDB para poder probarlo fácilmente.

Formato actual del save:
    {
      "playerName": "Alejandro",
      "actualCase": "Situacion1",
      "decisionsMade": ["¿Ha notado ...?", "Observar el Rostro"],
      "relevantDecisionsMade": ["Observar el Rostro"]      # opcional (aún no se guarda)
    }

- decisionsMade: todas las decisiones tomadas, en orden.
- relevantDecisionsMade (también se acepta relevantDecisionMade): las decisiones relevantes (correctas) que tomó el jugador.
  Si el campo no viene, las métricas de relevancia se muestran como "sin datos".
"""

MAX_NAME = 60
MAX_CASE = 100
MAX_DECISIONS = 2000
MAX_TEXT = 500


class ValidationError(ValueError):
    pass


def _clean_list(raw, field):
    if not isinstance(raw, list):
        raise ValidationError(f"{field} debe ser una lista de textos")
    if len(raw) > MAX_DECISIONS:
        raise ValidationError(f"{field} tiene demasiados elementos")
    result = []
    for item in raw:
        if isinstance(item, str):
            text = item.strip()
            if text:
                result.append(text[:MAX_TEXT])
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            result.append(str(item))
        else:
            raise ValidationError(f"{field} solo admite textos")
    return result


def validate_save(payload):
    """Devuelve un dict limpio listo para guardar o lanza ValidationError."""
    if not isinstance(payload, dict):
        raise ValidationError("El cuerpo debe ser un objeto JSON")

    name = str(payload.get("playerName", "")).strip()
    if not name:
        raise ValidationError("playerName es obligatorio")

    decisions = _clean_list(payload.get("decisionsMade", []), "decisionsMade")

    # None = el juego aún no envía este campo (distinto de lista vacía).
    # Acepta el nombre en plural y también la variante en singular.
    raw_relevant = payload.get("relevantDecisionsMade")
    if raw_relevant is None:
        raw_relevant = payload.get("relevantDecisionMade")
    relevant = None
    if raw_relevant is not None:
        relevant = _clean_list(raw_relevant, "relevantDecisionsMade")

    return {
        "playerName": name[:MAX_NAME],
        "actualCase": str(payload.get("actualCase", "")).strip()[:MAX_CASE],
        "decisionsMade": decisions,
        "relevantDecisionsMade": relevant,
    }


# ---------------------------------------------------------------- métricas

def natural_key(text):
    """'Situacion 10' va después de 'Situacion 2'."""
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text or "")]


def _player_stats(save):
    decisions = save.get("decisionsMade", []) or []
    relevant = save.get("relevantDecisionsMade")
    total = len(decisions)
    if relevant is None:
        relevant_count = None
        precision = None
    else:
        relevant_set = set(relevant)
        relevant_count = sum(1 for d in decisions if d in relevant_set)
        precision = round(100 * relevant_count / total, 1) if total else None
    return total, relevant_count, precision


def build_dashboard(saves, top_n=15):
    """`saves`: lista de documentos guardados en Mongo (con updated_at)."""
    players = []
    players_per_case = {}
    total_decisions = 0
    total_relevant = 0
    players_with_relevance = 0
    decisions_in_relevance_players = 0

    # decisión -> jugadores que la tomaron / jugadores que la marcaron relevante
    taken_by = {}
    relevant_flag = {}

    for save in saves:
        name = save.get("playerName", "")
        decisions = save.get("decisionsMade", []) or []
        relevant = save.get("relevantDecisionsMade")
        total, relevant_count, precision = _player_stats(save)

        case = save.get("actualCase") or "Sin caso"
        players_per_case[case] = players_per_case.get(case, 0) + 1

        total_decisions += total
        if relevant_count is not None:
            players_with_relevance += 1
            total_relevant += relevant_count
            decisions_in_relevance_players += total

        for d in set(decisions):
            taken_by.setdefault(d, set()).add(name)
            relevant_flag.setdefault(d, None)
        if relevant is not None:
            for d in set(decisions):
                relevant_flag[d] = bool(relevant_flag[d]) or d in set(relevant)
            # lo que está en 'relevant' pero no en 'decisions' también cuenta como relevante
            for d in relevant:
                relevant_flag[d] = True
                taken_by.setdefault(d, set()).add(name)

        updated = save.get("updated_at")
        players.append({
            "playerName": name,
            "actualCase": case,
            "decisions": total,
            "relevant": relevant_count,
            "precision": precision,
            "updated_at": updated.isoformat() if updated else None,
        })

    n = len(players)
    top = sorted(taken_by.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:top_n]

    return {
        "totals": {
            "players": n,
            "decisions": total_decisions,
            "avg_decisions_per_player": round(total_decisions / n, 2) if n else 0,
            "relevant_decisions": total_relevant if players_with_relevance else None,
            "precision": (round(100 * total_relevant / decisions_in_relevance_players, 1)
                          if decisions_in_relevance_players else None),
            "players_with_relevance": players_with_relevance,
        },
        "players_per_case": [
            {"case": c, "players": players_per_case[c]}
            for c in sorted(players_per_case, key=natural_key)
        ],
        "top_decisions": [
            {
                "decision": d,
                "players": len(who),
                "percent": round(100 * len(who) / n, 1) if n else 0,
                "relevant": relevant_flag.get(d),
            }
            for d, who in top
        ],
        "players": sorted(players, key=lambda p: p["updated_at"] or "", reverse=True),
    }
