"""user, integrations tables, unique constraint for interation names

Revision ID: 8b89101e556d
Revises: 
Create Date: 2020-07-09 03:59:38.630097

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b89101e556d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=100), nullable=True),
    sa.Column('password_hash', sa.String(length=100), nullable=True),
    sa.Column('name', sa.String(length=1000), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)
    op.create_index(op.f('ix_user_name'), 'user', ['name'], unique=False)
    op.create_table('integration',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('integration_name', sa.String(length=100), nullable=True),
    sa.Column('api_key', sa.String(length=100), nullable=True),
    sa.Column('user_domain', sa.String(length=100), nullable=True),
    sa.Column('metrika_key', sa.String(length=100), nullable=True),
    sa.Column('metrika_counter_id', sa.Integer(), nullable=True),
    sa.Column('clickhouse_login', sa.String(length=20), nullable=True),
    sa.Column('clickhouse_password', sa.String(length=20), nullable=True),
    sa.Column('clickhouse_host', sa.String(length=200), nullable=True),
    sa.Column('clickhouse_db', sa.String(length=200), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('integration_name'),
    sa.UniqueConstraint('user_id', 'integration_name')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('integration')
    op.drop_index(op.f('ix_user_name'), table_name='user')
    op.drop_index(op.f('ix_user_email'), table_name='user')
    op.drop_table('user')
    # ### end Alembic commands ###
