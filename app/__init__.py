import flask

from app.models import User, Role
from app.resources import GatewayResource, NetworkResource, UserResource, VoucherResource
from app.services import menu, db, manager, login_manager, api, security, principals
from flask.ext.principal import UserNeed, AnonymousIdentity, identity_loaded, RoleNeed
from flask.ext.security import current_user, SQLAlchemyUserDatastore

app = flask.Flask(__name__)
app.config.from_object('config')

import views

menu.init_app(app)
db.init_app(app)

with app.app_context():
    db.create_all()

    api.add_resource(UserResource)
    api.add_resource(VoucherResource)
    api.add_resource(GatewayResource)
    api.add_resource(NetworkResource)

manager.app = app
login_manager.init_app(app)
api.init_app(app)
principals.init_app(app)

datastore = SQLAlchemyUserDatastore(db, User, Role)
security.init_app(app, datastore)

@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    if not isinstance(identity, AnonymousIdentity):
        identity.provides.add(UserNeed(identity.id))

        for role in current_user.roles:
            identity.provides.add(RoleNeed(role.name))

@app.route('/')
def home():
    return flask.redirect(flask.url_for('security.login'))
