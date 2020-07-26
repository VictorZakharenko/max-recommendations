# models.py
from werkzeug.security import generate_password_hash, check_password_hash
from flask_security import UserMixin, RoleMixin
from app import db, login
import jwt
from time import time
from hashlib import md5
from flask import current_app

roles_users = db.Table('roles_users', \
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),\
    db.Column('role_id', db.Integer(), db.ForeignKey('role.id'))
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100),index=True, unique=True)
    password_hash = db.Column(db.String(100))
    name = db.Column(db.String(1000), index=True)
    active = db.Column(db.Boolean())
    integrations = db.relationship('Integration', backref='user', lazy='dynamic')
    roles = db.relationship('Role', secondary = roles_users, backref=db.backref('users', lazy='dynamic'))

    def __repr__(self):
        return '<User {}>'.format(self.name)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password_hash):
        return check_password_hash(self.password_hash, password_hash)

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            current_app.config['SECRET_KEY'], algorithm='HS256').decode('utf-8')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, current_app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class Integration(UserMixin,db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    integration_name = db.Column(db.String(100))
    api_key = db.Column(db.String(100))
    user_domain = db.Column(db.String(100))
    metrika_key = db.Column(db.String(100))
    metrika_counter_id = db.Column(db.Integer)
    clickhouse_login = db.Column(db.String(20))
    clickhouse_password = db.Column(db.String(20))
    clickhouse_host = db.Column(db.String(200))
    clickhouse_db = db.Column(db.String(200))

    def delete_myself(self):
        db.session.delete(self)
        db.session.commit()


class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(100), unique=True)
    description = db.Column(db.String(256))
