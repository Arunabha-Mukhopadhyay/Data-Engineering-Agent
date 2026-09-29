# Data Engineering Agent

A Python project that uses LangGraph and Groq models to route requests to either an ETL agent or a PostgreSQL SQL agent.

The ETL agent can extract API data to files and transform supported files with Pandas. The SQL agent uses a PostgreSQL database schema as context to answer data questions.

## Requirements

- Python 3.11 or newer
- A Groq API key for the agent workflows
- `uv` for installing the locked project dependencies
- PostgreSQL is optional for ETL. It is required for the SQL workflow and for loading the sample CSVs into database tables.

## Setup

From the project root, install the dependencies:

```sh
uv sync
```

Create a `.env` file in the project root. At minimum, add your Groq API key:

```dotenv
GROQ_API_KEY=your_groq_api_key
```

For SQL-agent or database-loading workflows, add PostgreSQL settings too. Use the lowercase names shown because the application reads these exact variable names:

```dotenv
host=localhost
port=5432
database=your_database
user=your_postgres_role
password=your_password
```

Keep `.env` private; it is excluded by `.gitignore`. Do not commit API keys or database passwords.

## Run the Agent

Run the built-in API extraction example:

```sh
uv run python main.py
```

You can also activate the project environment and run it directly:

```sh
source .venv/bin/activate
python main.py
```

The example request is defined in `main.py`. It asks the agent to extract Pokémon data from PokeAPI and save a CSV under `data/extract/`. Edit that request to try a different extraction or transformation. The router and ETL agents use the `openai/gpt-oss-20b` model through Groq; model choices are configured in `utils/llm_pick.py`.

For a direct extraction without the LLM router, use the CLI:

```sh
uv run python etl_cli.py \
	--url https://pokeapi.co/api/v2/pokemon \
	--output-folder data/extract \
	--format csv
```

The CLI supports `csv`, `json`, and `parquet`. It does not require a Groq API key.

The graph-image generation is optional. If the environment does not have IPython installed, the app may print `Could not generate graph image: No module named 'IPython'` and continue.

## ETL Output

The extractor follows API `next` links, validates that every page contains a list of JSON objects in `results`, and writes the combined records. It writes files relative to the project root with the name `extracted_data` and creates the output directory if needed. For example:

```text
data/extract/extracted_data.csv
```

Requests have a 30-second timeout and pagination is capped at 1,000 pages. Completed and failed extraction attempts are recorded in `logs/etl_runs.jsonl`; query parameters are omitted from the logged source URL.

For transformations, the agent reads CSV, newline-delimited JSON, or Parquet input and asks a model for a JSON plan. The application applies only supported operations: filter, select columns, sort, drop duplicates, rename columns, and limit rows. Model-generated Python is not executed.

Parquet requires the optional `pyarrow` engine. Add it to the project with `uv add pyarrow` before choosing `--format parquet`.

## PostgreSQL Workflows

The ETL example does not require PostgreSQL or pre-created tables. PostgreSQL is used only when the router selects the SQL agent or when you load the included ride-sharing CSV data.

To create and populate the sample tables, first configure the PostgreSQL values in `.env` and make sure the database server and database exist. Then run:

```sh
uv run python feed_db.py
```

`feed_db.py` creates the `public.users`, `vehicles`, `rides`, `payments`, and `ratings` tables and loads the corresponding CSV files from `data/`. It validates headers, required fields, primary-key uniqueness, and configured unique fields, then loads through temporary staging tables and upserts by primary key. Running it updates or inserts source rows without truncating existing tables; rows removed from a CSV are not deleted from PostgreSQL.

The SQL agent needs valid PostgreSQL credentials and tables to answer database questions. Queries are restricted to a single `SELECT` or `WITH` statement, run in a read-only transaction with a 10-second statement timeout, and return at most 1,000 rows. Also use an appropriately restricted PostgreSQL role; application checks are not a substitute for least-privilege database permissions.

## Ride-Share Reports

After loading the sample tables, run the read-only reports:

```sh
uv run python -m utils.analytics
```

The reports show daily ride volume, cancellation rate, monthly completed-payment revenue, and top-rated drivers.

## Tests

Run the offline unit tests with:

```sh
uv run python -m unittest discover -s tests -v
```

The tests use mocked API and database interactions; they do not require live credentials or a running PostgreSQL server.

## Project Layout

```text
agents/          Router, ETL, and SQL LangGraph agents
Models/          Pydantic models and LangGraph state types
utils/           Database, ETL, and Groq model helpers
tests/           Offline tests for ETL, data quality, and SQL safeguards
data/            Sample CSVs and ETL input/output folders
main.py          Runs the built-in router and ETL example
etl_cli.py       Configurable direct API extraction CLI
feed_db.py       Creates and loads the sample PostgreSQL tables
utils/analytics.py  Read-only ride-share analytics reports
pyproject.toml   Project dependencies and Python requirement
uv.lock          Locked dependency versions
```

## Troubleshooting

- **Missing Groq API key:** confirm the project-root `.env` contains `GROQ_API_KEY` and restart the command.
- **Groq model not found:** check that the account can use the model configured in `utils/llm_pick.py`.
- **PostgreSQL role does not exist:** set `user` to an existing PostgreSQL role and confirm `database`, `host`, `port`, and `password` match that server. PostgreSQL is not needed for the ETL example.
- **IPython graph warning:** this only disables the optional graph image; it does not prevent the agent workflow from running.
- **Parquet output unavailable:** add the optional engine with `uv add pyarrow`.
