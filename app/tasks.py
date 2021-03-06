"""
all these functions works on Redis
here we do stuff that takes time
"""

import time
import sys
import requests
import datetime
import concurrent.futures
import pandas as pd
import io
from rq import get_current_job
from app import db
from app import create_app
from app.models import Task, Integration,Message, User
from app.utils import encode_this_string
from app.clickhousehub.metrica_logs_api import handle_integration
from app.clickhousehub.metrica_logs_api import drop_integration
from app.clickhousehub.clickhouse import get_tables
from app.grhub.grmonster import GrMonster
from app.clickhousehub.clickhouse import get_dbs
from app.clickhousehub.clickhouse_custom_request import create_ch_db
from app.clickhousehub.clickhouse_custom_request import give_user_grant
from app.clickhousehub.clickhouse_custom_request import request_iam

app = create_app(adminFlag=False)
app.app_context().push()


def send_search_contacts_to_gr_ftp(contacts_list, external_name, method ,integration, user_id):
    _set_task_progress(0)
    grmonster = GrMonster(api_key = integration.api_key,\
                            ftp_login = integration.ftp_login,\
                            ftp_pass = integration.ftp_pass)
    grmonster.store_external_segment_from_list(contacts_list, external_name, method)
    _set_task_progress(100, 'Вешний сегмент загружен в GR', user_id)

def assign_crypto_to_user_id(admin_user_id, user_id, crypto):
    print(type(user_id))
    print()
    _set_task_progress(0)
    # check if db already exists
    if crypto in get_dbs():
        _set_task_progress(100,'ERROR db with this name already exists, dog', admin_user_id)
        return -1
    # get user from db by id or except
    try:
        user = User.query.filter_by(id=user_id).one()
    except Exception as e:
        _set_task_progress(100,'ERROR No user was foung for {}'.format(user_id), admin_user_id)
        return -1
    # check if user already got crypto
    if user.crypto != None:
        _set_task_progress(100,'ERROR This user already set up, dog', admin_user_id)
        return -1
    # assign crypto if it unique
    try:
        user.crypto = crypto
        db.session.commit()
    except Exception as e:
        _set_task_progress(100,'ERROR {} - this crypto already exists'.format(crypto), admin_user_id)
        return -1
    # now let's create clickhouse db
    # and
    # give user grant access to crypto db
    try:
        _set_task_progress(50, 'Пока все ОК! Запрашиваю токен и создаю базы данных')
        # dont forget to update iam token
        iam_token = request_iam()
        if not iam_token:
            raise Exception('ERROR Failed to request iam')
        create_ch_db(crypto)
        give_user_grant('user1', crypto) ## # TODO: drop hardcode use config user name
    except Exception as err:
        user.crypto = None
        db.session.commit()
        _set_task_progress(100,'ERROR \n' + str(err) + '\nsmth went wrong dog :(( try again later..', admin_user_id)
        return -1

    _set_task_progress(100, f'Победа - {user.email} присвоен {user.crypto}', admin_user_id)
    app.logger.info('### Done!')


def send_search_contacts_to_gr(search_contacts_list, campaignId, api_key, user_id):
    _set_task_progress(0)
    success_load_count = 0
    grmonster = GrMonster(api_key, '')
    # for contact_email in search_contacts_list:
    # We can use a with statement to ensure threads are cleaned up promptly
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Start the load operations and mark each future with its URL
        future_to_email = {executor.submit(grmonster.post_contact_to_list, email, campaignId): email for email in search_contacts_list}
        for idx,future in enumerate(concurrent.futures.as_completed(future_to_email)):
            _set_task_progress(int((idx*100)/len(search_contacts_list)))
            email = future_to_email[future]
            try:
                response = future.result()
            except Exception as exc:
                print('%r generated an exception: %s' % (email, exc))
            else:
                success_load_count+=1
                print('%r address loaded with status %d' % (email, response.status_code))
    report_string = f'Загружено контатов в GR: {success_load_count} из {len(search_contacts_list)}'
    _set_task_progress(100, report_string, user_id)



def _set_task_progress(progress, comment='', user_id=0):
    job = get_current_job()
    if job:
        job.meta['progress'] = progress
        job.save_meta()
        task = Task.query.get(job.get_id())
        task.user.add_notification('task_progress', {'task_id': job.get_id(),
                                                     'progress': comment if comment else \
                                                            str(progress) + '%'})
        if  progress >= 100:
            print(f'Task complete, here is the task: \n{task}')
            task.complete = True
        if user_id:
            user = User.query.filter_by(id=user_id).first()
            timestamp= datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user.send_message(f'{str(timestamp)} : {comment} ')
            user.add_notification('unread_message_count', user.new_messages())
        db.session.commit()

