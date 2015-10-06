import flask

from app.utils import is_logged_in, has_role
from flask.ext.menu import register_menu
from flask.ext.security import login_required, roles_required

bp = flask.Blueprint('networks', __name__, url_prefix='/networks', template_folder='templates', static_folder='static')

@bp.route('/')
@login_required
@roles_required('super-admin')
@register_menu(bp, '.networks', 'Networks', visible_when=has_role('super-admin'))
def index():
    return flask.render_template('networks/index.html')
