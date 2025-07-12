# Phase 2: Change Event Queue

## 1. Overview

This document defined the requirements for capturing change events for the core data types: **layers**, **domains**, **terms**, and **term_relationships**.

## 2. Event Data Model

Events should be captured in a sqlite table `graph_events` with the following fields:

- **id**: integer primary key
- **event_type**: `create`, `update`, `delete`
- **entity_type**: `layer`, `domain`, `term`, `term_relationship`
- **old_data**: JSON column capturing of the old record
- **new_data**: JSON column capturing of the updated record (null for `delete` events)
- **timestamp**: datetime column, current_timestamp
- **processed**: boolean, defaults to false

## 3. Event Lifecycle

Event rows should be created via sqlite database triggers when `layer`, `domain`, `term`, or `term_relationship` rows are created/updated/deleted.

### 3.1 Event Processor

After the event rows are created the event processor should periodically poll for unprocessed events.

- The default polling interval should be 1 second
- The application should pass in the path to the sqlite database when the `EventProcessor` class is instantiated
- The event processor should use threading to run under a separate thread from the main application, with start and stop methods used to manage the thread
- Events with `processed` = FALSE should be fetched on each execution of the loop (with a sane default maximum number to fetch)
- Each event should be individually processed
- There should be a separate event processor method for each of the `entity_type` values to keep the code segmented
- After each event is processed, it should be marked as `processed` = True
- There should be a slow polling thread which runs once per day which deletes all processed events that are older than 48 hours