import traceback
import requests
from io import StringIO
import ast
import numpy as np
import requests
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
import pandas as pd
from app.models import User, Integration
from app import db
from app.metrika import bp
from app.clickhousehub.clickhouse_custom_request import made_url_for_query,request_clickhouse
from app.metrika.secur import current_user_own_integration
from app.metrika.send_hash_to_gr import add_custom_field
from app.metrika.conversion_table_builder import generate_grouped_columns_sql

VISITS_AGGR_QUERY = '''
    SELECT *
    FROM {clickhouse_table_name}
    WHERE {where_statesments}
'''

COLUMNS = ['Email', \
            'Total Visits', \
            'Total Visits From Newsletter', \
            'Total Goals Complited', \
            'Total Goals From Newsletter', \
            'Conversion (TG/TV)', \
            'Email power proportion']


VISITS_RAW_QUERY = '''
    select * from(
        SELECT
            CASE  when extractURLParameter(StartURL, 'mxm') != ''
                  then base64Decode(extractURLParameter(StartURL, 'mxm'))
                  else concat('no-email',toString(ClientID)) end as email,

            sum(case when Date >= '{start_date}'
                then 1 else 0 end) as total_visits,

            sum(case when extractURLParameter(StartURL, 'mxm') != ''
                and (Date >= '{start_date}')
                then 1 else 0 end) as total_visits_from_newsletter,

            sum(case when Date >= '{start_date}'
                then length(GoalsID) else 0 end) as total_goals,

            sum(case when extractURLParameter(StartURL, 'mxm') != ''
                {grouped_columns}
                then length(GoalsID) else 0 end) as total_goals_from_newsletter,

            total_goals/total_visits,
            total_goals_from_newsletter/total_goals
        FROM {clickhouse_table_name}
        group by email
    )
    where total_visits != 0
'''


@bp.route('/metrika/<integration_id>/get_data')
@login_required
def metrika_get_data(integration_id):
    integration = Integration.query.filter_by(id=integration_id).first_or_404()
    if not current_user_own_integration(integration, current_user):
        print('Permission abort')
        abort(404)

    request_start_date = request.args.get('start_date')
    request_goals = request.args.get('goals')
    # TODO: validate start_date, goals
    current_app.logger.info("### selected-goals {}".format(request_goals))
    clickhouse_table_name = '{}.{}_raw_{}'.format(current_user.crypto, 'visits', integration_id)
    grouped_columns_sql = generate_grouped_columns_sql({'start_date':[request_start_date], 'goals':request_goals.split(',')})
    url_for_columns = made_url_for_query('DESC {}'.format(clickhouse_table_name), current_user.crypto)
    url_for_visits_all_data = made_url_for_query(\
        VISITS_RAW_QUERY.format(\
            clickhouse_table_name=clickhouse_table_name,\
            start_date = request_start_date,\
            grouped_columns = grouped_columns_sql
            ), current_user.crypto \
        )

    try:
        current_app.logger.info('### request_clickhouse start urls: {}\n{}'.format(url_for_columns,url_for_visits_all_data))
        # get column names 1
        response_with_columns_names = request_clickhouse(url_for_columns, current_app.config['AUTH'], current_app.config['CERTIFICATE_PATH'])
        # get table data and prepare it
        response_with_visits_all_data =request_clickhouse (url_for_visits_all_data, current_app.config['AUTH'], current_app.config['CERTIFICATE_PATH'])
        if any([\
                response_with_columns_names.status_code != 200,\
                response_with_visits_all_data.status_code !=200\
                ]):
            flash('Некорректная в дата!')
            print(response_with_visits_all_data.text)
            print()
            print(response_with_columns_names.text)
    except:
        flash('{} Ошибки в запросе или в настройках итеграции!'.format(integration.integration_name))
        return redirect(url_for('main.user_integrations'))

    # current_app.logger.info('### request_clickhouse done! columns: {}\ndata: {}'.format(response_with_columns_names, response_with_visits_all_data))
    file_from_string = StringIO(response_with_visits_all_data.text)
    visits_all_data_df = pd.read_csv(file_from_string,sep='\t',lineterminator='\n', names=COLUMNS)
    if request_goals:
        print('Before and after goals filter')
        print(visits_all_data_df.shape[0])
        visits_all_data_df = visits_all_data_df[visits_all_data_df['Total Goals Complited']!=0]
        print(visits_all_data_df.shape[0])
    max_df = visits_all_data_df

    # max_no_email_1graph = [ [int(max_row['Total Visits No Email']),int(max_row['Conversion (TG/TV)'])] for _, max_row in max_df[['Total Visits No Email','Conversion (TG/TV)']].iterrows() ] # 1 график - без email
    # max_email_1graph = [ [int(max_row['Total Visits Email']),int(max_row['Conversion (TG/TV)'])] for _, max_row in max_df[['Total Visits Email','Conversion (TG/TV)']].iterrows() ] # 1 график - с email

    max_no_email_1graph = [ [int(max_row['Total Visits']),int(max_row['Conversion (TG/TV)'])] for _, max_row in max_df[max_df['Total Visits From Newsletter'] != 0][['Total Visits','Conversion (TG/TV)']].iterrows() ] # 1 график - без email
    max_email_1graph = [ [int(max_row['Total Visits']),int(max_row['Conversion (TG/TV)'])] for _, max_row in max_df[max_df['Total Visits From Newsletter'] == 0][['Total Visits','Conversion (TG/TV)']].iterrows() ] # 1 график - с email

    if (len(max_no_email_1graph) == 0):
        max_no_email_1graph = [[0,0]]
    if (len(max_email_1graph) == 0):
        max_email_1graph = [[0,0]]


    conv_email_sum = max_df[max_df['Total Visits From Newsletter'] != 0]['Conversion (TG/TV)'].sum()
    conv_no_email_sum = max_df[max_df['Total Visits From Newsletter'] == 0]['Conversion (TG/TV)'].sum()

    front_end_df = max_df[['Email', 'Total Visits', 'Total Visits From Newsletter','Total Goals Complited', 'Total Goals From Newsletter', 'Conversion (TG/TV)', 'Email power proportion']]
    front_end_df= front_end_df.astype(str)
    json_to_return = front_end_df.to_json(default_handler=str, orient='table', index=False)

    json_to_return =json.loads(json_to_return)
    json_to_return['conv_email_sum'] = str(conv_email_sum)
    json_to_return['conv_no_email_sum'] = str(conv_no_email_sum)
    json_to_return['max_no_email_1graph'] = json.dumps(max_no_email_1graph)
    json_to_return['max_email_1graph'] = json.dumps(max_email_1graph)

    return json_to_return

