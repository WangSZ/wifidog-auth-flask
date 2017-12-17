"""
Views for the app
"""

from __future__ import absolute_import
from __future__ import division

import datetime
import os

from auth import constants

from auth.forms import \
    CashupForm, \
    CategoryForm, \
    CountryForm, \
    CurrencyForm, \
    GatewayForm, \
    LoginVoucherForm, \
    MyUserForm, \
    NetworkForm, \
    NewVoucherForm, \
    OrderForm, \
    ProductForm, \
    SelectCategoryForm, \
    SelectNetworkGatewayForm, \
    UserForm

from auth.models import \
    Cashup, \
    Category, \
    Gateway, \
    Network, \
    Order, \
    OrderItem, \
    Product, \
    Transaction, \
    User, \
    Voucher, \
    db

from auth.resources import resource_instance, resource_instances, RESOURCE_MODELS
from auth.services import \
        environment_dump, \
        healthcheck as healthcheck_service, \
        logos
from auth.utils import generate_uuid, has_role, is_logged_in
from auth.vouchers import process_auth

from decimal import Decimal
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
from flask_security import \
    auth_token_required, \
    current_user, \
    login_required, \
    roles_accepted
from PIL import Image
from pytz import common_timezones
from sqlalchemy import func
from wtforms import fields as f, validators


bp = Blueprint('auth', __name__)


def redirect_url():
    return request.args.get('next') or \
        session.get('next_url') or \
        request.referrer or \
        url_for('.home')


def resource_index(resource, form=None):
    """Handle a resource index request"""
    pagination = resource_instances(resource).paginate()
    return render_template('%s/index.html' % resource,
                           form=form,
                           pagination=pagination,
                           resource=resource)


def resource_new(resource, form):
    """Handle a new resource request"""
    if form.validate_on_submit():
        instance = RESOURCE_MODELS[resource]()
        form.populate_obj(instance)
        db.session.add(instance)
        db.session.commit()
        flash('Create %s successful' % instance)
        return redirect(url_for('.%s_index' % resource))
    return render_template('%s/new.html' % resource, form=form, resource=resource)


def resource_edit(resource, id, form_class):
    """Handle a resource edit request"""
    instance = resource_instance(resource, id)
    form = form_class(obj=instance)
    if form.validate_on_submit():
        form.populate_obj(instance)
        db.session.commit()
        flash('Update %s successful' % instance)
        return redirect(url_for('.%s_index' % resource))
    return render_template('%s/edit.html' % resource,
                           form=form,
                           instance=instance,
                           resource=resource)


def resource_show(resource, id):
    """Handle a resource show request"""
    instance = resource_instance(resource, id)
    return render_template('%s/show.html' % resource,
                           instance=instance,
                           resource=resource)


def resource_delete(resource, id):
    """Handle a resource delete request"""
    instance = resource_instance(resource, id)
    if request.method == 'POST':
        instance_label = str(instance)
        db.session.delete(instance)
        db.session.commit()
        flash('Delete %s successful' % instance_label)
        return redirect(url_for('.%s_index' % resource))
    return render_template('shared/delete.html',
                           instance=instance,
                           resource=resource)


def resource_action(resource, id, action, param_name='id'):
    """Handle a resource action request"""
    instance = resource_instance(resource, id, param_name)
    if request.method == 'POST':
        if action in constants.ACTIONS[resource]:
            getattr(instance, action)()
            db.session.commit()
            flash('%s %s successful' % (instance, action))
            return redirect(url_for('.%s_index' % resource))
        else:
            abort(404)
    action_url = url_for('.%s_action' % resource, **{'action': action, param_name: getattr(instance, param_name)})
    return render_template('shared/action.html',
                           action=action,
                           action_url=action_url,
                           instance=instance,
                           resource=resource)


