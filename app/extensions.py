from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message_category = "warning"
login_manager.session_protection = "strong"
limiter = Limiter(key_func=get_remote_address, default_limits=["300 per day", "100 per hour"])
