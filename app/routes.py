from flask import Blueprint,abort,flash,redirect,render_template_string,request,url_for
from flask_login import current_user,login_required,login_user,logout_user
from flask_wtf import FlaskForm
from wtforms import StringField,PasswordField,SelectField,TextAreaField,SubmitField
from wtforms.validators import DataRequired,Email,Length
from .extensions import db
from .models import User,BusinessApplication
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
    county=SelectField("County",choices=[(x,x) for x in ["Bomi","Bong","Gbarpolu","Grand Bassa","Grand Cape Mount","Grand Gedeh","Grand Kru","Lofa","Margibi","Maryland","Montserrado","Nimba","River Cess","River Gee","Sinoe"]],validators=[DataRequired()])
    description=TextAreaField("Business description",validators=[Length(max=4000)])
    submit=SubmitField("Submit application")
class ReviewForm(FlaskForm):
    status=SelectField("Decision",choices=[("approved","Approve"),("rejected","Reject")])
    review_notes=StringField("Review notes",validators=[Length(max=1000)])
    submit=SubmitField("Save decision")
def page(title,body): return render_template_string(PAGE,title=title,body=body)
def field(form,name,**attrs):
    f=getattr(form,name)
    return f'<label>{f.label.text}</label>{f(**attrs)}'+''.join(f'<p style="color:#b42318">{e}</p>' for e in f.errors)
@bp.route("/auth/register",methods=["GET","POST"])
def register():
    if current_user.is_authenticated: return redirect(url_for("main.dashboard"))
    form=RegisterForm()
    if form.validate_on_submit():
        email=form.email.data.strip().lower()
        if User.query.filter_by(email=email).first(): flash("An account with that email already exists.","warning")
        else:
            user=User(email=email,full_name=form.full_name.data.strip()); user.set_password(form.password.data)
            db.session.add(user); db.session.commit(); login_user(user)
            flash("Account created. Submit your business application when ready.","success")
            return redirect(url_for("main.dashboard"))
    body=f'<section class="panel"><h1>Create your account</h1><form method="post">{form.hidden_tag()}{field(form,"full_name",class_="input")}{field(form,"email",class_="input",autocomplete="email")}{field(form,"password",class_="input",autocomplete="new-password")}{form.submit(class_="button")}</form><p>Already registered? <a href="/auth/login">Sign in</a></p></section>'
    return page("Create account",body)
@bp.route("/auth/login",methods=["GET","POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for("main.dashboard"))
    form=LoginForm()
    if form.validate_on_submit():
        user=User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.is_active and user.check_password(form.password.data):
            login_user(user)
            nxt=request.args.get("next","")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("main.dashboard"))
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
    body='<section class="panel"><h1>Welcome, '+current_user.full_name+'</h1><p>Manage your business applications and track their review status.</p><a class="button" href="/applications/new">New business application</a></section><section class="panel"><h2>Your applications</h2>'
    if not items: body+='<p>No applications yet. Submit your first business application to get started.</p>'
    for x in items: body+=f'<article><h3>{x.business_name}</h3><p>{x.business_type} · {x.county} County</p><span class="status {x.status}">{x.status.title()}</span><p>{x.review_notes}</p></article><hr>'
    return page("Dashboard",body+'</section>')
@bp.route("/applications/new",methods=["GET","POST"])
@login_required
def new_application():
    form=ApplicationForm()
    if form.validate_on_submit():
        item=BusinessApplication(owner_id=current_user.id,business_name=form.business_name.data.strip(),business_type=form.business_type.data.strip(),county=form.county.data,description=(form.description.data or "").strip())
        db.session.add(item); db.session.commit(); flash("Application submitted for review.","success"); return redirect(url_for("main.dashboard"))
    body=f'<section class="panel"><h1>Business application</h1><p>Provide accurate information. An administrator will review your submission.</p><form method="post">{form.hidden_tag()}{field(form,"business_name",class_="input")}{field(form,"business_type",class_="input")}{field(form,"county",class_="input")}{field(form,"description",class_="input",rows=4)}{form.submit(class_="button")}</form></section>'
    return page("New application",body)
@bp.get("/directory")
def directory():
    items=BusinessApplication.query.filter_by(status="approved").order_by(BusinessApplication.business_name.asc()).all()
    body='<section class="panel"><h1>Liberian business directory</h1><p>Only applications approved by administrators appear here.</p>'
    if not items: body+='<p>No approved businesses have been published yet.</p>'
    for x in items: body+=f'<article><h2>{x.business_name}</h2><p>{x.business_type} · {x.county} County</p><p>{x.description}</p><span class="status approved">Approved</span></article><hr>'
    return page("Business directory",body+'</section>')
@bp.get("/admin/applications")
@login_required
def admin_applications():
    if not current_user.is_admin: abort(403)
    items=BusinessApplication.query.order_by(BusinessApplication.created_at.asc()).all()
    body='<section class="panel"><h1>Applications for review</h1>'
    if not items: body+='<p>No applications to review.</p>'
    for x in items: body+=f'<article><h2>{x.business_name}</h2><p>{x.business_type} · {x.county} County</p><p>Applicant: {x.owner.email}</p><span class="status {x.status}">{x.status.title()}</span> <a href="/admin/applications/{x.id}/review">Review</a></article><hr>'
    return page("Admin review",body+'</section>')
@bp.route("/admin/applications/<int:application_id>/review",methods=["GET","POST"])
@login_required
def review(application_id):
    if not current_user.is_admin: abort(403)
    item=db.get_or_404(BusinessApplication,application_id); form=ReviewForm(status=item.status if item.status in {"approved","rejected"} else "approved",review_notes=item.review_notes)
    if form.validate_on_submit():
        item.status=form.status.data; item.review_notes=(form.review_notes.data or "").strip(); db.session.commit(); flash("Application review saved.","success"); return redirect(url_for("main.admin_applications"))
    body=f'<section class="panel"><h1>Review {item.business_name}</h1><p>{item.business_type} · {item.county} County</p><p>{item.description}</p><form method="post">{form.hidden_tag()}{field(form,"status",class_="input")}{field(form,"review_notes",class_="input")}{form.submit(class_="button")}</form></section>'
    return page("Review application",body)
