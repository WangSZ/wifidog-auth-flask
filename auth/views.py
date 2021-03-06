"""
Views for the app
"""

from __future__ import absolute_import
from __future__ import division

import os
import uuid

from auth import constants

from auth.forms import \
    CategoryForm, \
    CountryForm, \
    CurrencyForm, \
    GatewayForm, \
    LoginVoucherForm, \
    MyUserForm, \
    NetworkForm, \
    NewVoucherForm, \
    ProductForm, \
    UserForm

from auth.models import Auth, Category, Country, Currency, Gateway, Network, Product, User, Voucher, db
# from auth.payu import get_transaction, set_transaction, capture
from auth.resources import logos
from auth.services import \
        environment_dump, \
        healthcheck as healthcheck_service
from auth.utils import is_logged_in, has_role

from flask import \
    Blueprint, \
    abort, \
    current_app, \
    flash, \
    redirect, \
    request, \
    render_template, \
    send_from_directory, \
    session, \
    url_for
from flask_menu import register_menu
from flask_potion.exceptions import ItemNotFound
from flask_security import \
    auth_token_required, \
    current_user, \
    login_required, \
    roles_accepted
from PIL import Image


bp = Blueprint('auth', __name__)

RESOURCE_MODELS = {
    'categories': Category,
    'countries': Country,
    'currencies': Currency,
    'gateways': Gateway,
    'networks': Network,
    'products': Product,
    'users': User,
    'vouchers': Voucher,
}


def generate_token():
    """Generate token for the voucher session"""
    return uuid.uuid4().hex


def resource_query(resource):
    """Generate a filtered query for a resource"""
    model = RESOURCE_MODELS[resource]
    query = model.query

    if current_user.has_role('network-admin') or current_user.has_role('gateway-admin'):
        if model == Network:
            query = query.filter_by(id=current_user.network_id)
        elif model in [ Gateway, User ]:
            query = query.filter_by(network_id=current_user.network_id)

    if current_user.has_role('network-admin'):
        if model == Voucher:
            query = query.join(Voucher.gateway).join(Gateway.network).filter(Network.id == current_user.network_id)

    if current_user.has_role('gateway-admin'):
        if model == Gateway:
            query = query.filter_by(id=current_user.gateway_id)
        elif model in [ User, Voucher ]:
            query = query.filter_by(gateway_id=current_user.gateway_id)

    return query

def resource_instance(resource, id):
    """Return instances"""
    model = RESOURCE_MODELS[resource]
    return resource_query(resource).filter(model.id == id).first_or_404()


def resource_instances(resource):
    """Return instances"""
    query = resource_query(resource)
    if resource == 'vouchers':
        return (query.filter(Voucher.status != 'archived')
                     .order_by(Voucher.status, Voucher.created_at.desc())
                     .all())
    else:
        return query.all()


def resource_index(resource, form=None):
    """Handle a resource index request"""
    instances = resource_instances(resource)
    return render_template('%s/index.html' % resource,
                           form=form,
                           instances=instances)


def resource_new(resource, form):
    """Handle a new resource request"""
    if form.validate_on_submit():
        instance = RESOURCE_MODELS[resource]()
        form.populate_obj(instance)
        db.session.add(instance)
        db.session.commit()
        flash('Create %s successful' % instance)
        return redirect(url_for('.%s_index' % resource))
    return render_template('%s/new.html' % resource, form=form)


def resource_edit(resource, id, form_class):
    instance = resource_instance(resource, id)
    form = form_class(obj=instance)
    if form.validate_on_submit():
        form.populate_obj(instance)
        db.session.commit()
        flash('Update %s successful' % instance)
        return redirect(url_for('.%s_index' % resource))
    return render_template('%s/edit.html' % resource,
                           form=form,
                           instance=instance)


def resource_delete(resource, id):
    instance = resource_instance(resource, id)
    if request.method == 'POST':
        db.session.delete(instance)
        db.session.commit()
        flash('Delete %s successful' % instance)
        return redirect(url_for('.%s_index' % resource))
    return render_template('shared/delete.html',
                           instance=instance,
                           resource=resource)


def resource_action(resource, id, action):
    instance = resource_instance(resource, id)
    if request.method == 'POST':
        if action in constants.ACTIONS[resource]:
            getattr(instance, action)()
            db.session.commit()
            flash('%s %s successful' % (instance, action))
            return redirect(url_for('.%s_index' % resource))
        else:
            abort(404)
    return render_template('shared/action.html',
                           instance=instance,
                           action=action,
                           resource=resource)


