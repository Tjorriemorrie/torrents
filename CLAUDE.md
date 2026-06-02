# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Django app that scrapes torrent sites (1337x, formerly rarbg) and organizes torrents into titles for movies, TV shows, and PC games. Uses SQLite database, Django admin as the primary UI, and BeautifulSoup for HTML parsing.

## Commands

```bash
# Run dev server
python manage.py runserver

# Run scraper (parses HTML files from 1337x_files/ and rarbg_files/, updates DB)
python manage.py scrape_sites

# Migrations
python manage.py makemigrations
python manage.py migrate

# Lint and format (via pre-commit / ruff)
ruff check . --fix
ruff format .

# Run tests
python manage.py test main
```

## Architecture

- **`torrents/`** - Django project config (settings, urls, wsgi/asgi)
- **`main/`** - Single Django app containing all business logic
  - **`scraper.py`** - Core scraping logic. Parses saved HTML files from `1337x_files/` directory (not live scraping). Maps 1337x subcategory codes (e.g. `/sub/54/0`) to internal categories. Auto-creates `Title` records from torrent names using regex parsing (TV: `S01E02` patterns, Movies: name + year extraction).
  - **`models.py`** - `Title` (grouped identity for torrents, with status workflow: New->Skipped/Finished), `Torrent` (individual torrent entry linked to a Title), `Expansion`, `Postcode`/`Distance` (geographic distance calculation, separate concern)
  - **`admin.py`** - Heavy admin customization with proxy models (`PcGames`, `TvShows`, `Movies`) providing category-specific filtered views with annotations (seeders, upload dates). Custom admin actions for status management.
  - **`selectors.py`** - Query helpers (old TV cleanup, recent games)
  - **`parsing.py`** - Title text normalization
  - **`constants.py`** - Site names, categories, subcategories, status codes
  - **`management/commands/`** - `scrape_sites` (main entry point), plus postcode-related commands

## Self-Maintenance

After every task completion, review this CLAUDE.md file and update it with any relevant changes discovered during the session (e.g. new commands, changed architecture, updated dependencies, new conventions). Keep the file accurate and current as the codebase evolves.

## Code Style

- Ruff for linting and formatting (configured in `pyproject.toml`)
- Single quotes, 100 char line length, Google-style docstrings
- Pre-commit hooks run ruff check/format on commit
- Python 3.11, Django 5.0
- Dependencies managed via `uv` and `pyproject.toml` (use `uv sync --all-extras` to install)