@bp.route('/metrika/<integration_id>', methods = ['GET'])
@login_required
def metrika(integration_id):
    integration = Integration.query.filter_by(id=integration_id).first_or_404()
    if not current_user_own_integration(integration, current_user):
        abort(404)

    try:
        certificate_path = 'app/YandexInternalRootCA.crt'
        auth = {
        'X-ClickHouse-User': current_app.config['CLICKHOUSE_LOGIN'],
        'X-ClickHouse-Key': current_app.config['CLICKHOUSE_PASSWORD']
        }
        clickhouse_raw_table_name = '{}.{}_raw_{}'.format(current_user.crypto, 'visits', integration_id)
        query_count = 'SELECT count(Date) FROM {}'.format(clickhouse_raw_table_name)
        query_min = 'SELECT min(Date) FROM {}'.format(clickhouse_raw_table_name)
        query_max = 'SELECT max(Date) FROM {}'.format(clickhouse_raw_table_name)
        query_data_length = made_url_for_query(query_count, current_user.crypto)
        query_min_date = made_url_for_query(query_min, current_user.crypto)
        query_max_date = made_url_for_query(query_max, current_user.crypto)
        data_length_text =request_clickhouse(query_data_length, auth, certificate_path).text
        min_date_text = request_clickhouse(query_min_date, auth, certificate_path).text
        max_date_text = request_clickhouse(query_max_date, auth, certificate_path).text

    except Exception as e:
        traceback.print_exc()
        flash('{} Ошибки в настройках интеграции!'.format(integration.integration_name))
        return redirect(url_for('main.user_integrations'))

    # get goals
    counter_id = integration.metrika_counter_id
    metrika_key = integration.metrika_key
    headers = {'Authorization':'OAuth {}'.format(metrika_key)}
    ROOT = 'https://api-metrika.yandex.net/'
    url = ROOT+'management/v1/counter/{}/goals'.format(counter_id)
    r = requests.get(url, headers=headers)
    current_app.logger.info('### get goals status code: {}'.format(r.status_code))
    # print(r.json())
    goals = [(goal['id'],goal['name']) for goal in r.json()['goals']]

    if (current_user.email == 'sales@getresponse.com'):
        return render_template('metrika_example.html')
    else:
        return render_template(\
            'metrika.html',\
            min_date=min_date_text.strip(),\
            max_date=max_date_text.strip(),\
            data_length = data_length_text,\
            integration_name=integration.integration_name,\
            integration_id=integration_id,\
            goals=goals)

@bp.route('/metrika/callback_add_custom_field', methods = ['GET'])
def callback_add_custom_field():
    action = request.args.get('action')
    contact_email = request.args.get('contact_email')
    contact_id = request.args.get('CONTACT_ID')
    custom_field_id= 'Vu40V0'  #TODO id кастомного поля hash_metrika Макса
    if (action == 'subscribe'): #проверяем, что коллбек именно на подписку
        add_custom_field(contact_email, contact_id, custom_field_id)
    return redirect(url_for('main.index'))
