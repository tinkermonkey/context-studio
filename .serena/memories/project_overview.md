# Context Studio Project Overview

## Purpose
Context Studio is a local-first application for creating and curating knowledge graphs, and using those graphs for RAG and communication for both humans and agents.

## Architecture
- **Back End:** Python, sqlite, configurable llm pipelines, remote sync via duckdb & parquet (local-server/)
- **Front End:** React, flowbite-react (ux/)  
- **Desktop App:** Tauri builds for MacOS, Windows, Linux, iOS & Android tablets (app/)
- **Future:** Chat-with-graph-data agent (agent/)

## Development Status
- **Back End:** Nearing beta stage, under very active development
- **Front End:** Nearing beta stage, under very active development in sync with back-end
- **Desktop App:** Not started
- **Business Chat Bridge:** Not started

## Core Principles
- **KISS (Keep It Simple, Stupid):** Simplicity should be a key goal in design
- **YAGNI (You Aren't Gonna Need It):** Avoid building functionality on speculation
- **Open/Closed Principle:** Software entities should be open for extension but closed for modification

## Change Management Process
1. Functionality is built in back-end first, tested and validated
2. UX for that functionality is built
3. When back-end APIs are added/updated/removed:
   - Run `/local-server/utils/update_api_specs.py` to update `openapi.json`
   - Front-end executes `npm run generate-types` 
   - Update hooks and services
   - Build user experience and workflows

## Issue Management
- Use GitHub issues for change documentation
- Use GitHub issue tasks for task management
- PRPs should be new GitHub issues with linked sub-tasks