@bp.route('/network', methods=['GET', 'POST'])
@login_required
@roles_accepted('network-admin')
@register_menu(
    bp,
    '.network',
    'My Network',
    visible_when=has_role('network-admin'),
    order=997
)
def my_network():
    form = NetworkForm(obj=current_user.network)
    if form.validate_on_submit():
        form.populate_obj(current_user.network)
        db.session.commit()
        flash('Update successful')
        return redirect('/')
    return render_template('networks/current.html',
                           form=form,
                           instance=current_user.network)


@bp.route('/gateway', methods=['GET', 'POST'])
@login_required
@roles_accepted('gateway-admin')
@register_menu(
    bp,
    '.gateway',
    'My Gateway',
    visible_when=has_role('gateway-admin'),
    order=998
)
def my_gateway():
    gateway = current_user.gateway
    return _gateways_edit(
        gateway,
        'My Gateway',
        url_for('.my_gateway'),
        url_for('.home')
    )


@bp.route('/user', methods=['GET', 'POST'])
@login_required
@register_menu(
    bp,
    '.account',
    'My Account',
    visible_when=is_logged_in,
    order=999
)
def my_account():
    form = MyUserForm(obj=current_user)
    if form.validate_on_submit():
        if form.password.data == '':
            del form.password
        form.populate_obj(current_user)
        db.session.commit()
        flash('Update successful')
        return redirect('/')
    return render_template('users/current.html',
                           form=form,
                           instance=current_user)


@bp.route('/networks')
@login_required
@roles_accepted('super-admin')
@register_menu(
    bp,
    '.networks',
    'Networks',
    visible_when=has_role('super-admin'),
    order=10
)
def networks_index():
    return resource_index('networks')


@bp.route('/networks/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin')
def networks_new():
    form = NetworkForm()
    return resource_new('networks', form)


@bp.route('/networks/<id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin')
def networks_edit(id):
    return resource_edit('networks', id, NetworkForm)


@bp.route('/networks/<id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin')
def networks_delete(id):
    return resource_delete('networks', id)


@bp.route('/gateways')
@login_required
@roles_accepted('super-admin', 'network-admin')
@register_menu(
    bp,
    '.gateways',
    'Gateways',
    visible_when=has_role('super-admin', 'network-admin'),
    order=20)
def gateways_index():
    return resource_index('gateways')

def handle_logo(form):
    if request.files['logo']:
        filename = form.logo.data = logos.save(request.files['logo'], name='%s.' % form.id.data)
        im = Image.open(logos.path(filename))
        im.thumbnail((300, 300), Image.ANTIALIAS)
        im.save(logos.path(filename))
    else:
        del form.logo

@bp.route('/gateways/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin')
def gateways_new():
    form = GatewayForm()
    if form.validate_on_submit():
        handle_logo(form)
        gateway = Gateway()
        form.populate_obj(gateway)
        db.session.add(gateway)
        db.session.commit()
        flash('Create %s successful' % gateway)
        return redirect(url_for('.gateways_index'))
    return render_template('gateways/new.html', form=form)


def _gateways_edit(gateway, page_title, action_url, redirect_url):
    form = GatewayForm(obj=gateway)
    if form.validate_on_submit():
        handle_logo(form)
        form.populate_obj(gateway)
        db.session.commit()
        flash('Update %s successful' % gateway)
        return redirect(redirect_url)
    return render_template('gateways/edit.html',
                           action_url=action_url,
                           form=form,
                           instance=gateway,
                           logos=logos,
                           page_title=page_title)


@bp.route('/gateways/<id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin')
def gateways_edit(id):
    gateway = Gateway.query.filter_by(id=id).first_or_404()
    return _gateways_edit(
        gateway,
        'Edit Gateway',
        url_for('.gateways_edit', id=id),
        url_for('.gateways_index')
    )


@bp.route('/gateways/<id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin')
def gateways_delete(id):
    return resource_delete('gateways', id)


@bp.route('/users')
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
@register_menu(
    bp,
    '.users',
    'Users',
    visible_when=has_role('super-admin', 'network-admin', 'gateway-admin'),
    order=40
)
def users_index():
    form = UserForm()
    return resource_index('users', form=form)


