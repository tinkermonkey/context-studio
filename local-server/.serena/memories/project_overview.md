# Context Studio Local Server - Project Overview

## Purpose
Python server for the Context Studio (a React app built using Flowbite-React). This server is used to run the app locally during development and is deployed with the desktop app to serve the UX.

## Technology Stack
- **Language**: Python
- **Web Server**: uvicorn  
- **API Framework**: FastAPI
- **Database**: SQLite with SQLiteVector for vector storage
- **Data Validation**: Pydantic
- **Test Framework**: pytest
- **Additional**: langchain, sentence-transformers, spacy, nltk for NLP

## Key Features
- Graph data structure and utilities
- NLP reference and processing
- Vector embedding generation and search
- Change management system with distributed collaboration
- SQLite-based local storage with DuckDB for synchronization
- S3-compatible storage for distributed data sharing

## Project Structure
- `api/` - API endpoints
- `app.py` - Main application file
- `database/` - Models, migrations, utilities
- `tests/` - Unit, integration, and performance tests
- `documentation/` - Requirements, designs, and guides
- `services/` - Service layer components
- `utils/` - Utility functions and helpers