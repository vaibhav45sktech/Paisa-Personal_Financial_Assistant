"""Full reasoning behind the ranked recommendations.

The ranking and every figure come from the deterministic engines. Gemini is
called only to reword the #1 recommendation's reason, and only when a key is
configured — the page renders identically without it.
"""
from datetime import date

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from app.services import (
    financial_context_service, priority_engine, explainability_service,
    consent_service, ai_service,
)

recommendations_bp = Blueprint(
    "recommendations", __name__, template_folder="../templates/recommendations"
)


@recommendations_bp.route("/")
@login_required
def index():
    today = date.today()
    ctx = financial_context_service.build_context(current_user, today=today)
    ranked = priority_engine.rank(ctx, limit=3)

    # Opt-out so the page can be read without waiting on the model.
    use_ai = request.args.get("plain") != "1"

    explained = []
    for i, rec in enumerate(ranked):
        phrasing = (
            ai_service.phrase_recommendation(rec, ctx)
            if (use_ai and i == 0) else None
        )
        explained.append({
            "rec": rec,
            "detail": explainability_service.explain(rec, ctx, phrasing=phrasing),
        })

    return render_template(
        "recommendations/index.html",
        ctx=ctx,
        metrics=ctx["metrics"],
        zone=ctx["zone"],
        zone_label=financial_context_service.ZONE_LABELS[ctx["zone"]],
        zone_style=explainability_service.ZONE_STYLES[ctx["zone"]],
        explained=explained,
        factors=explainability_service.decision_factors(ctx),
        breakdown=explainability_service.score_breakdown(ctx),
        consent_summary=consent_service.summary(current_user.id),
        ai_available=ai_service.is_available(),
        all_clear=priority_engine.ALL_CLEAR if not ranked else None,
    )
