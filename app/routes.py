from flask import Blueprint,abort,flash,redirect,render_template_string,request,url_for
from flask_login import current_user,login_required,login_user,logout_user
from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from flask_wtf import FlaskForm
from markupsafe import escape
from wtforms import StringField,PasswordField,SelectField,TextAreaField,SubmitField
from wtforms.fields import SelectChoice
from wtforms.validators import DataRequired,Email,Length
from .extensions import db, limiter
from .models import User,BusinessApplication,AuditEvent
from . import PAGE
bp=Blueprint("main",__name__)
class RegisterForm(FlaskForm):
    full_name=StringField("Full name",validators=[DataRequired(),Length(min=2,max=120)])
    email=StringField("Email",validators=[DataRequired(),Email(),Length(max=254)])
    password=PasswordField("Password (12 characters minimum)",validators=[DataRequired(),Length(min=12,max=128)])
    submit=SubmitField("Create account")
class LoginForm(FlaskForm):
    email=StringField("Email",validators=[DataRequired(),Email()])
    password=PasswordField("Password",validators=[DataRequired()])
    submit=SubmitField("Sign in")
class ApplicationForm(FlaskForm):
    business_name=StringField("Business name",validators=[DataRequired(),Length(min=2,max=180)])
    business_type=StringField("Business type",validators=[DataRequired(),Length(min=2,max=100)])
    county=SelectField("County",choices=[SelectChoice(value=x, label=x) for x in ["Bomi","Bong","Gbarpolu","Grand Bassa","Grand Cape Mount","Grand Gedeh","Grand Kru","Lofa","Margibi","Maryland","Montserrado","Nimba","River Cess","River Gee","Sinoe"]],validators=[DataRequired()])
    description=TextAreaField("Business description",validators=[Length(max=4000)])
    submit=SubmitField("Submit application")
class ReviewForm(FlaskForm):
    status=SelectField("Decision",choices=[SelectChoice(value="approved",label="Approve"),SelectChoice(value="rejected",label="Reject")])
    review_notes=StringField("Review notes",validators=[Length(max=1000)])
    submit=SubmitField("Save decision")
def page(title,body): return render_template_string(PAGE,title=title,body=body)
def field(form,name,**attrs):
    f=getattr(form,name)
    return f'<label>{f.label.text}</label>{f(**attrs)}'+''.join(f'<p style="color:#b42318">{escape(e)}</p>' for e in f.errors)
@bp.route("/auth/register",methods=["GET","POST"])
@limiter.limit("5 per minute")
def register():
    if current_user.is_authenticated: return redirect(url_for("main.dashboard"))
    form=RegisterForm()
    if form.validate_on_submit():
        email=form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "warning")
        else:
            user = User(email=email, full_name=form.full_name.data.strip())
            user.set_password(form.password.data)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                # A concurrent registration may insert the same unique email
                # after the lookup above. Roll back and show a safe response.
                db.session.rollback()
                flash("An account with that email already exists.", "warning")
            else:
                login_user(user)
                flash("Account created. Submit your business application when ready.", "success")
                return redirect(url_for("main.dashboard"))
    body=f'<section class="panel"><h1>Create your account</h1><form method="post">{form.hidden_tag()}{field(form,"full_name",class_="input")}{field(form,"email",class_="input",autocomplete="email")}{field(form,"password",class_="input",autocomplete="new-password")}{form.submit(class_="button")}</form><p>Already registered? <a href="/auth/login">Sign in</a></p></section>'
    return page("Create account",body)
