# Phase 1: Basic Term Management

## 1. Overview

This document defines the requirements for CRUD (Create, Read, Update, Delete) APIs to manage a hierarchical taxonomical data system consisting of **Layers**, **Domains**, **Terms**, and **Term Relationships**.

## 2. Data Model Summary

The system manages four interconnected entity types:

- **Layers**: Top-level groupings that contain domains
- **Domains**: Sub-groups within layers that contain terms
- **Terms**: Taxonomical entries with titles and definitions, forming hierarchical relationships
- **Term Relationships**: Connections between terms via specific predicates

## 3. Functional Requirements

### 3.1 Layer Management APIs

#### 3.1.1 Create Layer

- **Endpoint:** `POST /api/layers`
- **Purpose:** Create a new layer
- **Required Fields:** `title`
- **Optional Fields:** `definition`, `primary_predicate`
- **Validation:** Layer title must be unique
- **Behavior:** When a layer is created, vector embeddings for the title and definition are automatically generated and stored.
- **Response:** Created layer object with generated `id`

#### 3.1.2 Read Layer(s)

- **Endpoint:** `GET /api/layers/{id}` (single), `GET /api/layers` (list)
- **Purpose:** Retrieve layer information
- **Query Parameters:** For list - pagination, filtering, sorting
- **Response:** Layer object(s) with associated domain count, including title, definition, primary_predicate, vector embeddings, and creation date

#### 3.1.3 Update Layer

- **Endpoint:** `PUT /api/layers/{id}`
- **Purpose:** Modify existing layer
- **Updatable Fields:** `title`, `definition`, `primary_predicate`
- **Validation:** Updated title must remain unique
- **Behavior:** When the title or definition is updated, new vector embeddings are generated and stored.
- **Response:** Updated layer object

#### 3.1.4 Delete Layer

- **Endpoint:** `DELETE /api/layers/{id}`
- **Purpose:** Remove layer and cascade delete dependencies
- **Constraints:** Must handle cascade deletion of associated domains, terms, and relationships
- **Response:** Success confirmation

### 3.2 Domain Management APIs

#### 3.2.1 Create Domain

- **Endpoint:** `POST /api/domains`
- **Purpose:** Create a new domain within a layer
- **Required Fields:** `title`, `definition`, `layer_id`
- **Validation:** Domain title must be unique, `layer_id` must exist
- **Behavior:** When a domain is created, vector embeddings for the title and definition are automatically generated and stored.
- **Response:** Created domain object with generated `id`

#### 3.2.2 Read Domain(s)

- **Endpoint:** `GET /api/domains/{id}` (single), `GET /api/domains` (list)
- **Purpose:** Retrieve domain information
- **Query Parameters:** For list - `layer_id` filter, pagination, sorting
- **Response:** Domain object(s) with associated layer info and term count, including title, definition, vector embeddings, and creation date

#### 3.2.3 Update Domain

- **Endpoint:** `PUT /api/domains/{id}`
- **Purpose:** Modify existing domain
- **Updatable Fields:** `title`, `definition`, `layer_id`
- **Validation:** Updated title must remain unique, `layer_id` must exist
- **Behavior:** When the title or definition is updated, new vector embeddings are generated and stored.
- **Response:** Updated domain object

#### 3.2.4 Delete Domain

- **Endpoint:** `DELETE /api/domains/{id}`
- **Purpose:** Remove domain and cascade delete dependencies
- **Constraints:** Must handle cascade deletion of associated terms and relationships
- **Response:** Success confirmation

### 3.3 Term Management APIs

#### 3.3.1 Create Term

- **Endpoint:** `POST /api/terms`
- **Purpose:** Create a new term within a domain
- **Required Fields:** `title`, `definition`, `domain_id`, `layer_id`
- **Optional Fields:** `parent_term_id`
- **Validation:** `domain_id` and `layer_id` must exist, `parent_term_id` (if provided) must exist and belong to same domain, term title must be unique within domain
- **Behavior:** When a term is created, vector embeddings for the title and definition are automatically generated and stored. The term is created with version 1, and creation and last modified timestamps are set.
- **Response:** Created term object with generated `id`

#### 3.3.2 Read Term(s)

- **Endpoint:** `GET /api/terms/{id}` (single), `GET /api/terms` (list)
- **Purpose:** Retrieve term information
- **Query Parameters:** For list - `domain_id` filter, `layer_id` filter, `parent_term_id` filter, pagination, sorting
- **Response:** Term object(s) with hierarchy information (parent/children), including title, definition, vector embeddings, creation date, version, and last modified date

#### 3.3.3 Update Term

- **Endpoint:** `PUT /api/terms/{id}`
- **Purpose:** Modify existing term
- **Updatable Fields:** `title`, `definition`, `parent_term_id`
- **Validation:** `parent_term_id` must belong to same domain, cannot create circular references, term title must remain unique within domain
- **Behavior:** When the title or definition is updated, new vector embeddings are generated and stored. The version number is incremented, and the last modified timestamp is updated.
- **Response:** Updated term object

#### 3.3.4 Delete Term

- **Endpoint:** `DELETE /api/terms/{id}`
- **Purpose:** Remove term and handle hierarchy/relationship cleanup
- **Constraints:** Must handle orphaned child terms and remove associated relationships
- **Response:** Success confirmation

### 3.4 Term Relationship Management APIs

#### 3.4.1 Create Term Relationship

- **Endpoint:** `POST /api/term-relationships`
- **Purpose:** Create a relationship between two terms
- **Required Fields:** `source_term_id`, `target_term_id`, `predicate`
- **Validation:** Both term IDs must exist, prevent duplicate relationships
- **Response:** Created relationship object with generated `id`

#### 3.4.2 Read Term Relationships

- **Endpoint:** `GET /api/term-relationships/{id}` (single), `GET /api/term-relationships` (list)
- **Purpose:** Retrieve relationship information
- **Query Parameters:** For list - `source_term_id`, `target_term_id`, `predicate` filters
- **Response:** Relationship object(s) with full term information

#### 3.4.3 Update Term Relationship

- **Endpoint:** `PUT /api/term-relationships/{id}`
- **Purpose:** Modify existing relationship
- **Updatable Fields:** `predicate`
- **Validation:** Maintain referential integrity
- **Response:** Updated relationship object

#### 3.4.4 Delete Term Relationship

- **Endpoint:** `DELETE /api/term-relationships/{id}`
- **Purpose:** Remove specific term relationship
- **Response:** Success confirmation

## 4. Technical Requirements

### 4.1 Data Integrity

- Enforce foreign key constraints across all entity relationships
- Implement cascading delete operations where appropriate
- Prevent circular references in term hierarchies
- Validate unique constraints (layer titles, domain titles, term titles within domains, relationship uniqueness)
- Perform validation checks before committing changes to ensure data integrity

### 4.2 API Standards

- RESTful API design principles
- JSON request/response format
- HTTP status codes (200, 201, 400, 404, 500)
- Consistent error response structure

### 4.3 Performance

- Implement pagination for list endpoints (default page size: 50)
- Support filtering and sorting on list endpoints
- Optimize queries for hierarchical term retrieval