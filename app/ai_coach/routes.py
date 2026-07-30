"""AI Coach routes — multi-turn Gemini chat."""
from datetime import datetime, timezone

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import AISession, AIMessage
from app.services import ai_service

ai_coach_bp = Blueprint("ai_coach", __name__, template_folder="../templates/ai_coach")


@ai_coach_bp.route("/")
@login_required
def index():
    sessions = (
        AISession.query.filter_by(user_id=current_user.id)
        .order_by(AISession.updated_at.desc())
        .all()
    )
    if not sessions:
        # Create a starter session so the chat UI is immediately usable
        s = AISession(user_id=current_user.id, session_title="Chat with paisa Coach")
        db.session.add(s)
        db.session.commit()
        return redirect(url_for("ai_coach.chat", session_id=s.id))
    return redirect(url_for("ai_coach.chat", session_id=sessions[0].id))


@ai_coach_bp.route("/chat/<uuid:session_id>", methods=["GET"])
@login_required
def chat(session_id):
    session = AISession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    sessions = AISession.query.filter_by(user_id=current_user.id).order_by(AISession.updated_at.desc()).all()
    insights = ai_service.generate_insights(current_user) if not session.messages else []
    return render_template(
        "ai_coach/chat.html",
        session=session, sessions=sessions,
        gemini_available=ai_service.is_available(),
        insights=insights,
    )


@ai_coach_bp.route("/chat/<uuid:session_id>/send", methods=["POST"])
@login_required
def send(session_id):
    session = AISession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    user_msg = (request.form.get("message") or "").strip()
    if not user_msg:
        return redirect(url_for("ai_coach.chat", session_id=session.id))

    db.session.add(AIMessage(session_id=session.id, role="user", content=user_msg))

    history = [{"role": m.role, "content": m.content} for m in session.messages]
    reply = ai_service.ask(current_user, history, user_msg)
    db.session.add(AIMessage(session_id=session.id, role="assistant", content=reply))

    # Auto-title the session from the first user message
    if session.session_title in ("New chat", "Chat with paisa Coach") and len(session.messages) == 0:
        session.session_title = (user_msg[:40] + "…") if len(user_msg) > 40 else user_msg

    session.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return redirect(url_for("ai_coach.chat", session_id=session.id) + "#latest")


@ai_coach_bp.route("/new", methods=["POST"])
@login_required
def new_session():
    s = AISession(user_id=current_user.id, session_title="New chat")
    db.session.add(s)
    db.session.commit()
    return redirect(url_for("ai_coach.chat", session_id=s.id))


@ai_coach_bp.route("/<uuid:session_id>/delete", methods=["POST"])
@login_required
def delete(session_id):
    s = AISession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    db.session.delete(s)
    db.session.commit()
    return redirect(url_for("ai_coach.index"))