def init_clickhouse_tables(integration_obj, user_obj, paramss,regular_load=False):
    _set_task_progress(0)
    try:
        for count,params in enumerate(paramss):
            _set_task_progress(50 * count // len(paramss))
            handle_integration(integration_obj, user_obj, params)
        if regular_load:
            _set_task_progress(100, 'Ежедневная автоматическая загрузка - Готово', user_obj['user_id'])
        else:
            _set_task_progress(100, 'Создание базы данных - Готово', user_obj['user_id'])
    except Exception as err:
        _set_task_progress(100)
        if not regular_load:
            _set_task_progress(100, 'Создание базы данных - Ошибка', user_obj['user_id'])
            drop_integration(user_obj['user_crypto'], integration_obj.id)
            Integration.query.filter_by(id = integration_obj.id).first_or_404().delete_myself()
        else:
            _set_task_progress(100, 'Ежедневная автоматическая загрузка - Ошибка', user_obj['user_id'])
        
        app.logger.info('### init_clickhouse_tables EXCEPTION regular_load={}'.format(regular_load))
        app.logger.error('### Unhandled exception {exc_info}\n{err}'.format(exc_info=sys.exc_info(), err=err))

def set_callback(integration_obj,user_obj):
    _set_task_progress(0)
    try:
        grmonster = GrMonster(api_key=integration_obj.api_key, \
                                callback_url=integration_obj.callback_url, \
                                ftp_login = integration_obj.ftp_login, \
                                ftp_pass = integration_obj.ftp_pass)
        set_callback_response = grmonster.set_callback_if_not_busy()
    except KeyError as err:
        integration = Integration.query.filter_by(id = integration_obj.id).first()
        integration.set_callback_dummy()
        db.session.commit()
        _set_task_progress(100, f'Создание уведомления - Уведомления вашего аккаунта уже заняты' ,user_obj['user_id'])
    else:
        _set_task_progress(100, f'Создание уведомления - Успех' ,user_obj['user_id'])

def set_ftp(integration_obj,user_obj):
    # ftp folders init
    _set_task_progress(0)
    try:
        grmonster = GrMonster(api_key=integration_obj.api_key, \
                                ftp_login = integration_obj.ftp_login, \
                                ftp_pass = integration_obj.ftp_pass)
        grmonster.init_ftp_folders()
    except Exception as err:
        print(err)
        _set_task_progress(100, f'Создание FTP директорий - Ошибка' ,user_obj['user_id'])
    else:
        _set_task_progress(100, f'Создание FTP директорий - Успех' ,user_obj['user_id'])       


def init_gr_contacts_chunk(integration_obj,user_obj, chunk_size=100):
    _set_task_progress(0)
    # get hash field id if exists else create and get
    # TODO NEED REFACTORING SO BAD
    grmonster = GrMonster(api_key = integration_obj.api_key, \
                        ftp_pass = integration_obj.ftp_pass, \
                        ftp_login= integration_obj.ftp_login)
    hash_field_id = grmonster.get_hash_field_id()
    campaigns = grmonster.get_gr_campaigns()
    campaigns_ids_list = [c[0] for c in campaigns]
    search_contacts_total_pages_count = grmonster.get_search_contacts_total_pages_count(hash_field_id, campaigns_ids_list)
    empty_contacts_chunk = grmonster.get_contacts_field_not_assigned_chunk(chunk_size)
    email_cid_df = pd.DataFrame(empty_contacts_chunk, columns=['email','campaign_id'])
    campaigns = grmonster.get_gr_campaigns()
    campaigns_df = pd.DataFrame(campaigns, columns=['campaignId', 'name'])  
    email_cname = email_cid_df.merge(campaigns_df, left_on='campaign_id',right_on='campaignId')[['email','name']]
    email_cname[grmonster.hashed_email_custom_field_name] = email_cname['email'].apply(lambda x: encode_this_string(x))
    unique_campaign_names = email_cname['name'].unique()
    ready_campaign_string_buffers = {}
    for campaign_name in unique_campaign_names:
        single_campaign_df = email_cname[email_cname['name'] == campaign_name]
        if single_campaign_df.shape[0]:
            rec = single_campaign_df[['email',grmonster.hashed_email_custom_field_name]].to_csv(index=False)
            df_bytes = rec.encode('utf-8')
            # text buffer
            # set buffer start point at the begining
            s_buf = io.BytesIO(df_bytes)
            s_buf.seek(0)
            ready_campaign_string_buffers[campaign_name] = s_buf
    attempts = 5
    cur_attempt = 0
    for campaign_name,string_buffer in ready_campaign_string_buffers.items():
        ftp_files_list = grmonster.ftp_list_files('/sync_contacts/update/')
        print('Files in sync_contacts/update/ \n',ftp_files_list, f'{campaign_name}.csv', f'{campaign_name}.csv' in ftp_files_list)
        while f'{campaign_name}.csv' in ftp_files_list:
            if cur_attempt >= attempts:
                _set_task_progress(100, 'Проблемы с GR FTP. Повторите операцию позже', user_obj['user_id'])  
                return
            time.sleep(3*60)
            ftp_files_list = grmonster.ftp_list_files('sync_contacts/update/')
            print('Files in sync_contacts/update/ \n',ftp_files_list, f'\n Current attempt: {cur_attempt}')
            cur_attempt += 1
        grmonster.ftp_gr(f'/sync_contacts/update/{campaign_name}.csv',string_buffer)
    
    # continue only after all files dissapear from ftp folder
    print('continue only after all files dissapear from ftp folder')
    cur_attempt = 0
    ftp_files_set = set(grmonster.ftp_list_files('/sync_contacts/update/'))
    print('ftp_files_set', ftp_files_set)
    loaded_campaigns = set(ready_campaign_string_buffers.keys())
    loaded_campaigns_names_set = {campaign + '.csv' for campaign in loaded_campaigns}
    print('loaded_campaigns_names_set', loaded_campaigns_names_set)
    intesection_names = loaded_campaigns_names_set.intersection(ftp_files_set)
    print('intesection_names', intesection_names)
    while loaded_campaigns_names_set.intersection(ftp_files_set):
        if cur_attempt == attempts:
            print('Fuck that FTP is too slow. So let\'s moove on')
        cur_attempt+=1
        print(f'{len(loaded_campaigns_names_set)} files on load. Waiting {len(loaded_campaigns_names_set)} minutes. \t attempt № ', cur_attempt)
        time.sleep(len(loaded_campaigns_names_set)*60)
        ftp_files_set = set(grmonster.ftp_list_files('/sync_contacts/update/'))
    _set_task_progress(100, 'Проставление служебного поля контактам GR завершена успешно', user_obj['user_id'])  