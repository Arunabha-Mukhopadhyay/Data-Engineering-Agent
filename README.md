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

The graph-image generation is optional. If the environment does not have IPython installed, the app may print `Could not generate graph image: No module named 'IPython'` and continue.

## ETL Output

The extraction tool supports `csv`, `json`, and `parquet` output formats. It writes files relative to the project root with the name `extracted_data` and creates the output directory if needed. For example:

```text
data/extract/extracted_data.csv
```

The extractor reads the API response's `results` field. APIs that paginate results may return only one page; the current extractor does not follow a `next` link. PokeAPI's default endpoint returns 20 Pokémon per page, so the example CSV contains the first 20 unless pagination is added.

For transformations, the agent reads CSV, newline-delimited JSON, or Parquet input and asks a model to generate Pandas code. That generated code is executed by the application. Only use this feature with trusted requests and data, and do not run it in an environment containing secrets or valuable files.

## PostgreSQL Workflows

The ETL example does not require PostgreSQL or pre-created tables. PostgreSQL is used only when the router selects the SQL agent or when you load the included ride-sharing CSV data.

To create and populate the sample tables, first configure the PostgreSQL values in `.env` and make sure the database server and database exist. Then run:

```sh
uv run python feed_db.py
```

`feed_db.py` creates the `public.users`, `vehicles`, `rides`, `payments`, and `ratings` tables and loads the corresponding CSV files from `data/`. **Warning:** it truncates these tables before loading, so running it again replaces their current contents. Use a disposable database or back up data first.

The SQL agent needs valid PostgreSQL credentials and tables to answer database questions. Use an appropriately restricted database role; model-generated SQL should not be treated as a security boundary.

## Project Layout

```text
agents/          Router, ETL, and SQL LangGraph agents
Models/          Pydantic models and LangGraph state types
utils/           Database, ETL, and Groq model helpers
data/            Sample CSVs and ETL input/output folders
main.py          Runs the built-in router and ETL example
feed_db.py       Creates and loads the sample PostgreSQL tables
pyproject.toml   Project dependencies and Python requirement
uv.lock          Locked dependency versions
```

## Troubleshooting

- **Missing Groq API key:** confirm the project-root `.env` contains `GROQ_API_KEY` and restart the command.
- **Groq model not found:** check that the account can use the model configured in `utils/llm_pick.py`.
- **PostgreSQL role does not exist:** set `user` to an existing PostgreSQL role and confirm `database`, `host`, `port`, and `password` match that server. PostgreSQL is not needed for the ETL example.
- **IPython graph warning:** this only disables the optional graph image; it does not prevent the agent workflow from running.
- **Only 20 API records:** the source endpoint is paginated and the current extractor processes only its first response page.
