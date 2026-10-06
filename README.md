# Pubmed: Biomedical Literature gathreing tool with Knowledge Graph Toolkit and Candidates Extraction

<!-- Dodanie opisu -->


## Table of Contents
* [Requirements](#requirements)
* [Installation](#installation)
* [Configuration](#configuration)
* [Repository Layout](#repository-layout)
* [Corpus Builder](#corpus-builder)


## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Maxifunny/Pubmed.git
   ```
   ```bash
   cd Pubmed
   ```
2. Ensure you have Python 3.10 or higher installed:
   ```bash
   python --version
   ```
   



## Requirements
To make sure that you are able to work on this repository you need to:

1. Download the required libraries:
   ```bash
   pip install requirements.txt
   ```
2. Setup the .env file:
   ```bash
    touch .env
   ```

3. Make sure to add your email to the .env file:

    Example:
    ```
    EMAIL=@example.com
    ```

## Repository Layout

| Module | Role |
|--------|------|
| `corpus.py` | User interactive corpus builder |
| `pubmed.py` | Pubmed search and metadata fetching |
| `pmc.py` | PMC full-text download|
| `retry_failures.py` | Retrying the failed full-text downloads |
| `rebuild_text.py` | Rebuilding `article.txt` from stored `article.xml` |
| `database.py` | SQLite schema with article/search/failure functions, creates (`pubmed.db`) |
| `sync_database.py` | Syncing local articles into the database |
| `get_env.py` | `.env` loader |
| `knowledge_graph_v41.py` | Knowledge-graph schema |
| `extract_candidates_v41.py` | Candidate-sentence extraction for relation mining |

## Corpus Builder

Execute the builder:

```bash
python corpus.py
```

User input:
* PubMed query string
* (Optional) Start or End publication year
* Maximum number of records
* PMC Open Access full text only restriction



<!-- Pozosotała część pipeline'u -->