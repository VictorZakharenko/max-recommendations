# main.py

from flask import Blueprint, render_template, redirect, url_for, flash,request
from flask_login import login_required, current_user
from app.models import User
import pandas as pd
from app.main import bp
from app.main.forms import EditIntegration
from app.models import Integration, User
from app import db

@bp.route('/')
@bp.route('/index')
def index():
    return render_template('index.html')

@bp.route('/profile')
@login_required
def profile():
    return render_template('profile.html', name=current_user.name)

@bp.route('/admin')
@login_required
def admin():
    if current_user.email == 'george@mail.ru':
        list_users = []
        users = User.query.all()
        for user in users:
            list_users.append(str('Name: ' + user.name + ' Email: ' + user.email))
        print (list_users)
        pands_users = pd.DataFrame(list_users)
        pands_users.columns = ['Users']
        return render_template('admin.html', tables=[pands_users.to_html(classes='data', index=False)], titles=pands_users.columns.values)
    else:
        return render_template('index.html')

@bp.route('/user_integrations', methods=['GET'])
@login_required
def user_integrations():
    user = User.query.filter_by(id=current_user.id).first()
    integrations = user.integrations.all()

    return render_template('user_integrations.html', integrations=integrations)

@bp.route('/create_integration', methods=['GET','POST'])
@login_required
def create_integration():
    form = EditIntegration()
    if form.validate_on_submit():
        integration = Integration(
        integration_name = form.integration_name.data,
        api_key = form.api_key.data,
        user_domain = form.user_domain.data,
        metrika_key = form.metrika_key.data,
        metrika_counter_id = form.metrika_counter_id.data,
        clickhouse_login = form.clickhouse_login.data,
        clickhouse_password = form.clickhouse_password.data,
        clickhouse_host = form.clickhouse_host.data,
        clickhouse_db = form.clickhouse_db.data,
        user=current_user
        )
        db.session.add(integration)
        db.session.commit()
        flash('You just have add new {} integration '.format(integration.integration_name))

        return redirect(url_for('main.user_integrations'))

    return render_template('create_integration.html', form=form)


@bp.route('/delete_integration', methods=['GET','POST'])
@login_required
def delete_integration():
    pass



@bp.route('/edit_integration/<integration_name>', methods = ['GET','POST'])
@login_required
def edit_integration(integration_name):
    form = EditIntegration()
    integration = Integration.query.filter_by(integration_name=integration_name).first_or_404()
    # TODO: test it :) !!!!!!
    if integration.user!=current_user:
        abort(404)

    if form.validate_on_submit():
        integration.integration_name = form.integration_name.data
        integration.api_key = form.api_key.data
        integration.user_domain = form.user_domain.data
        integration.metrika_key = form.metrika_key.data
        integration.metrika_counter_id = form.metrika_counter_id.data
        integration.clickhouse_login = form.clickhouse_login.data
        integration.clickhouse_password = form.clickhouse_password.data
        integration.clickhouse_host = form.clickhouse_host.data
        integration.clickhouse_db = form.clickhouse_db.data
        db.session.commit()
    elif request.method == 'GET':
        form.integration_name.data = integration.integration_name
        form.api_key.data = integration.api_key
        form.user_domain.data = integration.user_domain
        form.metrika_key.data = integration.metrika_key
        form.metrika_counter_id.data = integration.metrika_counter_id
        form.clickhouse_login.data = integration.clickhouse_login
        form.clickhouse_password.data = integration.clickhouse_password
        form.clickhouse_host.data = integration.clickhouse_host
        form.clickhouse_db.data = integration.clickhouse_db
    return render_template("create_integration.html", form=form)

@bp.route('/settings', methods = ['GET'])
@login_required
def setup():
    setup_already = Integration.query.filter_by(user_id=current_user.get_id()).first()
    if setup_already:
        api = setup_already.api_key
        domain = setup_already.user_domain
        metrika_key = setup_already.metrika_key
        metrika_counter_id = setup_already.metrika_counter_id
        clickhouse_login = setup_already.clickhouse_login
        clickhouse_password = setup_already.clickhouse_password
        clickhouse_host = setup_already.clickhouse_host
        clickhouse_db = setup_already.clickhouse_db
        return render_template('yoursettings.html', api=api, domain=domain, metrika_key=metrika_key, metrika_counter_id=metrika_counter_id, clickhouse_login=clickhouse_login, clickhouse_password=clickhouse_password, clickhouse_host=clickhouse_host, clickhouse_db=clickhouse_db)
    return render_template('settings.html')
