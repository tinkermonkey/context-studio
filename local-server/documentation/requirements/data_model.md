# Data Model

## SQLite Schema
- `layers` table:
  - `id`: Primary key (uuid)
  - `title`: Title of the layer
  - `definition`: Definition of the layer
  - `primary_predicate`: (optional) The primary predicate for this layer
  - `title_embedding`: Vector embedding of the title (using `sqlite-vec`)
  - `definition_embedding`: Vector embedding of the definition (using `sqlite-vec`)
  - `created_at`: Timestamp of creation

- `domains` table:
  - `id`: Primary key (uuid)
  - `layer_id`: The id of the layer to which this domain belongs (foreign key to `layers` table)
  - `title`: Title of the domain (UNIQUE)
  - `definition`: Definition of the domain (NOT NULL)
  - `title_embedding`: Vector embedding of the title (using `sqlite-vec`)
  - `definition_embedding`: Vector embedding of the definition (using `sqlite-vec`)
  - `created_at`: Timestamp of creation

- `terms` table:
  - `id`: Primary key (uuid)
  - `domain_id`: The id of the domain to which this term belongs (foreign key to `domains` table)
  - `layer_id`: The id of the layer to which this term belongs (foreign key to `layers` table)
  - `title`: The term title (text)
  - `definition`: The term definition (text)
  - `title_embedding`: Vector embedding of the title (using `sqlite-vec`)
  - `definition_embedding`: Vector embedding of the definition (using `sqlite-vec`)
  - `created_at`: Timestamp of initial creation
  - `version`: Integer tracking number of updates
  - `last_modified`: Timestamp of most recent modification
  - `UNIQUE(domain_id, title)`: Constraint ensuring term titles are unique within each domain

- `term_relationships` table:
  - `id`: Primary key (uuid)
  - `source_term_id`: Foreign key to `terms` table
  - `target_term_id`: Foreign key to `terms` table
  - `predicate`: The predicate of the relationship
  - `created_at`: Timestamp of relationship creation
  - `UNIQUE(source_term_id, target_term_id, predicate)`: Constraint ensuring relationship uniqueness