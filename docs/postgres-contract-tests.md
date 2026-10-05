# PostgreSQL contract tests

The PostgreSQL integration suite checks database behavior that SQLite cannot
represent: fresh and repeated schema initialization, migration of a legacy
`chunks` table, vector dimensions and cosine ordering (including ties), and
document/section filters. Fixtures are synthetic; the suite does not call Ollama
or download Hugging Face models.

It also verifies unknown/mismatched index profiles, unique chunk locations,
non-destructive duplicate detection during migration, and concurrent replacement
and removal through the application indexer. Request-owned question vectors are
checked across repeated scopes, including changed provenance after caching.
An invalid later embedding batch must preserve the saved chunks and provenance.
Synthetic files use stub extraction
and embedding; transaction locking and database writes are real PostgreSQL.

The suite is opt-in. Without `RAG_TEST_POSTGRES_URL`, its tests skip. The URL is
the **controller database** used only to create and drop a uniquely named
`rag_contract_<uuid>` database for each test. The controller database itself is
not modified. The test role needs `CREATEDB` and permission to install the
pgvector `vector` extension in each test database. Keep `RAG_DATABASE_URL` set to
SQLite so importing the application cannot point its default engine at the test
server.

For a local run, start an isolated pgvector container on an unused loopback port.
This example generates a throwaway password, uses no host or named volume, waits
for PostgreSQL to become ready, and removes only the named container and its
anonymous volume when the shell exits:

```bash
(
set -e
RAG_CONTRACT_CONTAINER="rag-contract-pg-$$"
RAG_CONTRACT_PASSWORD="$(openssl rand -hex 24)"
docker run --detach --name "$RAG_CONTRACT_CONTAINER" \
  --publish 127.0.0.1:55433:5432 \
  --env POSTGRES_USER=rag \
  --env POSTGRES_PASSWORD="$RAG_CONTRACT_PASSWORD" \
  --env POSTGRES_DB=postgres \
  --health-cmd='pg_isready -U rag -d postgres' \
  --health-interval=1s --health-timeout=3s --health-retries=30 \
  pgvector/pgvector:pg17
cleanup() {
  docker rm --force --volumes "$RAG_CONTRACT_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT
attempt=0
until [ "$(docker inspect --format='{{.State.Health.Status}}' "$RAG_CONTRACT_CONTAINER")" = healthy ]; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then
    docker logs "$RAG_CONTRACT_CONTAINER"
    exit 1
  fi
  sleep 1
done

RAG_TEST_POSTGRES_URL="postgresql+psycopg://rag:${RAG_CONTRACT_PASSWORD}@127.0.0.1:55433/postgres" \
RAG_DATABASE_URL=sqlite:///:memory: \
uv run --locked python -m unittest discover -s tests/integration -v
)
```

Choose another unused local port if `55433` is occupied. The commands do not
source `.env`; the random password is passed only to this disposable container
and test process. Do not point the controller URL at a personal or shared
database: the suite creates and drops test databases there.

CI runs these contracts in a separate Ubuntu job against a disposable
`pgvector/pgvector` service with a locked, pruned dependency set that omits
`sentence-transformers` and Uvicorn. PyMuPDF is retained for importing the indexer.
This job validates PostgreSQL
contracts only and does not claim that the full application supports Linux.