@bp.route("/auth/login",methods=["GET","POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated: return redirect(url_for("main.dashboard"))
    form=LoginForm()
    if form.validate_on_submit():
        user=User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.is_active and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for("main.dashboard"))
        flash("Email or password is incorrect.","danger")
    body=f'<section class="panel"><h1>Sign in</h1><form method="post">{form.hidden_tag()}{field(form,"email",class_="input",autocomplete="email")}{field(form,"password",class_="input",autocomplete="current-password")}{form.submit(class_="button")}</form><p>New here? <a href="/auth/register">Create an account</a></p></section>'
    return page("Sign in",body)
@bp.post("/auth/logout")
@login_required
def logout():
    logout_user(); flash("You have been signed out.","success"); return redirect(url_for("index"))
@bp.get("/dashboard")
@login_required
def dashboard():
    items=BusinessApplication.query.filter_by(owner_id=current_user.id).order_by(BusinessApplication.created_at.desc()).all()
    body='<section class="panel"><h1>Welcome, '+str(escape(current_user.full_name))+'</h1><p>Manage your business applications and track their review status.</p><a class="button" href="/applications/new">New business application</a></section><section class="panel"><h2>Your applications</h2>'
    if not items: body+='<p>No applications yet. Submit your first business application to get started.</p>'
    for x in items:
        body+=f'<article><h3>{escape(x.business_name)}</h3><p>{escape(x.business_type)} · {escape(x.county)} County</p><span class="status {x.status}">{x.status.title()}</span><p>{escape(x.review_notes)}</p>' + (f'<p><a href="/applications/{x.id}/edit">Edit pending application</a></p>' if x.status == "pending" else "") + '</article><hr>'
    return page("Dashboard",body+'</section>')
@bp.route("/applications/new",methods=["GET","POST"])
@login_required
def new_application():
    form=ApplicationForm()
    if form.validate_on_submit():
        item=BusinessApplication(owner_id=current_user.id,business_name=form.business_name.data.strip(),business_type=form.business_type.data.strip(),county=form.county.data,description=(form.description.data or "").strip())
        db.session.add(item)
        db.session.flush()
        db.session.add(AuditEvent(
            actor_user_id=current_user.id,
            application_id=item.id,
            event_type="application_submitted",
            previous_status="none",
            new_status="pending",
            notes="Business application submitted.",
        ))
        db.session.commit()
        flash("Application submitted for review.", "success")
        return redirect(url_for("main.dashboard"))
    body=f'<section class="panel"><h1>Business application</h1><p>Provide accurate information. An administrator will review your submission.</p><form method="post">{form.hidden_tag()}{field(form,"business_name",class_="input")}{field(form,"business_type",class_="input")}{field(form,"county",class_="input")}{field(form,"description",class_="input",rows=4)}{form.submit(class_="button")}</form></section>'
    return page("New application",body)
@bp.get("/directory")
def directory():
    # Bound query inputs and paginate public results so the directory remains
    # responsive as the number of approved businesses grows.
    search_term = request.args.get("q", "").strip()[:100]
    county = request.args.get("county", "").strip()
    business_type = request.args.get("type", "").strip()[:100]
    page_number = request.args.get("page", 1, type=int) or 1
    valid_counties = [
        "Bomi", "Bong", "Gbarpolu", "Grand Bassa", "Grand Cape Mount",
        "Grand Gedeh", "Grand Kru", "Lofa", "Margibi", "Maryland",
        "Montserrado", "Nimba", "River Cess", "River Gee", "Sinoe",
    ]
    query = BusinessApplication.query.filter_by(status="approved")
    if search_term:
        escaped_search = search_term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped_search}%"
        query = query.filter(
            or_(
                BusinessApplication.business_name.ilike(pattern, escape="\\"),
                BusinessApplication.business_type.ilike(pattern, escape="\\"),
                BusinessApplication.description.ilike(pattern, escape="\\"),
            )
        )
    if county in valid_counties:
        query = query.filter_by(county=county)
    else:
        county = ""
    if business_type:
        escaped_type = business_type.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(
            BusinessApplication.business_type.ilike(f"%{escaped_type}%", escape="\\")
        )
    pagination = query.order_by(BusinessApplication.business_name.asc()).paginate(
        page=max(page_number, 1), per_page=25, error_out=False
    )
    body = (
        '<section class="panel"><h1>Liberian business directory</h1>'
        '<p>Only applications approved by administrators appear here.</p>'
        '<form method="get" action="/directory">'
        f'<label for="directory-q">Search businesses</label><input class="input" id="directory-q" name="q" value="{escape(search_term)}" maxlength="100" placeholder="Name, category or description">'
        '<label for="directory-county">County</label><select class="input" id="directory-county" name="county"><option value="">All counties</option>'
    )
    for option in valid_counties:
        selected = ' selected' if county == option else ''
        body += f'<option value="{escape(option)}"{selected}>{escape(option)}</option>'
    body += (
        '</select><label for="directory-type">Business type</label>'
        f'<input class="input" id="directory-type" name="type" value="{escape(business_type)}" maxlength="100" placeholder="e.g. Retail">'
        '<button class="button" type="submit">Search directory</button> '
        '<a href="/directory">Clear filters</a></form>'
    )
    if not pagination.items:
        body += '<p>No approved businesses match those filters.</p>'
    for item in pagination.items:
        body += (
            f'<article><h2>{escape(item.business_name)}</h2>'
            f'<p>{escape(item.business_type)} · {escape(item.county)} County</p>'
            f'<p>{escape(item.description)}</p>'
            f'<p><a href="{url_for("main.public_business_profile", application_id=item.id)}">View business profile</a></p>'
            '<span class="status approved">Approved</span></article><hr>'
        )
    if pagination.pages > 1:
        body += '<nav aria-label="Directory pages">'
        if pagination.has_prev:
            body += f'<a href="{url_for("main.directory", q=search_term, county=county, type=business_type, page=pagination.prev_num)}">Previous</a> '
        body += f'<span>Page {pagination.page} of {pagination.pages}</span>'
        if pagination.has_next:
            body += f' <a href="{url_for("main.directory", q=search_term, county=county, type=business_type, page=pagination.next_num)}">Next</a>'
        body += '</nav>'
    return page("Business directory", body + '</section>')
@bp.get("/admin/applications")
@login_required
def admin_applications():
    if not current_user.is_admin: abort(403)
    items=BusinessApplication.query.order_by(BusinessApplication.created_at.asc()).all()
    body='<section class="panel"><h1>Applications for review</h1>'
    if not items: body+='<p>No applications to review.</p>'
    for x in items:
        body+=f'<article><h2>{escape(x.business_name)}</h2><p>{escape(x.business_type)} · {escape(x.county)} County</p><p>Applicant: {escape(x.owner.email)}</p><span class="status {x.status}">{x.status.title()}</span> <a href="/admin/applications/{x.id}/review">Review</a></article><hr>'
    return page("Admin review",body+'</section>')
