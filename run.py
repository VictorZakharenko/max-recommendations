from app import create_app
from app.models import User, Integration
from app import db
app = create_app()


@app.cli.command()
def regular_load_to_clickhouse():
    """Clickhouse cron job."""
    users = User.query.filter_by(active=True).all()
    print('Users:', str(users))
    print('------')
    for user in users:
        user_integrations=Integration.query.filter_by(user_id=user.id).\
                                            filter_by(auto_load=True).all()
        print("Integrations:",str(user_integrations))
        for integration in user_integrations:
            mode = '-mode=regular'
            params = ['-source=hits', mode]
            params_2 = ['-source=visits', mode]
            user.launch_task('init_clickhouse_tables', ('Автоматическая загрузка метрик'),integration.metrika_key, integration.metrika_counter_id,user.crypto,  integration.id, [params,params_2])
            db.session.commit()
    print('Done!')
