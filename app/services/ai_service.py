"""AI Financial Coach service — Gemini-powered chat + proactive insights.

Requires GEMINI_API_KEY in environment. Gracefully degrades to a friendly
"please add your Gemini key" message when the SDK or key is missing.
"""
from __future__ import annotations

import os
from typing import List, Dict

from app.services import health_engine, dashboard_service


def is_available() -> bool:
    if not os.environ.get("GEMINI_API_KEY"):
        return False
    try:
        import google.genai  # noqa: F401
        return True
    except ImportError:
        return False


def build_financial_context(user) -> str:
    """Compact snapshot of the user's finances seeded into the system prompt."""
    profile = user.profile
    goals = user.goals
    from datetime import date
    today = date.today()
    health = health_engine.compute_health_score(user, today=today)
    nw = health_engine.compute_net_worth(user)
    monthly = dashboard_service.monthly_totals(user, today.month, today.year)

    lines = [
        f"User: {user.username}",
        f"Currency: INR (₹)",
        f"Financial Health Score: {health['total']}/100 ({health['grade']})",
        f"Net Worth: ₹{nw['net_worth']:,.0f}",
        f"This month — Income: ₹{monthly['income']:,.0f}, Spent: ₹{monthly['expenses']:,.0f}, Saved: ₹{monthly['savings']:,.0f}",
    ]
    if profile:
        lines.append(f"Income type: {profile.income_type}, monthly gross: ₹{float(profile.monthly_gross_income):,.0f}")
    if goals:
        goal_lines = [f"  - {g.name}: ₹{float(g.target_amount):,.0f} by {g.target_date} ({g.priority})" for g in goals[:5]]
        lines.append("Goals:\n" + "\n".join(goal_lines))
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
