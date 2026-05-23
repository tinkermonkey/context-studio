# ArXiv Corpus

Research papers from ArXiv (cs.DC - Distributed Systems and cs.SE - Software Engineering categories) for validation of Individual Entity Extraction pipelines.

## Composition

- **20 papers** from ArXiv cs.DC (Distributed, Parallel, and Cluster Computing)
- Published from 2018 onwards
- Contains abstracts and metadata for entity extraction validation

Papers typically cover:
- Consensus algorithms and distributed systems theory
- Microservices and service-oriented architecture
- Data replication and consistency models
- Cloud infrastructure and containerization
- Fault tolerance and resilience patterns

## Structure

```
papers/
  <arxiv_id>/
    metadata.json     - Paper metadata (title, authors, categories, URLs)
    abstract.txt      - Paper abstract (plain text)
    body.txt          - [Optional] Full paper body text (not in initial build)
```

## Usage

- `index.json` - Metadata about the corpus and summary of all papers
- `papers/<arxiv-id>/metadata.json` - Paper metadata
- `papers/<arxiv-id>/abstract.txt` - Paper abstract text

Abstracts exhibit above-average terminological care, making them good validation signals for entity consistency across papers.

## Refresh

To regenerate the corpus with different date ranges or paper counts:

```bash
cd local-server
python scripts/build_arxiv_corpus.py
```

The script is idempotent and will overwrite existing files. `index.json` and paper metadata are regenerated from API responses.

### Customization

Edit `build_arxiv_corpus.py` to change:
- `max_papers` - Number of papers to fetch (default: 20)
- `categories` - ArXiv category codes (default: ['cs.DC', 'cs.SE'])
- `date_from` - Start date for papers (default: '2018-01-01')

## Licensing & Attribution

ArXiv content is freely available for non-commercial research and educational use per the ArXiv terms of service. When using this corpus:

1. **Respect ArXiv licenses** - Most papers are under CC licenses or author copyright
2. **Attribute authors** - Include paper authors and titles in any analysis
3. **Non-commercial only** - Do not use for commercial purposes without permission

## ArXiv API Rate Limits

The build script respects ArXiv API rate limits:
- Maximum 3 requests per second
- Includes 0.4-second delay between requests

Adjust `delay_between_requests` parameter if necessary.

## Known Limitations

- **Abstracts only**: Full paper text not fetched in initial build; can be added later
- **Limited sample**: 20 papers is a starting point; production validation may benefit from 200-500 papers
- **Date range**: Limited to 2018+; older foundational papers excluded
- **No filtering**: Minimal filtering on paper quality or relevance beyond category
- **Update frequency**: Manual updates only; continuous crawling not implemented

## Performance Notes

- Corpus is checked into git as metadata only (index.json, metadata.json)
- Large content (full paper bodies) is gitignored
- Index regeneration takes ~30 seconds due to ArXiv API rate limits
