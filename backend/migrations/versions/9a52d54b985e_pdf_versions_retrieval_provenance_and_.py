"""pdf versions retrieval provenance and durable exports

Revision ID: 9a52d54b985e
Revises: 4419783888ce
"""
from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


revision = '9a52d54b985e'
down_revision = '4419783888ce'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_extension WHERE extname='vector') THEN RAISE EXCEPTION 'Install the pgvector extension in this database before migrating'; END IF; END $$")
    op.create_table('embedding_profiles',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('provider', sa.String(length=30), nullable=False),
    sa.Column('model', sa.String(length=160), nullable=False),
    sa.Column('dimensions', sa.Integer(), nullable=False),
    sa.Column('configuration', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('fingerprint')
    )
    op.create_table('claims',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('collection_id', sa.String(length=36), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_claims_collection_id'), 'claims', ['collection_id'], unique=False)
    op.create_table('claim_revisions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('claim_id', sa.String(length=36), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['claim_id'], ['claims.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('claim_id', 'revision')
    )
    op.create_index(op.f('ix_claim_revisions_claim_id'), 'claim_revisions', ['claim_id'], unique=False)
    op.create_table('exports',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('collection_id', sa.String(length=36), nullable=False),
    sa.Column('investigation_id', sa.String(length=36), nullable=False),
    sa.Column('review_revision', sa.Integer(), nullable=False),
    sa.Column('draft', sa.Boolean(), nullable=False),
    sa.Column('mode', sa.String(length=30), nullable=False),
    sa.Column('state', sa.String(length=24), nullable=False),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.Column('storage_key', sa.String(length=80), nullable=False),
    sa.Column('checksum', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['investigation_id', 'collection_id'], ['investigations.id', 'investigations.collection_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exports_collection_id'), 'exports', ['collection_id'], unique=False)
    op.create_index(op.f('ix_exports_investigation_id'), 'exports', ['investigation_id'], unique=False)
    op.create_table('provider_calls',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('job_id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('provider', sa.String(length=30), nullable=False),
    sa.Column('model', sa.String(length=160), nullable=False),
    sa.Column('state', sa.String(length=30), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('usage', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_provider_calls_job_id'), 'provider_calls', ['job_id'], unique=False)
    op.create_table('passage_embeddings',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('passage_id', sa.String(length=36), nullable=False),
    sa.Column('collection_id', sa.String(length=36), nullable=False),
    sa.Column('profile_id', sa.String(length=36), nullable=False),
    sa.Column('vector', pgvector.sqlalchemy.vector.VECTOR(), nullable=False),
    sa.ForeignKeyConstraint(['passage_id', 'collection_id'], ['passages.id', 'passages.collection_id'], ),
    sa.ForeignKeyConstraint(['profile_id'], ['embedding_profiles.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('passage_id', 'profile_id')
    )
    op.create_index(op.f('ix_passage_embeddings_collection_id'), 'passage_embeddings', ['collection_id'], unique=False)
    op.create_index(op.f('ix_passage_embeddings_passage_id'), 'passage_embeddings', ['passage_id'], unique=False)
    op.create_index(op.f('ix_passage_embeddings_profile_id'), 'passage_embeddings', ['profile_id'], unique=False)
    op.create_table('retrieval_hits',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('investigation_id', sa.String(length=36), nullable=False),
    sa.Column('collection_id', sa.String(length=36), nullable=False),
    sa.Column('passage_id', sa.String(length=36), nullable=False),
    sa.Column('method', sa.String(length=20), nullable=False),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('score', sa.String(length=60), nullable=False),
    sa.Column('in_context', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['investigation_id', 'collection_id'], ['investigations.id', 'investigations.collection_id'], ),
    sa.ForeignKeyConstraint(['passage_id', 'collection_id'], ['passages.id', 'passages.collection_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_retrieval_hits_collection_id'), 'retrieval_hits', ['collection_id'], unique=False)
    op.create_index(op.f('ix_retrieval_hits_investigation_id'), 'retrieval_hits', ['investigation_id'], unique=False)
    op.add_column('documents', sa.Column('family_id', sa.String(length=36), nullable=True))
    op.execute('UPDATE documents SET family_id=id')
    op.alter_column('documents', 'family_id', nullable=False)
    op.add_column('documents', sa.Column('version', sa.Integer(), server_default='1', nullable=False))
    op.add_column('documents', sa.Column('active', sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column('documents', sa.Column('media_type', sa.String(length=40), server_default='text/plain', nullable=False))
    op.add_column('documents', sa.Column('page_count', sa.Integer(), server_default='1', nullable=False))
    op.add_column('documents', sa.Column('warnings', sa.JSON(), server_default='[]', nullable=False))
    op.add_column('documents', sa.Column('extraction_version', sa.String(length=50), server_default='text-v1', nullable=False))
    op.create_index(op.f('ix_documents_family_id'), 'documents', ['family_id'], unique=False)
    op.add_column('investigations', sa.Column('configuration', sa.JSON(), server_default='{}', nullable=False))
    op.add_column('investigations', sa.Column('embedding_profile_id', sa.String(length=36), nullable=True))
    op.add_column('investigations', sa.Column('claim_id', sa.String(length=36), nullable=True))
    op.add_column('investigations', sa.Column('claim_revision', sa.Integer(), server_default='1', nullable=False))
    op.add_column('jobs', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('jobs', sa.Column('result_payload', sa.JSON(), nullable=True))
    op.add_column('passages', sa.Column('page_number', sa.Integer(), server_default='1', nullable=False))
    # ### end Alembic commands ###

def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('passages', 'page_number')
    op.drop_column('jobs', 'result_payload')
    op.drop_column('jobs', 'started_at')
    op.drop_column('investigations', 'claim_revision')
    op.drop_column('investigations', 'claim_id')
    op.drop_column('investigations', 'embedding_profile_id')
    op.drop_column('investigations', 'configuration')
    op.drop_index(op.f('ix_documents_family_id'), table_name='documents')
    op.drop_column('documents', 'extraction_version')
    op.drop_column('documents', 'warnings')
    op.drop_column('documents', 'page_count')
    op.drop_column('documents', 'media_type')
    op.drop_column('documents', 'active')
    op.drop_column('documents', 'version')
    op.drop_column('documents', 'family_id')
    op.drop_index(op.f('ix_retrieval_hits_investigation_id'), table_name='retrieval_hits')
    op.drop_index(op.f('ix_retrieval_hits_collection_id'), table_name='retrieval_hits')
    op.drop_table('retrieval_hits')
    op.drop_index(op.f('ix_passage_embeddings_profile_id'), table_name='passage_embeddings')
    op.drop_index(op.f('ix_passage_embeddings_passage_id'), table_name='passage_embeddings')
    op.drop_index(op.f('ix_passage_embeddings_collection_id'), table_name='passage_embeddings')
    op.drop_table('passage_embeddings')
    op.drop_index(op.f('ix_provider_calls_job_id'), table_name='provider_calls')
    op.drop_table('provider_calls')
    op.drop_index(op.f('ix_exports_investigation_id'), table_name='exports')
    op.drop_index(op.f('ix_exports_collection_id'), table_name='exports')
    op.drop_table('exports')
    op.drop_index(op.f('ix_claim_revisions_claim_id'), table_name='claim_revisions')
    op.drop_table('claim_revisions')
    op.drop_index(op.f('ix_claims_collection_id'), table_name='claims')
    op.drop_table('claims')
    op.drop_table('embedding_profiles')
    # ### end Alembic commands ###