def set_locale_choices(form):
    form.locale.choices = [(id, title) for id, title in constants.LOCALES.items()]
    form.timezone.choices = [(timezone, timezone) for timezone in common_timezones]


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
    return render_template('network/current.html',
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
    return _gateway_edit(
        gateway,
        'My Gateway',
        url_for('.my_gateway')
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
    set_locale_choices(form)

    if form.validate_on_submit():
        if form.password.data == '':
            del form.password
        form.populate_obj(current_user)
        db.session.commit()
        flash('Update successful')
        return redirect('/')
    return render_template('user/current.html',
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
def network_index():
    return resource_index('network')


@bp.route('/networks/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin')
def network_new():
    form = NetworkForm()
    return resource_new('network', form)


@bp.route('/networks/<id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin')
def network_edit(id):
    return resource_edit('network', id, NetworkForm)


@bp.route('/networks/<id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin')
def network_delete(id):
    return resource_delete('network', id)


@bp.route('/gateways')
@login_required
@roles_accepted('super-admin', 'network-admin')
@register_menu(
    bp,
    '.gateways',
    'Gateways',
    visible_when=has_role('super-admin', 'network-admin'),
    order=20)
def gateway_index():
    return resource_index('gateway')


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
def gateway_new():
    form = GatewayForm()
    if form.validate_on_submit():
        handle_logo(form)
        gateway = Gateway()
        form.populate_obj(gateway)
        db.session.add(gateway)
        db.session.commit()
        flash('Create %s successful' % gateway)
        return redirect(url_for('.gateway_index'))
    return render_template('gateway/new.html', form=form)


def _gateway_edit(gateway, page_title, action_url):
    form = GatewayForm(obj=gateway)
    if form.validate_on_submit():
        handle_logo(form)
        form.populate_obj(gateway)
        db.session.commit()
        flash('Update %s successful' % gateway)
        return redirect(url_for('.home'))
    return render_template('gateway/edit.html',
                           action_url=action_url,
                           form=form,
                           instance=gateway,
                           logos=logos,
                           page_title=page_title)


@bp.route('/gateways/<id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin')
def gateway_edit(id):
    gateway = Gateway.query.filter_by(id=id).first_or_404()
    return _gateway_edit(
        gateway,
        'Edit Gateway',
        url_for('.gateway_edit', id=id)
    )


@bp.route('/gateways/<id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin')
def gateway_delete(id):
    return resource_delete('gateway', id)


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
def user_index():
    form = UserForm()
    return resource_index('user', form=form)


@bp.route('/users/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def user_new():
    form = UserForm()
    set_locale_choices(form)

    if current_user.has_role('gateway-admin'):
        del form.roles

    if form.validate_on_submit():
        user = User()
        form.populate_obj(user)
        db.session.add(user)
        db.session.commit()
        flash('Create %s successful' % user)
        return redirect(url_for('.user_index'))

    return render_template('user/new.html', form=form)


@bp.route('/users/<int:id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def user_edit(id):
    instance = resource_instance('user', id)

    if (current_user.has_role('network-admin')
            and instance.network != current_user.network):
        abort(403)

    if (current_user.has_role('gateway-admin')
            and (instance.network != current_user.network
                 or instance.gateway != current_user.gateway)):
        abort(403)

    form = UserForm(obj=instance)
    set_locale_choices(form)

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
        return redirect(url_for('.user_index'))

    return render_template('user/edit.html', form=form, instance=instance)


@bp.route('/users/<int:id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def user_delete(id):
    return resource_delete('user', id)


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
def voucher_index():
    return resource_index('voucher')


@bp.route('/vouchers/<int:id>/<action>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def voucher_action(id, action):
    return resource_action('voucher', id, action)


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
def category_index():
    return resource_index('category')


@bp.route('/categories/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def category_new():
    form = CategoryForm()
    return resource_new('category', form)


@bp.route('/categories/<int:id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def category_delete(id):
    return resource_delete('category', id)


@bp.route('/categories/<int:id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def category_edit(id):
    category = resource_instance('category', id)
    if category.read_only:
        return redirect(redirect_url())
    return resource_edit('category', id, CategoryForm)


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
def product_index():
    return resource_index('product')


@bp.route('/products/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def product_new():
    select_network_gateway_form = SelectNetworkGatewayForm()

    if request.method == 'GET':
        return render_template('shared/select-network-gateway.html',
                               action_url=url_for('.product_new'),
                               form=select_network_gateway_form)
    else:
        category = request.form.get('category')

        if category is None:
            class Form(SelectCategoryForm):
                pass

            network = select_network_gateway_form.network.data
            gateway = select_network_gateway_form.gateway.data

            Form.network = f.HiddenField()
            Form.gateway = f.HiddenField()

            choices = Category.query.filter(Category.network == None, Category.gateway == None).all()

            if network:
                choices += Category.query.filter(Category.network == network,
                                                Category.gateway == None).all()

            if network and gateway:
                choices += Category.query.filter(Category.network == network,
                                                Category.gateway == gateway).all()

            select_category_form = Form(data={'network': network, 'gateway': gateway})
            select_category_form.category.choices = [(c.code, c.title) for c in choices]

            return render_template('shared/select-category.html',
                                action_url=url_for('.product_new'),
                                form=select_category_form,
                                gateway=gateway,
                                network=network)
        else:
            data = {
                'category': Category.query.filter_by(code=request.form['category']).first(),
                'network': Network.query.get(request.form['network']) if request.form['network'] else None,
                'gateway': Gateway.query.get(request.form['gateway']) if request.form['gateway'] else None,
            }

            class Form(ProductForm):
                pass

            for name in data['category'].properties.split('\n'):
                setattr(Form, name, f.StringField(name[0].upper() +  name[1:]))

            product_form = Form(data=data)
            return render_template('product/new.html', form=product_form, **data)


@bp.route('/products/<int:id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def product_delete(id):
    return resource_delete('product', id)


@bp.route('/products/<int:id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def product_edit(id):
    product = resource_instance('product', id)

    class Form(ProductForm):
        pass

    names = product.category.properties
    names = names.split('\n') if names else []

    if product.properties:
        lines = product.properties.split('\n')
        for line in lines:
            (k, v) = line.split('=')
            setattr(product, k, v)

    for name in names:
        setattr(Form,
                name,
                f.StringField(name[0].upper() + name[1:],
                                   validators=[
                                       validators.InputRequired(),
                                   ],
                                   _name=name))

    form = Form(obj=product)

    if form.validate_on_submit():
        form.populate_obj(product)
        if names:
            values = {}
            for name in names:
                values[name] = getattr(form, name).data
            product.properties = '\n'.join('%s=%s' % (k, v) for k, v in values.items())

        db.session.commit()
        flash('Update %s successful' % product)
        return redirect(url_for('.product_index'))

    return render_template('product/edit.html',
                           category=product.category,
                           form=form,
                           instance=product,
                           resource='product')


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
def country_index():
    return resource_index('country')


@bp.route('/countries/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin')
def country_new():
    form = CountryForm()
    return resource_new('country', form)


@bp.route('/countries/<id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin')
def country_delete(id):
    return resource_delete('country', id)


@bp.route('/countries/<id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin')
def country_edit(id):
    return resource_edit('country', id, CountryForm)


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
def currency_index():
    return resource_index('currency')


@bp.route('/currencies/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def currency_new():
    form = CurrencyForm()
    return resource_new('currency', form)


@bp.route('/currencies/<id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def currency_delete(id):
    return resource_delete('currency', id)


@bp.route('/currencies/<id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def currency_edit(id):
    return resource_edit('currency', id, CurrencyForm)


@bp.route('/orders')
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
@register_menu(
    bp,
    '.orders',
    'Orders',
    visible_when=has_role('super-admin', 'network-admin', 'gateway-admin'),
    order=2
)
def order_index():
    return resource_index('order')


def _gateway_choices():
    choices = []

    if current_user.has_role('gateway-admin'):
        choices = [
            [
                current_user.gateway_id,
                '%s - %s' % (current_user.gateway.network.title,
                             current_user.gateway.title)
            ]
        ]
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

    return choices


@bp.route('/new-order', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
@register_menu(
    bp,
    '.new-order',
    'New Order',
    visible_when=has_role('super-admin', 'network-admin', 'gateway-admin'),
    order=0
)
def order_new():
    order_form = OrderForm()

    show_gateway = current_user.has_role('super-admin') or current_user.has_role('network-admin')

    if show_gateway:
        choices = _gateway_choices()

        if choices == []:
            flash('Define a network and gateway first.')
            return redirect(redirect_url())

        order_form.gateway.choices = choices
        gateway = Gateway.query.get(order_form.gateway.data)
    else:
        del order_form.gateway
        gateway = current_user.gateway

    if order_form.validate_on_submit():
        order = Order()
        order.gateway_id = gateway.id
        order.network_id = gateway.network_id
        order.currency_id = gateway.network.currency_id
        order.user_id = current_user.id

        order_item = OrderItem()
        order_item.order = order
        order_item.product_id = order_form.product.data.id
        order_item.price = Decimal(order_form.price.data)
        order_item.quantity = order_form.quantity.data

        _recalculate_total(order)

        db.session.add(order)
        db.session.add(order_item)
        db.session.commit()

        flash('Create %s successful' % order)
        return redirect(url_for('.order_edit', hash=order.hash))

    # TODO This should be a union of global products,
    # then network then gateway
    products = Product.query

    if products.count() == 0:
        abort(404, 'Create a product.')

    prices = dict((p.id, p.price) for p in products)
    price = '%.2f' % (list(prices.values())[0])

    return render_template('order/new.html',
                           order_form=order_form,
                           price=price,
                           prices=prices)


def _recalculate_total(order):
    order.total_amount = 0
    for item in order.items:
        order.total_amount += item.price * item.quantity


@bp.route('/orders/<hash>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def order_edit(hash):
    order = resource_instance('order', hash, 'hash')

    if order.status == 'new':
        order_form = OrderForm(obj=order)

        show_gateway = current_user.has_role('super-admin') or current_user.has_role('network-admin')

        if show_gateway:
            choices = _gateway_choices()

            if choices == []:
                flash('Define a network and gateway first.')
                return redirect(redirect_url())

            order_form.gateway.choices = choices
            gateway = Gateway.query.get(order_form.gateway.data)
        else:
            del order_form.gateway
            gateway = current_user.gateway

        if order_form.validate_on_submit():
            order_item = OrderItem()
            order_item.order = order
            order_item.product_id = order_form.product.data.id
            order_item.price = Decimal(order_form.price.data)
            order_item.quantity = order_form.quantity.data

            order.gateway = gateway
            order.network = gateway.network

            _recalculate_total(order)

            db.session.add(order_item)
            db.session.commit()

            flash('Create %s successful' % order)
            return redirect(url_for('.order_edit', hash=order.hash))

        prices = dict((p.id, p.price) for p in Product.query.all())
        price = '%.2f' % (list(prices.values())[0])

        return render_template('order/edit.html',
                               order_form=order_form,
                               order=order,
                               price=price,
                               prices=prices)

    return render_template('order/show.html', order=order)



@bp.route('/orders/<id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def order_delete(id):
    return resource_delete('order', id)


@bp.route('/orders/<hash>/<int:item_id>', methods=['POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def order_item_edit(hash, item_id):
    order = Order.query.filter_by(hash=hash).first_or_404()
    order_item = OrderItem.query.filter_by(id=item_id).first_or_404()
    order_item_label = str(order_item)

    action = request.form.get('action')

    if action == 'remove':
        db.session.delete(order_item)
    else:
        order_item.product = Product.query.get(request.form.get('product'))
        order_item.quantity = int(request.form.get('quantity'))
        order_item.price = Decimal(request.form.get('price'))

    _recalculate_total(order)
    db.session.commit()

    flash('%s %s successful' % (action[0].upper() + action[1:], order_item_label))
    return redirect(url_for('.order_edit', hash=hash))


@bp.route('/orders/<hash>/pay/<processor_id>', methods=['GET', 'POST'])
def order_pay(hash, processor_id):
    order = resource_instance('order', hash, 'hash')
    processor = resource_instance('processor', processor_id)
    return processor.pay_order(order)


@bp.route('/orders/<hash>/<action>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def order_action(hash, action):
    return resource_action('order', hash, action, 'hash')


@bp.route('/cashups')
@login_required
@roles_accepted('super-admin')
@register_menu(
    bp,
    '.cashups',
    'Cashups',
    visible_when=has_role('super-admin'),
    order=99
)
def cashup_index():
    return resource_index('cashup')


@bp.route('/cashups/new', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def cashup_new():
    if Transaction.query.filter(Transaction.cashup == None).count() == 0:
        flash('No new transactions since last cashup', 'warning')
        return redirect(redirect_url())

    form = CashupForm(data={'user': current_user})
    if form.validate_on_submit():
        cashup = Cashup()
        cashup.user = current_user
        form.populate_obj(cashup)
        db.session.add(cashup)
        db.session.commit()

        for transaction in db.session.query(Transaction) \
                             .filter(Transaction.created_at < cashup.created_at, Transaction.cashup == None):
            cashup.transactions.append(transaction)
        db.session.commit()

        flash('Create %s successful' % cashup)
        return redirect(url_for('.cashup_index'))
    return render_template('cashup/new.html', form=form)


@bp.route('/cashups/<id>/delete', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def cashup_delete(id):
    return resource_delete('cashup', id)


@bp.route('/cashups/<id>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def cashup_show(id):
    return resource_show('cashup', id)


@bp.route('/transactions')
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
@register_menu(
    bp,
    '.transactions',
    'Transactions',
    visible_when=has_role('super-admin', 'network-admin', 'gateway-admin'),
    order=3
)
def transaction_index():
    return resource_index('transaction')


@bp.route('/transactions/<hash>')
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def transaction_show(hash):
    transaction = Transaction.query.filter_by(hash=hash).first_or_404()
    return render_template('transaction/show.html', transaction=transaction)


@bp.route('/transactions/<hash>/<action>', methods=['GET', 'POST'])
@login_required
@roles_accepted('super-admin', 'network-admin', 'gateway-admin')
def transaction_action(hash, action):
    return resource_action('transaction', slug, action, 'hash')


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
def voucher_new():
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
        return redirect(redirect_url())

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

        return redirect(url_for('.voucher_new', code=voucher.code))

    return render_template('voucher/new.html', form=form, defaults=defaults)


@bp.route('/wifidog/login/', methods=['GET', 'POST'])
def wifidog_login():
    form = LoginVoucherForm(request.form)

    if form.validate_on_submit():
        voucher_code = form.voucher_code.data.upper()
        voucher = Voucher.query.filter(func.upper(Voucher.code) == voucher_code).first()

        if voucher is None:
            flash(
                'Voucher not found, did you type the code correctly?',
                'error'
            )

            return redirect(redirect_url())

        form.populate_obj(voucher)
        voucher.token = generate_uuid()
        db.session.commit()

        session['next_url'] = form.url.data
        session['voucher_token'] = voucher.token

        url = ('http://%s:%s/wifidog/auth?token=%s' %
               (voucher.gw_address,
                voucher.gw_port,
                voucher.token))

        return redirect(url)

    if request.method == 'GET':
        gw_id = request.args.get('gw_id')
    else:
        gw_id = form.gw_id.data

    if gw_id is None:
        abort(404)

    gateway = Gateway.query.filter_by(id=gw_id).first_or_404()

    return render_template('wifidog/login.html', form=form, gateway=gateway)


@bp.route('/wifidog/ping/')
def wifidog_ping():
    gateway = Gateway.query.filter_by(id=request.args.get('gw_id')).first_or_404()

    gateway.last_ping_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    gateway.last_ping_at = datetime.datetime.utcnow()
    gateway.last_ping_user_agent = request.user_agent.string
    gateway.last_ping_sys_uptime = request.args.get('sys_uptime')
    gateway.last_ping_wifidog_uptime = request.args.get('wifidog_uptime')
    gateway.last_ping_sys_memfree = request.args.get('sys_memfree')
    gateway.last_ping_sys_load = request.args.get('sys_load')

    db.session.commit()

    return ('Pong', 200)


@bp.route('/wifidog/auth/')
def wifidog_auth():
    args = dict(
        user_agent=request.user_agent.string,
        stage=request.args.get('stage'),
        ip=request.args.get('ip'),
        mac=request.args.get('mac'),
        token=request.args.get('token'),
        incoming=int(request.args.get('incoming')),
        outgoing=int(request.args.get('outgoing')),
        gateway_id=request.args.get('gw_id'),
    )
    (status, messages) = process_auth(args)
    return "Auth: %s\nMessages: %s\n" % (status, messages), 200


@bp.route('/wifidog/portal/')
def wifidog_portal():
    voucher_token = session.get('voucher_token')
    if voucher_token:
        voucher = Voucher.query.filter_by(token=voucher_token).first()
    else:
        voucher = None
    gw_id = request.args.get('gw_id')
    if gw_id is None:
        abort(404)
    gateway = Gateway.query.filter_by(id=gw_id).first_or_404()
    logo_url = None
    if gateway.logo:
        logo_url = logos.url(gateway.logo)
    next_url = session.pop('next_url', None)
    return render_template('wifidog/portal.html',
                           gateway=gateway,
                           logo_url=logo_url,
                           next_url=next_url,
                           voucher=voucher)


@bp.route('/favicon.ico')
def favicon():
    directory = os.path.join(current_app.root_path, 'static')
    return send_from_directory(directory,
                               'favicon.ico',
                               mimetype='image/vnd.microsoft.icon')


@bp.route('/uploads/<path:path>')
def uploads(path):
    directory = os.path.join(current_app.instance_path, 'uploads')
    return send_from_directory(directory, path)


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


@bp.route('/raise-exception')
@login_required
def raise_exception():
    abort(int(request.args.get('status', 500)))


@bp.route('/')
def home():
    return redirect(url_for('security.login'))
