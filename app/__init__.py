import os
from flask import Flask, jsonify, render_template_string
from flask_wtf.csrf import CSRFProtect
from .config import config_by_name
from .extensions import db, limiter, login_manager, migrate

csrf = CSRFProtect()
PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }} | Liberia Business OS</title><style>
:root{font-family:system-ui,sans-serif;color:#182638;background:#f5f8fb;--green:#167354;--navy:#102b46}*{box-sizing:border-box}body{margin:0}header{padding:20px 6%;background:white;border-bottom:1px solid #e1e7ee;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}header a{margin-right:15px;color:#24384c;text-decoration:none}.brand{font-weight:900;color:var(--navy);font-size:1.2rem}main{max-width:1000px;margin:50px auto;padding:0 20px}.panel{background:white;border:1px solid #e1e7ee;border-radius:18px;padding:30px;margin:18px 0;box-shadow:0 8px 28px #102b4608}h1{color:var(--navy);font-size:clamp(2rem,5vw,3.7rem);line-height:1.1;letter-spacing:-.04em}.green{color:var(--green)}p{line-height:1.7;color:#667085}.button,button{display:inline-block;background:var(--green);color:white;border:0;border-radius:9px;padding:12px 16px;text-decoration:none;font-weight:750;cursor:pointer}input,select,textarea{width:100%;padding:12px;border:1px solid #cbd5df;border-radius:8px;font:inherit;margin:6px 0 16px}label{font-weight:650}.flash{padding:12px;border-radius:8px;background:#e4f4ed;margin:10px 0}.muted{color:#667085}.status{font-weight:800;padding:5px 10px;background:#edf1f5;border-radius:20px}.status.approved{background:#dcfae6;color:#05603a}.status.pending{background:#fff1cc;color:#854d0e}.status.rejected{background:#fee4e2;color:#912018}footer{text-align:center;padding:25px;color:#667085}li{padding:10px 0;border-bottom:1px solid #edf0f4}</style></head><body><header><a class="brand" href="/">Liberia <span class="green">Business OS</span></a><nav><a href="/directory">Directory</a>{% if current_user.is_authenticated %}<a href="/dashboard">Dashboard</a>{% if current_user.is_admin %}<a href="/admin/applications">Admin review</a>{% endif %}<form style="display:inline" method="post" action="/auth/logout"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><button>Sign out</button></form>{% else %}<a href="/auth/login">Sign in</a><a href="/auth/register">Create account</a>{% endif %}</nav></header><main>{% for category,message in get_flashed_messages(with_categories=true) %}<div class="flash">{{ message }}</div>{% endfor %}{{ body|safe }}</main><footer>Built for Liberian businesses · Liberia Business OS</footer></body></html>"""

def create_app(config_name=None, test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    config_name = config_name or os.getenv("FLASK_CONFIG", "development")
    config_class = config_by_name.get(config_name, config_by_name["development"])
    app.config.from_object(config_class)
    if test_config:
        app.config.update(test_config)

    # Fail closed in production rather than silently running with a weak secret
    # or a local SQLite file that may disappear across deploys/instances.
    if config_name == "production":
        if not app.config.get("SECRET_KEY"):
            raise RuntimeError("SECRET_KEY must be configured in production.")
        database_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if not database_uri.startswith(("postgresql://", "postgresql+psycopg://")):
            raise RuntimeError("Production requires a PostgreSQL DATABASE_URL.")

    if not app.config.get("MAX_CONTENT_LENGTH"):
        app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    app.config["SESSION_PROTECTION"] = "strong"
    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.storage_uri = app.config.get("RATELIMIT_STORAGE_URI", "memory://")
    limiter.init_app(app)
    csrf.init_app(app)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return response

    from . import models
    from .routes import bp
    app.register_blueprint(bp)

    @app.get("/")
    def index():
        body = """<section class="panel"><p class="green"><b>BUSINESS REGISTRATION · DIGITAL TRANSFORMATION</b></p><h1>A stronger digital foundation for <span class="green">Liberian businesses.</span></h1><p>Start a business application, track its review, and help customers discover approved businesses in one place.</p><a class="button" href="/auth/register">Create an account</a> <a class="button" style="background:#102b46" href="/directory">Explore directory</a></section><section class="panel"><h2>Apply online. Track progress. Get discovered.</h2><p>Submit your business details, track review status, and appear in the public directory after approval.</p></section>"""
        return render_template_string(PAGE, title="Register, manage and discover", body=body)

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="Liberia Business OS"), 200

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template_string(PAGE, title="Access denied", body="<section class='panel'><h1>Access denied</h1><p>You do not have permission to view this page.</p></section>"), 403

    @app.errorhandler(404)
    def missing(_e):
        return render_template_string(PAGE, title="Not found", body="<section class='panel'><h1>Page not found</h1></section>"), 404

    @app.cli.command("create-admin")
    def create_admin():
        import getpass
        from .models import User
        email = input("Administrator email: ").strip().lower()
        if User.query.filter_by(email=email).first():
            print("That email already exists.")
            return
        password = getpass.getpass("Administrator password (12+ characters): ")
        if len(password) < 12:
            print("Password must be at least 12 characters.")
            return
        user = User(email=email, full_name="Platform Administrator", role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print("Administrator created.")

    return app
