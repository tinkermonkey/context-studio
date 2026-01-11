#!/bin/bash

# Update all API operations with OpenAPI specs
echo "Updating API operations..."
for file in openapi_extracts/operations/*.yaml; do
    op_name=$(basename "$file" .yaml)
    op_id="api.operation.$op_name"
    echo "  Updating $op_id..."
    .venv/bin/dr update "$op_id" --spec "$file" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "    ✓ Success"
    else
        echo "    ✗ Failed"
    fi
done

# Update all data model schemas
echo ""
echo "Updating data model schemas..."
for file in openapi_extracts/schemas/*.yaml; do
    schema_name=$(basename "$file" .yaml)
    schema_id="data_model.schema.$schema_name"
    echo "  Updating $schema_id..."
    .venv/bin/dr update "$schema_id" --spec "$file" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "    ✓ Success"
    else
        echo "    ✗ Failed"
    fi
done

echo ""
echo "All updates complete!"
