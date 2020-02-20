from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin
from web import app, db, login


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200))
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean)
    results = db.relationship('Result', backref='user', lazy=True)
    courses = db.relationship('Course', secondary='access')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String)
    passed_num = db.Column(db.Integer)
    runtime = db.Column(db.Float)
    success = db.Column(db.Boolean)
    content = db.Column(db.String)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    cases = db.relationship('Case', cascade="all,delete",
                            backref='result', lazy=True)


class Case(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    case_num = db.Column(db.Integer)
    success = db.Column(db.Boolean)
    reason = db.Column(db.String)
    result_id = db.Column(db.Integer, db.ForeignKey(
        'result.id'), nullable=False)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_num = db.Column(db.Integer)
    registration = db.Column(db.String)
    sessions = db.relationship('Session', cascade="all,delete", backref='course', lazy=True)
    users = db.relationship('User', secondary='access')


class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_num = db.Column(db.Float)
    entry_point = db.Column(db.String)
    runtime = db.Column(db.Float)
    blacklist = db.Column(db.String)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    results = db.relationship('Result', cascade="all,delete", backref='session', lazy=True)
    test_code = db.Column(db.String)

    def get_blacklist(self):
        return list(filter(lambda x: x != '', self.blacklist.split(',')))


class Access(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)

    user = db.relationship('User', backref=db.backref("course", cascade="all, delete-orphan"))
    course = db.relationship('Course', backref=db.backref("user", cascade="all, delete-orphan"))


@login.user_loader
def load_user(id):
    return User.query.get(int(id))
