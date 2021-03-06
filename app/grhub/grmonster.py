"""
Here is the main class of the module
it lays on the top of inheritance
it aggragates and do bussines logic over low level GrUtils methods
"""
import concurrent.futures
from pprint import pprint
from app.grhub.grutils import GrUtils
from app.utils import encode_this_string
import pandas as pd
from pprint import pprint
import io


class GrMonster(GrUtils):
    hashed_email_custom_field_name = 'hash_metrika'
    big_enough_newsletter = 0
    external_segments_root_dir = 'sync_external_segments'
    external_segments_method_dirs = ['insert','replace']
    per_page = 1000

    def __init__(self, api_key, callback_url = '', ftp_login = '', ftp_pass = ''):
        super().__init__(api_key,ftp_login,ftp_pass)
        self.callback_url = callback_url
        self.custom_not_assigned_search_json = {
            'subscribersType':['subscribed'],
            'sectionLogicOperator':'and',
            'section':[{
                'campaignIdsList':None,
                "logicOperator": "or",
                "subscriberCycle": [
                    "receiving_autoresponder",
                    "not_receiving_autoresponder"
                ],
                "subscriptionDate": "all_time",
                "conditions":[
                    {
                        "conditionType": "custom",
                        "operator": "not_assigned",
                        "operatorType": "string_operator",
                        'scope': None
                    }
                ]
            }]
        }


    def get_broadcast_messages_since_date_subject_df(self, since_date):
        messages_raw_response = self.get_messages()
        big_enough_since_array_dic = [\
                        {'send_on':newsletter['sendOn'].split('T')[0],\
                        'subject':newsletter['subject']} \
                        for newsletter in messages_raw_response.json() \
                        if newsletter['sendOn'] > since_date and \
                        newsletter['type'] == 'broadcast' and \
                        int(newsletter['sendMetrics']['sent'])>self.big_enough_newsletter\
                        ]
        messages_df = pd.DataFrame(big_enough_since_array_dic)
        return messages_df

    def get_search_contacts_total_pages_count(self, field_id, campaigns_ids_list):
        self.custom_not_assigned_search_json['section'][0]['campaignIdsList'] = campaigns_ids_list
        self.custom_not_assigned_search_json['section'][0]["conditions"][0]['scope'] = field_id
        return self.get_total_pages_count('search-contacts/contacts?perPage=1',self.per_page ,self.custom_not_assigned_search_json)

    def get_contacts_field_not_assigned_chunk(self,chunk_size):
        search_contacts = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            # Start the get search contacts operations and mark each future with its page
            future_to_page = { executor.submit(self.get_search_contacts_contacts, \
                                               self.custom_not_assigned_search_json, \
                                               self.per_page, page):page for page in range(1,chunk_size+1)}
            for idx,future in enumerate(concurrent.futures.as_completed(future_to_page)):
                page = future_to_page[future]
                print(f'page handled : total pages - {idx}:{len(future_to_page)}')
                try:
                    response = future.result()
                    search_contacts += [[r['email'],r['campaign']['campaignId']] for r in response.json()]
                except ConnectionRefusedError as exc:
                    print()
                    print(f'{page} generated an exception: {exc}')
        print()
        return search_contacts

    def get_search_contacts_field_not_assigned(self, field_id, campaigns_ids_list):
        per_page = 1000
        search_contacts = []
        json = {
            'subscribersType':['subscribed'],
            'sectionLogicOperator':'and',
            'section':[{
                'campaignIdsList':campaigns_ids_list,
                "logicOperator": "or",
                "subscriberCycle": [
                    "receiving_autoresponder",
                    "not_receiving_autoresponder"
                ],
                "subscriptionDate": "all_time",
                "conditions":[
                    {
                        "conditionType": "custom",
                        "operator": "not_assigned",
                        "operatorType": "string_operator",
                        'scope': field_id
                    }
                ]
            }]
        }
        search_contacts_total_pages = self.get_total_pages_count('search-contacts/contacts?perPage=1',per_page ,json)
        if search_contacts_total_pages > 150:
            print('GR lists are too big')
            raise TimeoutError
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            # Start the get search contacts operations and mark each future with its page
            future_to_page = {executor.submit(self.get_search_contacts_contacts, json, per_page, page):page for page in range(1, search_contacts_total_pages+1)}
            for idx,future in enumerate(concurrent.futures.as_completed(future_to_page)):
                page = future_to_page[future]
                try:
                    response = future.result()
                    search_contacts += [[r['email'],r['campaign']['campaignId']] for r in response.json()]
                except ConnectionRefusedError as exc:
                    print(f'{page} generated an exception: {exc}')
        return search_contacts

    def get_user_email(self):
        try: 
            return self.get_user_details()['email']
        except ConnectionRefusedError as err:
            print('Unable to get user email',err)

    def init_ftp_folders(self):
        if self.external_segments_root_dir not in self.ftp_list_files(''):
            print('Creating external_segments_root_dir')
            self.ftp_create_dir(self.external_segments_root_dir)
        for method_dir in self.external_segments_method_dirs:
            print(f'Creating {method_dir}')
            if method_dir not in self.ftp_list_files(f'/{self.external_segments_root_dir}'):
                self.ftp_create_dir(self.external_segments_root_dir+'/'+method_dir)

    def if_custom_field_exists(self, custom_field_name):
        custom_fields = self.get_customs()
        return custom_field_name in [custom_field['name'] for custom_field in custom_fields.json()]

    def get_hash_field_id(self):
        custom_fields = self.get_customs()
        if self.hashed_email_custom_field_name in [custom_field['name'] for custom_field in custom_fields.json()]:
            return [custom_field['customFieldId'] for custom_field \
                                                  in custom_fields.json() \
                                                  if custom_field['name'] == self.hashed_email_custom_field_name].pop()
        else:
            return self.create_custom_field(self.hashed_email_custom_field_name).json()['customFieldId']

    def set_callback_if_not_busy(self):
        # if ConnectionRefusedError then callback is free
        try:
            callback = self.get_callbacks()
            pprint(f'{callback.json()} already set PANIC')
            raise KeyError(f'Callback for this account is busy! PANIC')
        except ConnectionRefusedError as err:
            set_callback_response = self.set_callback(self.callback_url,['subscribe'])
            return set_callback_response

    def set_hash_email_custom_field_id(self):
        for custom in self.get_customs().json():
            if custom['name']==self.hashed_email_custom_field_name:
                self.hash_email_custom_field_id = custom['customFieldId']

    def store_external_segment_from_list(self, search_contacts_list, external_name, method):
        #data frame
        df = pd.DataFrame(search_contacts_list, columns=[external_name])
        rec = df.to_string(index=False)
        df_bytes = rec.encode('utf-8')
        # text buffer
        # set buffer start point at the begining
        s_buf = io.BytesIO(df_bytes)
        s_buf.seek(0)
        url = f"/sync_external_segments/{method}/" + self.get_user_email() + ".csv"
        print(url)
        self.store_external_segment(url, s_buf)

    def upsert_every_email_with_hashed_email(self, id_email_dic_list):
        responses = []
        print('Nubmer of contacts to init')
        print(len(id_email_dic_list))
        print('Usually it takes 0.25 sec per contact')
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_contact = {\
                    executor.submit(\
                        self.upsert_hash_field_for_contact, \
                        contact['contactId'], \
                        encode_this_string(contact['email'])\
                        ): \
                    contact['email'] \
                for contact in id_email_dic_list\
            }
            for future in concurrent.futures.as_completed(future_to_contact):
                contact = future_to_contact[future]
                try:
                    response_raw = future.result()
                    responses.append(response_raw)
                except Exception as exc:
                    pprint('%r generated an exception: %s' % (contact, exc))
        return responses
