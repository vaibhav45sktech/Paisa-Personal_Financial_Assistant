"""AI Financial Coach service — Gemini-powered chat + proactive insights.

Requires GEMINI_API_KEY in environment. Gracefully degrades to a friendly
"please add your Gemini key" message when the SDK or key is missing.
"""
from __future__ import annotations

import os
from typing import List, Dict

from app.services import health_engine, dashboard_service, consent_service

# Everything the coach sends to Gemini is gated on this purpose.
AI_PURPOSE = "ai_assistant"


def is_available() -> bool:
    if not os.environ.get("GEMINI_API_KEY"):
        return False
    try:
        import google.genai  # noqa: F401
        return True
    except ImportError:
        return False


def build_financial_context(user) -> str:
    """Compact snapshot of the user's finances seeded into the system prompt.

    Consent-gated per data category: anything the user has revoked for the AI
    assistant is left out of the prompt entirely, so revoked data never leaves
    the application. The coach degrades to whatever remains.
    """
    from datetime import date
    today = date.today()

    def allowed(category: str) -> bool:
        return consent_service.has_consent(user.id, category, AI_PURPOSE)

    lines = [f"User: {user.username}", "Currency: INR (₹)"]

    # The score aggregates income, expenses, accounts and assets, so it may only
    # be shared when the underlying inputs are all consented for this purpose.
    score_inputs = ("income", "expenses", "profile")
    if all(allowed(c) for c in score_inputs):
        health = health_engine.compute_health_score(user, today=today)
        nw = health_engine.compute_net_worth(user)
        lines.append(f"Financial Health Score: {health['total']}/100 ({health['grade']})")
        lines.append(f"Net Worth: ₹{nw['net_worth']:,.0f}")

    if allowed("income") and allowed("expenses"):
        monthly = dashboard_service.monthly_totals(user, today.month, today.year)
        lines.append(
            f"This month — Income: ₹{monthly['income']:,.0f}, "
            f"Spent: ₹{monthly['expenses']:,.0f}, Saved: ₹{monthly['savings']:,.0f}"
        )

    if user.profile and allowed("profile"):
        lines.append(
            f"Income type: {user.profile.income_type}, "
            f"monthly gross: ₹{float(user.profile.monthly_gross_income):,.0f}"
        )

    if user.goals and allowed("goals"):
        goal_lines = [
            f"  - {g.name}: ₹{float(g.target_amount):,.0f} by {g.target_date} ({g.priority})"
            for g in user.goals[:5]
        ]
        lines.append("Goals:\n" + "\n".join(goal_lines))

    withheld = [
        consent_service.CATEGORY_LABELS.get(c, c)
        for c in consent_service.PURPOSE_CATEGORIES[AI_PURPOSE]
        if not allowed(c)
    ]
    if withheld:
        lines.append(
            "NOTE: the user has not shared " + ", ".join(withheld).lower() +
            " with you. Do not speculate about the missing figures — say you "
            "don't have them and point to the Consent Center."
        )
    return "\n".join(lines)


SYSTEM_INSTRUCTION = (
    "You are 'paisa Coach', a friendly, encouraging personal finance assistant for an Indian user. "
    "Give short, practical, tactical advice using INR (₹) and Indian numbering. "
    "Cite the user's numbers when relevant. Avoid generic disclaimers. Keep responses under 220 words unless asked to elaborate. "
    "Format bullet points with '- ' and use **bold** sparingly."
)


def ask(user, history: List[Dict[str, str]], user_message: str) -> str:
    """Send a multi-turn chat to Gemini, seeded with live financial context."""
    if not is_available():
        return (
            "⚠️ Gemini isn't configured yet. Add `GEMINI_API_KEY=your-key` to your `.env` "
            "and install the SDK with `pip install google-genai`, then restart the app. "
            "Get a free key at https://aistudio.google.com/."
        )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    context = build_financial_context(user)

    contents = []
    for m in history:
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=m["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

    try:
        resp = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION + "\n\nLIVE CONTEXT:\n" + context,
                temperature=0.7,
                max_output_tokens=600,
            ),
        )
        return (resp.text or "").strip() or "Sorry, I couldn't come up with a reply. Try rephrasing?"
    except Exception as exc:
        return f"⚠️ Gemini error: {exc}. Please check your key and quota."


PHRASING_INSTRUCTION = (
    "You are the explanation layer of a financial health assistant. "
    "A deterministic rules engine has ALREADY decided this recommendation and "
    "calculated every figure. Your only job is to restate the supplied reason in "
    "warm, plain English for an Indian user.\n"
    "HARD RULES:\n"
    "- Use ONLY the numbers given. Never introduce, recompute or round a figure.\n"
    "- Never contradict, re-rank, or second-guess the recommendation.\n"
    "- Never suggest a loan, credit card, BNPL or any borrowing.\n"
    "- 2 to 3 sentences, under 60 words. No bullet points, no headings, no emoji.\n"
    "- Address the user as 'you'. Do not open with a greeting."
)


def phrase_recommendation(recommendation: dict, ctx: dict) -> str | None:
    """Ask Gemini to reword the engine's reason. Returns None on any failure.

    Only the already-computed, already-consented figures behind this one
    recommendation are sent — never the raw ledger.
    """
    if not is_available():
        return None

    from google import genai
    from google.genai import types

    facts = "\n".join(
        f"- {k}: {v}" for k, v in (recommendation.get("explanation_data") or {}).items()
    )
    prompt = (
        f"Recommendation: {recommendation['title']}\n"
        f"Severity: {recommendation['severity']}\n"
        f"Engine's reason: {recommendation.get('reason', '')}\n"
        f"Supporting figures:\n{facts}\n\n"
        "Restate the reason in plain English."
    )

    try:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        resp = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=PHRASING_INSTRUCTION,
                temperature=0.4,
                max_output_tokens=180,
            ),
        )
        text = (resp.text or "").strip()
        return text or None
    except Exception:
        # The engine's own wording is always a valid fallback — the feature
        # must never depend on the model being reachable.
        return None


def generate_insights(user) -> list[str]:
    """One-shot proactive insights based on live context. Returns list of tips."""
    if not is_available():
        return []
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    context = build_financial_context(user)
    prompt = (
        "Given the user's current finances below, give exactly 3 short, punchy, actionable insights or nudges. "
        "Each starts with an emoji, is under 20 words, and cites a number where possible. Return ONE per line, no numbering.\n\n"
        + context
    )
    try:
        resp = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.6, max_output_tokens=250),
        )
        text = (resp.text or "").strip()
        return [ln.strip("- ").strip() for ln in text.splitlines() if ln.strip()][:3]
    except Exception:
        return []
