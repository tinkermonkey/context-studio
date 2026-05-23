#!/usr/bin/env python
"""
Build ArXiv corpus for validation.

This script fetches papers from ArXiv matching distributed systems (cs.DC)
and software engineering (cs.SE) categories from 2018 onwards. Fetches abstracts
and metadata for use in validation pipelines.

The script is idempotent and can be re-run to regenerate the corpus.

Rate limits: ArXiv API allows 3 requests per second. This script respects that.
License: ArXiv content is freely available for non-commercial research use.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import arxiv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fetch_arxiv_papers(
    categories: list[str],
    date_from: str = "2018-01-01",
    max_papers: int = 20,
    delay_between_requests: float = 0.4
) -> list[dict[str, Any]]:
    """
    Fetch papers from ArXiv matching specified categories.

    Args:
        categories: List of ArXiv category codes (e.g., ['cs.DC', 'cs.SE'])
        date_from: Start date for papers (YYYY-MM-DD format)
        max_papers: Maximum number of papers to fetch (total across all categories)
        delay_between_requests: Delay in seconds between requests (respect rate limits)

    Returns:
        List of paper metadata dictionaries
    """
    papers = []
    request_count = 0

    # Build separate queries for each category to avoid API issues
    client = arxiv.Client()

    # Parse date_from for ArXiv query
    # ArXiv format: submittedDate:[202001010000 TO 202012312359]
    date_from_arxiv = date_from.replace("-", "")
    date_query_suffix = f"AND submittedDate:[{date_from_arxiv}010000 TO 9999123123]"

    papers_per_category = max_papers // len(categories)

    for category in categories:
        # Use simple category query with date filtering
        query = f"cat:{category} {date_query_suffix}"
        print(f"Fetching papers from {category}...")

        search = arxiv.Search(
            query=query,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
            max_results=papers_per_category
        )

        category_papers = 0
        for paper in client.results(search):
            if category_papers >= papers_per_category:
                break

            paper_data = {
                "arxiv_id": paper.entry_id.split("/abs/")[-1],
                "title": paper.title,
                "authors": [author.name for author in paper.authors],
                "abstract": paper.summary,
                "published": paper.published.isoformat(),
                "categories": paper.categories,
                "pdf_url": paper.pdf_url,
                "arxiv_url": paper.entry_id,
            }
            papers.append(paper_data)
            category_papers += 1
            request_count += 1

            # Respect rate limits
            if request_count % 3 == 0:
                time.sleep(delay_between_requests)

    return papers


def build_arxiv_corpus(output_dir: str, max_papers: int = 20) -> None:
    """
    Build ArXiv corpus and write to output directory.

    Args:
        output_dir: Directory to write corpus to
        max_papers: Maximum number of papers to fetch
    """
    corpus_dir = Path(output_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)

    papers = fetch_arxiv_papers(
        categories=["cs.DC", "cs.SE"],
        date_from="2018-01-01",
        max_papers=max_papers
    )

    # Write papers to individual directories
    papers_dir = corpus_dir / "papers"
    papers_dir.mkdir(exist_ok=True)

    for paper in papers:
        paper_id = paper["arxiv_id"].replace("/", "_")
        paper_dir = papers_dir / paper_id
        paper_dir.mkdir(exist_ok=True)

        # Write metadata
        metadata = {
            "arxiv_id": paper["arxiv_id"],
            "title": paper["title"],
            "authors": paper["authors"],
            "published": paper["published"],
            "categories": paper["categories"],
            "pdf_url": paper["pdf_url"],
            "arxiv_url": paper["arxiv_url"],
        }

        metadata_file = paper_dir / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        # Write abstract
        abstract_file = paper_dir / "abstract.txt"
        with open(abstract_file, "w") as f:
            f.write(paper["abstract"])

    # Write index file
    index = {
        "source": "ArXiv API",
        "categories": ["cs.DC", "cs.SE"],
        "description_cs_dc": "Computer Systems - Distributed, Parallel, and Cluster Computing",
        "description_cs_se": "Computer Science - Software Engineering",
        "date_from": "2018-01-01",
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "paper_count": len(papers),
        "license": "ArXiv content is freely available for non-commercial research use",
        "papers": [
            {
                "arxiv_id": paper["arxiv_id"],
                "title": paper["title"],
                "authors": paper["authors"],
                "published": paper["published"],
                "categories": paper["categories"],
            }
            for paper in papers
        ]
    }

    index_file = corpus_dir / "index.json"
    with open(index_file, "w") as f:
        json.dump(index, f, indent=2)

    print(f"ArXiv corpus built: {len(papers)} papers")
    print(f"Index: {index_file}")
    print(f"Papers directory: {papers_dir}")


if __name__ == "__main__":
    output_dir = Path(__file__).parent.parent / "datafiles" / "validation" / "arxiv"
    build_arxiv_corpus(str(output_dir), max_papers=20)
