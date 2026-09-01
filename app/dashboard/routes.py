"""Dashboard routes."""
from datetime import date

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.services import (
    health_engine, dashboard_service, financial_context_service, priority_engine,
    explainability_service, consent_service,
)

dashboard_bp = Blueprint(
    "dashboard", __name__, template_folder="../templates/dashboard"
)


@dashboard_bp.route("/")
@login_required
def index():
    profile = current_user.profile
    goals = current_user.goals
    accounts = current_user.accounts
    assets = current_user.assets

    today = date.today()
    net_worth = health_engine.compute_net_worth(current_user)
    avb_rows = dashboard_service.actual_vs_budget(current_user, today.month, today.year)
    monthly = dashboard_service.monthly_totals(current_user, today.month, today.year)

    total_goals_amount = float(sum(g.target_amount for g in goals))
    summary = {
        "profile_completed": profile is not None,
        "goals_created": len(goals) > 0,
        "goals_count": len(goals),
        "accounts_count": len(accounts),
        "assets_count": len(assets),
        "monthly_gross_income": float(profile.monthly_gross_income) if profile else 0.0,
        "total_monthly_budget": profile.total_budget if profile else 0.0,
        "estimated_savings": profile.estimated_savings if profile else 0.0,
        "total_goals_amount": total_goals_amount,
    }

    budget_map = profile.budget_map if profile else {}
    budget_rows = sorted(
        [(k, v) for k, v in budget_map.items() if v > 0],
        key=lambda x: x[1], reverse=True,
    )

    # Deterministic decision layer. No AI phrasing here — the dashboard stays
    # fast and works identically with or without a Gemini key.
    ctx = financial_context_service.build_context(current_user, today=today)
    # Withheld when the ledger has no expenses — an unscored month would
    # otherwise read as a perfect one. See financial_context_service.
    health = ctx["health"]
    priorities = priority_engine.rank(ctx, limit=3)
    nba = priorities[0] if priorities else None
    nba_explained = (
        explainability_service.explain(nba, ctx) if nba else None
    )

    return render_template(
        "dashboard/index.html",
        summary=summary,
        profile=profile,
        goals=goals,
        budget_rows=budget_rows,
        health=health,
        net_worth=net_worth,
        actual_vs_budget=avb_rows,
        monthly=monthly,
        today=today,
        ctx=ctx,
        metrics=ctx["metrics"],
        zone=ctx["zone"],
        zone_label=financial_context_service.ZONE_LABELS[ctx["zone"]],
        zone_style=explainability_service.ZONE_STYLES[ctx["zone"]],
        priorities=priorities,
        next_best_action=nba,
        nba_explained=nba_explained,
        severity_styles=explainability_service.SEVERITY_STYLES,
        consent_summary=consent_service.summary(current_user.id),
    )