@bp.route('/users/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def users_new():
    form = UserForm()

    if current_user.has_role('gateway-admin'):
        del form.roles

    return resource_new('users', form)


@bp.route('/users/<id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def users_edit(id):
    instance = resource_instance('users', id)

    if (current_user.has_role('network-admin')
            and instance.network != current_user.network):
        abort(403)

    if (current_user.has_role('gateway-admin')
            and (instance.network != current_user.network
                 or instance.gateway != current_user.gateway)):
        abort(403)

    form = UserForm(obj=instance)

    if current_user.has_role('network-admin'):
        del form.gateway

    if current_user == instance:
        del form.active
        del form.roles

    if form.validate_on_submit():
        if form.password.data == '':
            del form.password

        form.populate_obj(instance)
        db.session.commit()

        flash('Update %s successful' % instance)
        return redirect(url_for('.users_index'))
    return render_template('users/edit.html', form=form, instance=instance)


@bp.route('/users/<id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def users_delete(id):
    return resource_delete('users', id)


@bp.route('/vouchers')
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
@register_menu(
    bp,
    '.vouchers',
    'Vouchers',
    visible_when=has_role('super-admin', 'network-admin', 'gateway-admin'),
    order=5
)
def vouchers_index():
    return resource_index('vouchers')


@bp.route('/vouchers/<id>/<action>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def vouchers_action(id, action):
    return resource_action('vouchers', id, action)


@bp.route('/categories')
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
@register_menu(
    bp,
    '.categories',
    'Categories',
    visible_when=has_role('super-admin', 'network-admin', 'gateway-admin'),
    order=99
)
def categories_index():
    return resource_index('categories')


@bp.route('/categories/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def categories_new():
    form = CategoryForm()
    return resource_new('categories', form)


@bp.route('/categories/<id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def categories_delete(id):
    return resource_delete('categories', id)


@bp.route('/categories/<id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def categories_edit(id):
    return resource_edit('categories', id, CategoryForm)


@bp.route('/products')
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
@register_menu(
    bp,
    '.products',
    'Products',
    visible_when=has_role('super-admin', 'network-admin', 'gateway-admin'),
    order=99
)
def products_index():
    return resource_index('products')


@bp.route('/products/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def products_new():
    form = ProductForm()
    return resource_new('products', form)


@bp.route('/products/<id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def products_delete(id):
    return resource_delete('products', id)


@bp.route('/products/<id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def products_edit(id):
    return resource_edit('products', id, ProductForm)


@bp.route('/countries')
@login_required
@roles_accepted('super-admin')
@register_menu(
    bp,
    '.countries',
    'Countries',
    visible_when=has_role('super-admin'),
    order=99
)
def countries_index():
    return resource_index('countries')


@bp.route('/countries/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin')
def countries_new():
    form = CountryForm()
    return resource_new('countries', form)


@bp.route('/countries/<id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin')
def countries_delete(id):
    return resource_delete('countries', id)


@bp.route('/countries/<id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin')
def countries_edit(id):
    return resource_edit('countries', id, CountryForm)


@bp.route('/currencies')
@login_required
@roles_accepted('super-admin')
@register_menu(
    bp,
    '.currencies',
    'Currencies',
    visible_when=has_role('super-admin'),
    order=99
)
def currencies_index():
    return resource_index('currencies')


@bp.route('/currencies/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def currencies_new():
    form = CurrencyForm()
    return resource_new('currencies', form)


@bp.route('/currencies/<id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def currencies_delete(id):
    return resource_delete('currencies', id)


@bp.route('/currencies/<id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def currencies_edit(id):
    return resource_edit('currencies', id, CurrencyForm)


@bp.route('/new-voucher', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
@register_menu(
    bp,
    '.new-voucher',
    'New Voucher',
    visible_when=has_role('super-admin', 'network-admin', 'gateway-admin'),
    order=0
)
def vouchers_new():
    form = NewVoucherForm()
    choices = []
    defaults = {}

    if current_user.has_role('gateway-admin'):
        choices = [
            [
                current_user.gateway_id,
                '%s - %s' % (current_user.gateway.network.title,
                             current_user.gateway.title)
            ]
        ]
        defaults[current_user.gateway_id] = {
            'minutes': current_user.gateway.default_minutes,
            'megabytes': current_user.gateway.default_megabytes,
        }
    else:
        if current_user.has_role('network-admin'):
            networks = [current_user.network]
        else:
            networks = Network.query.all()

        for network in networks:
            for gateway in network.gateways:
                choices.append([
                    gateway.id,
                    '%s - %s' % (network.title,
                                 gateway.title)
                ])
                defaults[gateway.id] = {
                    'minutes': gateway.default_minutes,
                    'megabytes': gateway.default_megabytes,
                }

    if choices == []:
        flash('Define a network and gateway first.')
        return redirect(request.referrer)

    form.gateway_id.choices = choices

    item = defaults[choices[0][0]]

    if request.method == 'GET':
        form.minutes.data = item['minutes']
        form.megabytes.data = item['megabytes']

    if form.validate_on_submit():
        voucher = Voucher()
        form.populate_obj(voucher)
        db.session.add(voucher)
        db.session.commit()

        return redirect(url_for('.vouchers_new', code=voucher.code))

    return render_template('vouchers/new.html', form=form, defaults=defaults)


@bp.route('/wifidog/login/', methods=['GET', 'POST'])
def wifidog_login():
    form = LoginVoucherForm(request.form)

    if form.validate_on_submit():
        voucher_code = form.voucher_code.data.upper()
        voucher = Voucher.query.filter_by(code=voucher_code, status='new').first()

        if voucher is None:
            flash(
                'Voucher not found, did you type the code correctly?',
                'error'
            )

            return redirect(request.referrer)

        form.populate_obj(voucher)
        voucher.token = generate_token()
        db.session.commit()

        session['voucher_token'] = voucher.token

        url = ('http://%s:%s/wifidog/auth?token=%s' %
               (voucher.gw_address,
                voucher.gw_port,
                voucher.token))

        return redirect(url)

    if request.method == 'GET':
        gateway_id = request.args.get('gw_id')
    else:
        gateway_id = form.gateway_id.data

    if gateway_id is None:
        abort(404)

    gateway = Gateway.query.filter_by(id=gateway_id).first_or_404()

    return render_template('wifidog/login.html', form=form, gateway=gateway)


@bp.route('/wifidog/ping/')
def wifidog_ping():
    return ('Pong', 200)


@bp.route('/wifidog/auth/')
def wifidog_auth():
    auth = Auth(
        user_agent=request.user_agent.string,
        stage=request.args.get('stage'),
        ip=request.args.get('ip'),
        mac=request.args.get('mac'),
        token=request.args.get('token'),
        incoming=int(request.args.get('incoming')),
        outgoing=int(request.args.get('outgoing')),
        gateway_id=request.args.get('gw_id')
    )

    (auth.status, auth.messages) = auth.process_request()

    db.session.add(auth)
    db.session.commit()

    def generate_point(measurement):
        return {
            "measurement": 'auth_%s' % measurement,
            "tags": {
                "source": "auth",
                "network_id": auth.gateway.network_id,
                "gateway_id": auth.gateway_id,
                "user_agent": auth.user_agent,
                "stage": auth.stage,
                "ip": auth.ip,
                "mac": auth.mac,
                "token": auth.token,
            },
            "time": auth.created_at,
            "fields": {
                "value": getattr(auth, measurement),
            }
        }

    # points = [generate_point(m) for m in [ 'incoming', 'outgoing' ]]
    # influx_db.connection.write_points(points)

    return ("Auth: %s\nMessages: %s\n" % (auth.status, auth.messages), 200)


@bp.route('/wifidog/portal/')
def wifidog_portal():
    voucher_token = session.get('voucher_token')
    if voucher_token:
        voucher = Voucher.query.filter_by(token=voucher_token).first()
    else:
        voucher = None
    gateway_id = request.args.get('gw_id')
    if gateway_id is None:
        abort(404)
    gateway = Gateway.query.filter_by(id=gateway_id).first_or_404()
    logo_url = None
    if gateway.logo:
        logo_url = logos.url(gateway.logo)
    return render_template('wifidog/portal.html',
                           gateway=gateway,
                           logo_url=logo_url,
                           voucher=voucher)


@bp.route('/pay')
def pay():
    return_url = url_for('.pay_return', _external=True)
    cancel_url = url_for('.pay_cancel', _external=True)
    response = set_transaction('ZAR',
                               1000,
                               'Something',
                               return_url,
                               cancel_url)
    return redirect('%s?PayUReference=%s' % (capture, response.payUReference))


@bp.route('/pay/return')
def pay_return():
    response = get_transaction(request.args.get('PayUReference'))
    basketAmount = '{:.2f}'.format(int(response.basket.amountInCents) / 100)
    category = 'success' if response.successful else 'error'
    flash(response.displayMessage, category)
    return render_template('payu/transaction.html',
                           response=response,
                           basketAmount=basketAmount)


@bp.route('/pay/cancel')
def pay_cancel():
    response = get_transaction(request.args.get('payUReference'))
    basketAmount = '{:.2f}'.format(int(response.basket.amountInCents) / 100)
    flash(response.displayMessage, 'warning')
    return render_template('payu/transaction.html',
                           response=response,
                           basketAmount=basketAmount)


@bp.route('/favicon.ico')
def favicon():
    directory = os.path.join(current_app.root_path, 'static')
    return send_from_directory(directory,
                               'favicon.ico',
                               mimetype='image/vnd.microsoft.icon')


@bp.route('/auth-token')
@login_required
def auth_token():
    return current_user.get_auth_token()


@bp.route('/healthcheck')
@auth_token_required
def healthcheck():
    return healthcheck_service.check()


@bp.route('/environment')
@auth_token_required
def environment():
    return environment_dump.dump_environment()


@bp.route('/')
def home():
    return redirect(url_for('security.login'))
