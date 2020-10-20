from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, IntegerField, DateField,BooleanField
from wtforms.validators import DataRequired, ValidationError
from app.models import User, Integration
from datetime import date
from wtforms.fields.html5 import DateField
from app.grhub.grmonster import GrMonster
import requests
from flask import current_app
from ftplib import FTP


class CustomValidators(object):
    def validate_api_key(self, api_key):
        r = requests.get('https://api.getresponse.com/v3/accounts', \
                    headers={'X-Auth-Token': 'api-key {}'.format(api_key.data)})
        if r.status_code != 200 :
            raise ValidationError(('Нет контакта с GetResponse'))

    def validate_metrika_counter_id(self, metrika_counter_id):
        headers = {'Authorization':'OAuth {}'.format(self.metrika_key.data)}
        ROOT = 'https://api-metrika.yandex.net/'
        url = ROOT+'management/v1/counter/{}/logrequests'.format(metrika_counter_id.data)
        r = requests.get(url, headers=headers)
        if r.status_code != 200 :
            raise ValidationError(('Нет контакта с Yandex Метрикой. Проверьте ключ и счетчик'))

    def validate_ftp_pass(self, ftp_pass):
        # ftp object
        ftp = FTP(host = current_app.config['GR_FTP_HOST'])
        try:
            ftp.login(self.ftp_login.data, self.ftp_pass.data)
        except:
            raise ValidationError(('Нет контакта с FTP. Проверьте логин и пароль'))

class EditIntegration(FlaskForm,CustomValidators):
    integration_name = StringField("Название интеграции", validators=[DataRequired()])
    api_key = StringField('API ключ GetResponse', validators=[DataRequired()])
    ftp_login = StringField('Логин GR FTP', validators=[DataRequired()])
    ftp_pass = StringField('Пароль GR FTP', validators=[DataRequired()])
    metrika_key = StringField('Ключ Яндекс Метрики', validators=[DataRequired()])
    metrika_counter_id = StringField('ID счетчика Яндекс Метрики', validators=[DataRequired()])
    start_date = DateField('От', validators=[DataRequired()])
    auto_load = BooleanField('Автозагрузка')
    submit = SubmitField("Отправить")


class LinkGenerator(FlaskForm):
    link = StringField("Введите ссылку", validators=[DataRequired()])
    submit = SubmitField("Получить ссылку")

class GrInitializer(FlaskForm, CustomValidators):
    integration_name = StringField("Название интеграции", validators=[DataRequired()])
    api_key = StringField('API ключ GetResponse', validators=[DataRequired()])
    submit = SubmitField("Отправить")
