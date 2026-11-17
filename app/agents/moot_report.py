"""Deterministic post-hearing assessment of the frozen text record."""

import re

from app.agents.moot_assessment import PointAssessment, update_leaning

LABEL = "Practice simulation, not a prediction of a real court outcome"
INJECTION = re.compile(r"give me\s+100\s*%|ignore (?:all |previous |your )?instructions", re.I)


def eligible_turns(history):
    seen = set()
    for turn_id, turn in enumerate(history, 1):
        argument = turn["argument"]
        claim = " ".join(re.findall(r"\w+", argument["claim"].casefold()))
        if not claim or claim in seen or INJECTION.search(turn["text"]):
            continue
        seen.add(claim)
        yield turn_id, turn


def VerdictAgent(points, authorities, side):
    gaps = []
    if len(points) < 3:
        gaps.append("Fewer than three distinct submissions.")
    if not authorities:
        gaps.append("No verified authority found.")
    if any(point.contradiction > 0 or point.unanswered > 0 for _, _, point in points):
        gaps.append("A recorded contradiction or bench question remains unresolved.")
    supported = sum(point.strength * point.factual_consistency for _, _, point in points)
    if points and supported / len(points) < 0.5:
        gaps.append("The record does not sufficiently support the submissions.")
    return {
        "status": "reserved" if gaps else "decided",
        "issues": [
            {"turn_id": turn_id, "question": "Does the record support the submission on this turn?",
             "reasoning": "The recorded submission has stronger factual support."
             if point.factual_consistency >= 0.5 else "The recorded factual support is limited."}
            for turn_id, _, point in points
        ],
        "order": "Order reserved pending the identified gaps." if gaps else (
            "For this exercise, the petition is allowed."
            if side == "petitioner" else "For this exercise, the petition is dismissed."
        ),
        "material_gaps": gaps,
        "authorities": list(authorities.values()),
    }


def ScoringAgent(points, weights, side, authority_count):
    fields = {
        "legal_reasoning": "strength", "precedent": "precedent", "statute": "statute",
        "facts": "factual_consistency", "bench_responsiveness": "responsiveness",
    }
    rubric = {}
    issue_weights = [point.confidence * point.factual_consistency for _, _, point in points]
    weight_total = sum(issue_weights)
    axis = (
        sum(weight * update_leaning(50, point, side)
            for weight, (_, _, point) in zip(issue_weights, points)) / weight_total
        if weight_total else 50
    )
    for dimension, weight in weights.items():
        values = []
        for turn_id, turn, point in points:
            if dimension == "rebuttal":
                status = turn["argument"]["rebuttal_status"].strip().casefold()
                if status in {"answered", "rebutted", "partial", "unanswered"}:
                    values.append((turn_id, {"answered": 1, "rebutted": 1, "partial": 0.5, "unanswered": 0}[status]))
            elif dimension != "bench_responsiveness" or turn_id > 1:
                values.append((turn_id, getattr(point, fields[dimension])))
        rating = round(4 * sum(value for _, value in values) / len(values), 2) if values else None
        rubric[dimension] = {"weight": weight, "rating": rating,
                            "status": "assessed" if values else "unassessed",
                            "turn_ids": [turn_id for turn_id, _ in values]}
    coverage = sum(row["weight"] for row in rubric.values() if row["rating"] is not None)
    score = (
        round(sum(row["weight"] * row["rating"] / 4 for row in rubric.values()
                  if row["rating"] is not None) * 100 / coverage, 2)
        if coverage else None
    )
    band = {"label": LABEL, "status": "insufficient evidence for a range"}
    if len(points) >= 2 and coverage >= 50:
        confidence = sum(point.confidence for _, _, point in points) / len(points)
        if confidence >= 0.35:
            penalty = max(0, 5 - len(points)) * 2 + (0 if authority_count else 8) + (100 - coverage) / 10
            side_view = axis if side == "petitioner" else 100 - axis
            center = min(85, max(15, 0.6 * score + 0.4 * side_view - penalty))
            radius = 7 + penalty / 2 + 8 * (1 - confidence)
            band.update(status="available", low=max(0, round(center - radius)), high=min(100, round(center + radius)))
    return {"rubric": rubric, "score": score, "win_chance": band}


def CoachAgent(history, points, side, missed):
    questions = [
        {"question_turn_id": turn_id - 1, "answer_turn_id": turn_id,
         "advice": (
             "Answer the bench directly and cite the page that supports the requested relief."
             if side == "petitioner" else
             "Answer the bench directly and identify the missing element or the contrary record page."
         )}
        for turn_id, _, point in points if turn_id > 1 and
        history[turn_id - 2]["reply"].rstrip().endswith("?") and point.responsiveness < 0.75
    ]
    return {
        "side": side,
        "unused_points": [
            "Tie each requested remedy to a specific issue and record citation."
            if side == "petitioner" else
            "Test whether the record establishes each element required for the requested remedy."
        ],
        "bench_answers": questions,
        "missed_authorities": missed,
    }


def SpeechStyleAnalyzer(history):
    words = [re.findall(r"\w+", turn["text"].casefold()) for turn in history]
    fillers = {"um", "uh", "erm", "hmm", "मतलब"}
    return {
        "pace": "unavailable", "pauses": "unavailable",
        "turns": [
            {"turn_id": index, "word_count": len(tokens),
             "filler_count": sum(token in fillers for token in tokens),
             "etiquette_marker": bool(re.search(
                 r"my lord|your lordship|your honour|माननीय", turn["text"], re.I
             ))}
            for index, (turn, tokens) in enumerate(zip(history, words), 1)
        ],
    }


def build_report(state, authorities, weights):
    history = state["history"]
    side = state["setup"]["side"]
    points = []
    used = {}
    for turn_id, turn in eligible_turns(history):
        verified = {item["id"]: authorities[item["id"]] for item in turn["authorities"]
                    if item["id"] in authorities}
        used.update(verified)
        assessment = PointAssessment.model_validate(turn["leaning_change"]["assessment"])
        if not verified:
            assessment.precedent = 0
        points.append((turn_id, turn, assessment))
    verdict = VerdictAgent(points, used, side)
    scoring = ScoringAgent(points, weights, side, len(used))
    coaching = CoachAgent(history, points, side, [
        item for key, item in authorities.items() if key not in used
    ])
    speech = SpeechStyleAnalyzer(history)
    return {"verdict": verdict, "scoring": scoring, "coaching": coaching, "speech_style": speech}

