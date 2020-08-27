from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, IntegerField, DateField
from wtforms.validators import DataRequired, ValidationError
from app.models import User, Integration
from datetime import date
from wtforms.fields.html5 import DateField

class EditIntegration(FlaskForm):
    integration_name = StringField("Название интеграции", validators=[DataRequired()])
    api_key = StringField('API ключ GetResponse')
    user_domain = StringField('Домен GetResponse')
    metrika_key = StringField('Ключ Яндекс Метрики')
    metrika_counter_id = IntegerField('ID счетчика Яндекс Метрики')

    start_date = DateField('От', validators=[DataRequired()])
    end_date = DateField('До')

    submit = SubmitField("Отправить")



class LinkGenerator(FlaskForm):
    link = StringField("Введите ссылку", validators=[DataRequired()])
    submit = SubmitField("Получить ссылку")
