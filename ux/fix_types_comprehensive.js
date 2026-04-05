const fs = require('fs');
const path = require('path');

// Read the types file
const typesFile = 'src/api/client/types.ts';
let content = fs.readFileSync(typesFile, 'utf-8');

// Find the closing of the schemas section
const schemasMatch = content.match(/(\s+);(\s+responses: never;)/);
if (!schemasMatch) {
    console.error('Could not find schemas section end');
    process.exit(1);
}

const closingIndex = content.lastIndexOf('};', schemasMatch.index);

// Build comprehensive type definitions
const additionalTypes = `
        /**
         * Additional dataset and RAG types for compatibility
         */
        UpdateDatasetDirectoryRequest: {
            path?: string;
            datasets_directory?: string;
        };
        SearchRequest: {
            query?: string;
            term?: string;
            limit?: number;
        };
        CentralityRequest: {
            algorithm?: string;
            node_ids?: string[];
        };
        PathRequest: {
            source?: string;
            source_id?: string;
            target?: string;
            target_id?: string;
        };
        NeighborsRequest: {
            node_id?: string;
            entity_id?: string;
            depth?: number;
        };
`;

// Insert the additional types
content = content.slice(0, closingIndex) + additionalTypes + content.slice(closingIndex);

// Save the file
fs.writeFileSync(typesFile, content);
console.log('Updated types file with additional schema definitions');
