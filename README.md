# AMZ_Designy

Backend-only multi-agent AI system for Amazon Merch-on-Demand design pipeline.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

## Usage

### CLI (dev/testing)

```bash
python -m app.cli --mode daily
python -m app.cli --mode weekly
python -m app.cli --mode create --keyword "funny cat shirts"
```

### Production (Poe bot)

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Poe commands: `/daily`, `/weekly`, `/create <keyword>`, `/help`

## Deployment (Railway)

```bash
docker build -t amz-designy .
docker run -p 8000:8000 --env-file .env amz-designy
```

## Tests

```bash
pytest tests/ -v
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for full system design.