@bp.route("/admin/applications/<int:application_id>/review",methods=["GET","POST"])
@login_required
def review(application_id):
    if not current_user.is_admin: abort(403)
    item=db.get_or_404(BusinessApplication,application_id); form=ReviewForm(status=item.status if item.status in {"approved","rejected"} else "approved",review_notes=item.review_notes)
    if form.validate_on_submit():
        # Make the pending -> final transition atomic. Two administrators can
        # load the same pending record; a conditional UPDATE ensures only one
        # decision can win, even when requests run concurrently.
        previous_status = item.status
        decision_notes = (form.review_notes.data or "").strip()
        result = db.session.execute(
            update(BusinessApplication)
            .where(
                BusinessApplication.id == application_id,
                BusinessApplication.status == "pending",
            )
            .values(
                status=form.status.data,
                review_notes=decision_notes,
            )
        )
        if result.rowcount != 1:
            db.session.rollback()
            flash("This application has already been reviewed. A new review decision cannot overwrite the original decision.", "warning")
            return redirect(url_for("main.admin_applications"))
        db.session.add(AuditEvent(
            actor_user_id=current_user.id,
            application_id=application_id,
            event_type="application_reviewed",
            previous_status=previous_status,
            new_status=form.status.data,
            notes=decision_notes,
        ))
        # Commit the decision and audit record atomically.
        db.session.commit()
        flash("Application review saved.","success")
        return redirect(url_for("main.admin_applications"))
    body=f'<section class="panel"><h1>Review {escape(item.business_name)}</h1><p>{escape(item.business_type)} · {escape(item.county)} County</p><p>{escape(item.description)}</p><form method="post">{form.hidden_tag()}{field(form,"status",class_="input")}{field(form,"review_notes",class_="input")}{form.submit(class_="button")}</form></section>'
    return page("Review application",body)


@bp.route("/applications/<int:application_id>/edit", methods=["GET", "POST"])
@login_required
def edit_application(application_id):
    # Scope the lookup to the current owner before revealing any record details.
    item = BusinessApplication.query.filter_by(
        id=application_id, owner_id=current_user.id
    ).first_or_404()
    if item.status != "pending":
        flash("Only pending applications can be edited. Contact an administrator if a correction is needed after review.", "warning")
        return redirect(url_for("main.dashboard"))

    form = ApplicationForm(obj=item)
    if form.validate_on_submit():
        # A conditional update prevents a stale edit form from changing a record
        # that an administrator reviewed while the owner was editing.
        result = db.session.execute(
            update(BusinessApplication)
            .where(
                BusinessApplication.id == application_id,
                BusinessApplication.owner_id == current_user.id,
                BusinessApplication.status == "pending",
            )
            .values(
                business_name=form.business_name.data.strip(),
                business_type=form.business_type.data.strip(),
                county=form.county.data,
                description=(form.description.data or "").strip(),
            )
        )
        if result.rowcount != 1:
            db.session.rollback()
            flash("This application is no longer editable because its review status changed.", "warning")
            return redirect(url_for("main.dashboard"))
        db.session.add(AuditEvent(
            actor_user_id=current_user.id,
            application_id=application_id,
            event_type="application_updated",
            previous_status="pending",
            new_status="pending",
            notes="Owner updated business application details.",
        ))
        db.session.commit()
        flash("Your pending application has been updated.", "success")
        return redirect(url_for("main.dashboard"))

    body = (
        f'<section class="panel"><h1>Edit pending application</h1>'
        '<p>You can update your details while this application is awaiting review.</p>'
        f'<form method="post">{form.hidden_tag()}'
        f'{field(form, "business_name", class_="input")}'
        f'{field(form, "business_type", class_="input")}'
        f'{field(form, "county", class_="input")}'
        f'{field(form, "description", class_="input", rows=4)}'
        f'{form.submit(class_="button")}</form>'
        '<p><a href="/dashboard">Return to dashboard</a></p></section>'
    )
    return page("Edit pending application", body)


@bp.get("/directory/<int:application_id>")
def public_business_profile(application_id):
    # Never disclose pending or rejected applications through public profile URLs.
    item = BusinessApplication.query.filter_by(
        id=application_id, status="approved"
    ).first_or_404()
    body = (
        '<section class="panel"><p class="green"><b>VERIFIED DIRECTORY LISTING</b></p>'
        f'<h1>{escape(item.business_name)}</h1>'
        f'<p><b>Business type:</b> {escape(item.business_type)}</p>'
        f'<p><b>Location:</b> {escape(item.county)} County, Liberia</p>'
        f'<h2>About this business</h2><p>{escape(item.description)}</p>'
        '<span class="status approved">Approved</span>'
        '<p><a href="/directory">Back to directory</a></p></section>'
    )
    return page("Business profile", body)
