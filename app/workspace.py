from flask import Blueprint, abort, request
from flask_login import current_user, login_required
from markupsafe import escape
from sqlalchemy import or_
from .models import AuditEvent, BusinessApplication, User
from .routes import page

bp = Blueprint("workspace", __name__)


@bp.get("/dashboard/overview")
@login_required
def owner_overview():
    query = BusinessApplication.query.filter_by(owner_id=current_user.id)
    counts = {
        status: query.filter_by(status=status).count()
        for status in ("pending", "approved", "rejected")
    }
    total = query.count()
    ids = [row[0] for row in query.with_entities(BusinessApplication.id).all()]
    events = []
    if ids:
        events = (AuditEvent.query.filter(AuditEvent.application_id.in_(ids))
                  .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
                  .limit(15).all())
    body = (
        '<section class="panel"><p class="green"><b>BUSINESS WORKSPACE</b></p>'
        '<h1>Your business overview</h1>'
        '<p>Track your applications and recent review activity in one place.</p>'
        '<a class="button" href="/applications/new">Start an application</a> '
        '<a class="button" style="background:#102b46" href="/dashboard">My applications</a></section>'
        '<section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px">'
        f'<article class="panel"><p>Applications</p><h2>{total}</h2></article>'
        f'<article class="panel"><p>Pending</p><h2>{counts["pending"]}</h2></article>'
        f'<article class="panel"><p>Approved</p><h2>{counts["approved"]}</h2></article>'
        f'<article class="panel"><p>Rejected</p><h2>{counts["rejected"]}</h2></article>'
        '</section><section class="panel"><h2>Recent activity</h2>'
    )
    if not events:
        body += "<p>No application activity yet. Submissions and updates will appear here.</p>"
    for event in events:
        body += (
            f'<article><b>{escape(event.event_type.replace("_", " ").title())}</b>'
            f'<p>{escape(event.notes or "")}</p>'
            f'<p class="muted">Status: {escape(event.previous_status)} → {escape(event.new_status)}'
            f' · {escape(event.created_at.strftime("%Y-%m-%d %H:%M UTC"))}</p></article><hr>'
        )
    return page("Business overview", body + "</section>")


@bp.get("/admin/overview")
@login_required
def admin_overview():
    if not current_user.is_admin:
        abort(403)
    q = request.args.get("q", "").strip()[:100]
    status = request.args.get("status", "").strip()
    county = request.args.get("county", "").strip()
    counties = [
        "Bomi", "Bong", "Gbarpolu", "Grand Bassa", "Grand Cape Mount",
        "Grand Gedeh", "Grand Kru", "Lofa", "Margibi", "Maryland",
        "Montserrado", "Nimba", "River Cess", "River Gee", "Sinoe",
    ]
    statuses = ("pending", "approved", "rejected")
    query = BusinessApplication.query
    if q:
        term = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{term}%"
        query = query.filter(or_(
            BusinessApplication.business_name.ilike(pattern, escape="\\"),
            BusinessApplication.owner.has(or_(
                User.email.ilike(pattern, escape="\\"),
                User.full_name.ilike(pattern, escape="\\"),
            )),
        ))
    if status in statuses:
        query = query.filter_by(status=status)
    else:
        status = ""
    if county in counties:
        query = query.filter_by(county=county)
    else:
        county = ""
    counts = {s: BusinessApplication.query.filter_by(status=s).count() for s in statuses}
    pagination = query.order_by(
        BusinessApplication.created_at.desc(), BusinessApplication.id.desc()
    ).paginate(page=max(request.args.get("page", 1, type=int) or 1, 1),
               per_page=25, error_out=False)
    body = (
        '<section class="panel"><p class="green"><b>ADMINISTRATION</b></p>'
        '<h1>Business management</h1>'
        '<p>Search applications, prioritize pending reviews, and monitor the approval pipeline.</p>'
        f'<p><b>Pending:</b> {counts["pending"]} &nbsp; <b>Approved:</b> {counts["approved"]}'
        f' &nbsp; <b>Rejected:</b> {counts["rejected"]}</p>'
        '<form method="get" action="/admin/overview">'
        f'<label for="q">Business or applicant</label><input id="q" class="input" name="q" value="{escape(q)}" maxlength="100" placeholder="Business, owner name or email">'
        '<label for="status">Status</label><select class="input" id="status" name="status">'
    )
    for value, label in [("", "All statuses"), ("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")]:
        selected = " selected" if status == value else ""
        body += f'<option value="{value}"{selected}>{label}</option>'
    body += '</select><label for="county">County</label><select class="input" id="county" name="county"><option value="">All counties</option>'
    for value in counties:
        selected = " selected" if county == value else ""
        body += f'<option value="{escape(value)}"{selected}>{escape(value)}</option>'
    body += '<button class="button" type="submit">Apply filters</button> <a href="/admin/overview">Clear</a></form></section>'
    body += '<section class="panel"><h2>Applications</h2>'
    if not pagination.items:
        body += "<p>No applications match these filters.</p>"
    for item in pagination.items:
        body += (
            f'<article><h3>{escape(item.business_name)}</h3>'
            f'<p>{escape(item.business_type)} · {escape(item.county)} County</p>'
            f'<p>Applicant: {escape(item.owner.full_name)} ({escape(item.owner.email)})</p>'
            f'<span class="status {escape(item.status)}">{escape(item.status.title())}</span> '
            f'<a href="/admin/applications/{item.id}/review">Open review</a></article><hr>'
        )
    if pagination.pages > 1:
        body += '<nav aria-label="Application pages">'
        if pagination.has_prev:
            body += f'<a href="/admin/overview?q={escape(q)}&status={escape(status)}&county={escape(county)}&page={pagination.prev_num}">Previous</a> '
        body += f'Page {pagination.page} of {pagination.pages}'
        if pagination.has_next:
            body += f' <a href="/admin/overview?q={escape(q)}&status={escape(status)}&county={escape(county)}&page={pagination.next_num}">Next</a>'
        body += "</nav>"
    return page("Business management", body + "</section>")
