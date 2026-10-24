from datetime import datetime,timezone
from flask_login import UserMixin
from werkzeug.security import check_password_hash,generate_password_hash
from .extensions import db,login_manager
def utcnow(): return datetime.now(timezone.utc)
class User(UserMixin,db.Model):
    __table_args__ = (db.CheckConstraint("role IN ('admin', 'business_owner')", name="ck_user_role_allowed"),)
    id=db.Column(db.Integer,primary_key=True)
    email=db.Column(db.String(254),unique=True,nullable=False,index=True)
    full_name=db.Column(db.String(120),nullable=False)
    password_hash=db.Column(db.String(256),nullable=False)
    role=db.Column(db.String(30),nullable=False,default="business_owner")
    is_active=db.Column(db.Boolean,nullable=False,default=True)
    created_at=db.Column(db.DateTime(timezone=True),nullable=False,default=utcnow)
    applications=db.relationship("BusinessApplication",back_populates="owner",lazy=True)
    def set_password(self,password): self.password_hash=generate_password_hash(password)
    def check_password(self,password): return check_password_hash(self.password_hash,password)
    @property
    def is_admin(self): return self.role=="admin"
class BusinessApplication(db.Model):
    __table_args__ = (db.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_business_application_status_allowed"),)
    id=db.Column(db.Integer,primary_key=True)
    owner_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False,index=True)
    business_name=db.Column(db.String(180),nullable=False)
    business_type=db.Column(db.String(100),nullable=False)
    county=db.Column(db.String(100),nullable=False)
    description=db.Column(db.Text,nullable=False,default="")
    status=db.Column(db.String(30),nullable=False,default="pending",index=True)
    review_notes=db.Column(db.Text,nullable=False,default="")
    created_at=db.Column(db.DateTime(timezone=True),nullable=False,default=utcnow)
    updated_at=db.Column(db.DateTime(timezone=True),nullable=False,default=utcnow,onupdate=utcnow)
    owner=db.relationship("User",back_populates="applications")
@login_manager.user_loader
def load_user(user_id):
    try: return db.session.get(User,int(user_id))
    except (TypeError,ValueError): return None
