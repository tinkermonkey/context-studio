from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.orm import declarative_base, relationship
import uuid
import datetime


from sqlalchemy import JSON, Boolean
Base = declarative_base()

class Predicate(Base):
    __tablename__ = 'predicates'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    identifier = Column(String, unique=True, nullable=False)
    title = Column(String, unique=True, nullable=False)
    definition = Column(Text, nullable=True)
    mapping = Column(Text, nullable=True)  # JSON string
    date_created = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    date_modified = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), 
                          onupdate=lambda: datetime.datetime.now(datetime.UTC))
    
    # Relationships
    domains = relationship('Domain', back_populates='primary_predicate_ref')
    term_relationships = relationship('TermRelationship', back_populates='predicate_ref')

class GraphEvent(Base):
    __tablename__ = 'graph_events'
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)  # create, update, delete
    entity_type = Column(String, nullable=False)  # layer, domain, term, term_relationship
    old_data = Column(JSON, nullable=True)
    new_data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False)
    processed = Column(Boolean, default=False, nullable=False)

class Layer(Base):
    __tablename__ = 'layers'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, unique=True, nullable=False)
    definition = Column(Text)
    title_embedding = Column(BLOB)
    definition_embedding = Column(BLOB)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    version = Column(Integer, default=1)
    last_modified = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), onupdate=lambda: datetime.datetime.now(datetime.UTC))
    domains = relationship('Domain', back_populates='layer', cascade='all, delete-orphan')

class Domain(Base):
    __tablename__ = 'domains'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    layer_id = Column(String, ForeignKey('layers.id', ondelete='CASCADE'), nullable=False)
    title = Column(String, nullable=False)
    definition = Column(Text, nullable=False)
    title_embedding = Column(BLOB)
    definition_embedding = Column(BLOB)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    version = Column(Integer, default=1)
    last_modified = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), onupdate=lambda: datetime.datetime.now(datetime.UTC))
    primary_predicate = Column(String, nullable=True)
    primary_predicate_id = Column(String, ForeignKey('predicates.id'), nullable=True)
    predicate_set = Column(Text, nullable=True)  # JSON array
    layer = relationship('Layer', back_populates='domains')
    terms = relationship('Term', back_populates='domain', cascade='all, delete-orphan')
    # New relationship
    primary_predicate_ref = relationship('Predicate', back_populates='domains')
    __table_args__ = (
        UniqueConstraint('layer_id', 'title', name='_layer_title_uc'),
    )

class Term(Base):
    __tablename__ = 'terms'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    domain_id = Column(String, ForeignKey('domains.id', ondelete='CASCADE'), nullable=False)
    layer_id = Column(String, ForeignKey('layers.id', ondelete='CASCADE'), nullable=False)
    title = Column(String, nullable=False)
    definition = Column(Text, nullable=False)
    title_embedding = Column(BLOB)
    definition_embedding = Column(BLOB)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    version = Column(Integer, default=1)
    last_modified = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), onupdate=lambda: datetime.datetime.now(datetime.UTC))
    parent_term_id = Column(String, ForeignKey('terms.id', ondelete='SET NULL'))
    parent = relationship('Term', remote_side=[id], backref='children', foreign_keys=[parent_term_id])
    domain = relationship('Domain', back_populates='terms')
    __table_args__ = (
        UniqueConstraint('domain_id', 'title', name='_domain_title_uc'),
    )

class TermRelationship(Base):
    __tablename__ = 'term_relationships'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_term_id = Column(String, ForeignKey('terms.id', ondelete='CASCADE'), nullable=False)
    target_term_id = Column(String, ForeignKey('terms.id', ondelete='CASCADE'), nullable=False)
    predicate = Column(String, nullable=False)
    predicate_id = Column(String, ForeignKey('predicates.id'), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    # New relationship
    predicate_ref = relationship('Predicate', back_populates='term_relationships')
    __table_args__ = (UniqueConstraint('source_term_id', 'target_term_id', 'predicate', name='_relationship_uc'),)
