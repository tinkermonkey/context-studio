# Editable Table Component

## Outline

Users should be able to view, edit, and delete existing nodes (layers, domains, terms) in
tables which allow users to edit the nodes in-place.

## Capabilities

- The table component should work for the different node types (`layer`, `domain`, and `term`)
- The table component should utilize the API client in `/api` to read/write data to the backend
- The table component should have columns for `id`, `title`, `definition` and primary relationship for nodes (`layer_id` for `domain`, `domain_id` for terms), `last_modified`, and `created_at`
- The table component should support pagination
- The table component should support searching on title (default) or definition which should invoke the `/find` vector search api
- The table component should allow the `title` and `definition` values to be edited in-place and save the result via the API when edited
- The table should be built using gluestack-ui V2 components