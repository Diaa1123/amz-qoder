# AMZ_Designy - Architecture Document

## 1. System Overview

AMZ_Designy is a backend-only multi-agent AI system that automates the Amazon Merch-on-Demand design pipeline. The system discovers trending niches, generates strategic design briefs, creates design prompts via AI, validates outputs, and publishes to Airtable for human review. All interaction is through Poe bot commands.

### Data Flow

```
┌──────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────────────────┐
│ TrendScout   │───▶│ NicheAnalyzer    │───▶│  Strategist     │───▶│  Designer    │───▶│  Inspector   │───▶│ AirtableExporter +    │
│ Agent        │    │ Agent (weekly)   │    │  Agent          │    │  Agent       │    │  Agent       │    │ OutputWriter          │
└──────────────┘    └──────────────────┘    └─────────────────┘    └──────────────┘    └──────────────┘    └───────────────────────┘
      │                    │                       │                      │                   │
   pytrends            pytrends +              LLM (Poe)             LLM (Poe)        Rule-based scan
   Google Trends       LLM analysis            GPT-4/Claude         Prompt + Rules    + LLM rewrite
```

### Core Pipeline Stages

| Stage | Agent | Input | Output | External APIs |
|-------|-------|-------|--------|---------------|
| 1. Trend Discovery | `TrendScoutAgent` | Keywords, Categories | Trending queries, Rising topics | pytrends |
| 2. Niche Analysis | `NicheAnalyzerAgent` (weekly) | Raw trends | Scored niches with competition analysis | pytrends, LLM |
| 3. Strategy | `StrategistAgent` | High-score niche | Title, bullets, description, keywords, design brief | LLM (Poe) |
| 4. Design | `DesignerAgent` | Design brief | Design prompts + print-ready rules | LLM (Poe) |
| 5. Inspection | `InspectorAgent` | IdeaPackage + DesignPrompt | Rule-based scan + LLM rewrite (vision optional future) | LLM (Poe) |
| 6. Publishing | `AirtableExporter` + `OutputWriter` | Approved IdeaPackage + ComplianceReport | Airtable record + local output package | Airtable API, filesystem |

---

## 2. Orchestrator Entrypoints

### 2.1 CLI (`main.py`) - Dev/Testing Only

```python
# For local development and testing only. Not used in production.
python main.py --mode daily           # Run daily pipeline
python main.py --mode weekly          # Run full weekly pipeline
python main.py --mode create <kw>     # Create design package for keyword
```

### 2.2 Poe Bot Commands (Production)

All production interaction is through a Poe bot (`poe_bot.py` via `fastapi-poe`).

| Command | Description |
|---------|-------------|
| `/daily` | Run daily trend discovery pipeline (TrendScoutAgent + NicheAnalyzerAgent) |
| `/weekly` | Run full weekly pipeline (all 5 agents, end-to-end) |
| `/create <keyword>` | Manually trigger design package creation for a specific keyword/niche |
| `/help` | Show available commands and system status |

```python
# poe_bot.py - fastapi-poe bot
# Handles all 4 commands above.
# Each command triggers the orchestrator with the appropriate pipeline mode.
```

---

## 3. Agent Boundaries and Responsibilities

### 3.1 TrendScoutAgent

**Responsibility**: Discover trending search queries from Google Trends.

**Inputs**:
- `seed_keywords: list[str]` - Starting keywords for exploration
- `geo: str` - Geographic region (default: `"US"`)
- `timeframe: str` - Time window (default: `"today 1-m"`)

**Outputs**:
- `TrendReport` - List of trending queries with volume and growth data

**External Calls**:
- `pytrends.trending_searches()`
- `pytrends.related_queries()`
- `pytrends.interest_over_time()`

**Error Handling**:
- Rate limit: Exponential backoff (max 5 retries)
- Empty results: Log warning, return empty list
- Timeout: Retry with increased timeout

---

### 3.2 NicheAnalyzerAgent

**Responsibility**: Score and filter trends for Merch viability using deterministic scoring rules.

**Inputs**:
- `trend_report: TrendReport`
- `min_score: float` - Minimum viability threshold

**Outputs**:
- `NicheReport` - Scored niches with opportunity analysis

**Scoring Criteria** (rule-based, primary):

All scores are computed from data signals (search volume, growth rate, competition proxies, category metadata). The scoring formula is deterministic and does not depend on LLM output.

- Commercial intent (1-10)
- Designability (1-10)
- Audience size (1-10)
- Competition level (1-10, lower is better)
- Seasonality risk (1-10, lower is better)
- Trademark risk (1-10, lower is better)

**Optional LLM summary** (secondary):

After scoring, the agent may optionally call an LLM to generate a human-readable `analysis_summary` for each niche. This summary is informational only and does not influence the score or ranking.

**External Calls**:
- pytrends for trend depth data (primary)
- LLM for optional analysis summary (secondary, not used for scoring)

---

### 3.3 StrategistAgent

**Responsibility**: Create comprehensive listing content and design briefs.

**Inputs**:
- `niche_report: NicheReport` - High-scoring niche
- `brand_voice: str` - Tone/style guidelines

**Outputs**:
- `IdeaPackage` containing:
  - Final approved title
  - Final approved bullet points
  - Final approved description
  - Final approved keywords/tags
  - Target audience
  - Design style direction

**External Calls**:
- LLM (Poe GPT-4/Claude) with structured JSON output

---

### 3.4 DesignerAgent

**Responsibility**: Generate a design prompt and style metadata for image generation.

**Inputs**:
- `idea_package: IdeaPackage`

**Outputs**:
- `DesignPrompt` containing:
  - The image generation prompt text
  - Design style reference
  - Color/mood notes

**External Calls**:
- LLM (Poe) to craft the design prompt

**Note**: Actual image generation (DALL-E / SDXL) is triggered from the prompt but final rendering is a separate downstream step.

---

### 3.5 InspectorAgent

**Responsibility**: Validate idea packages and design prompts against Amazon Merch policies using text-based checks.

**Inputs**:
- `idea_package: IdeaPackage`
- `design_prompt: DesignPrompt`

**Outputs**:
- `ComplianceReport`:
  - `compliance_status: str` (approved / rejected / needs_review)
    - **approved**: Passed all checks, safe to publish.
    - **rejected**: Failed one or more checks, must not publish.
    - **needs_review**: Ambiguous result requiring human judgment.
  - `compliance_notes: str`
  - `risk_terms_detected: list[str]`

**Validation Checks**:
1. **Policy Compliance** (LLM + keyword rules):
   - No hate speech, violence, adult content
   - No copyrighted/trademarked material
   - No personal information
   - No misleading claims

2. **Prompt Validation**:
   - Design prompt does not reference banned content
   - Prompt aligns with the approved idea package

3. **Text Content Validation**:
   - Title, bullets, description free of risk terms
   - Keywords/tags appropriate for Amazon

**External Calls**:
- LLM (Poe) for text-based compliance analysis

**Note**: Image vision validation is planned for the future and is not in the current scope. The Inspector focuses on text and prompt validation only.

---

## 4. Data Contracts (Pydantic Schemas)

### 4.1 Core Contracts

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date

# --- TrendReport ---
class TrendEntry(BaseModel):
    query: str
    volume: Optional[int] = None
    growth_rate: Optional[float] = None
    category: Optional[str] = None
    source: str = "google_trends"

class TrendReport(BaseModel):
    entries: list[TrendEntry]
    geo: str = "US"
    timeframe: str = "today 1-m"
    created_at: datetime

# --- NicheReport ---
class NicheScore(BaseModel):
    commercial_intent: int = Field(ge=1, le=10)
    designability: int = Field(ge=1, le=10)
    audience_size: int = Field(ge=1, le=10)
    competition_level: int = Field(ge=1, le=10)
    seasonality_risk: int = Field(ge=1, le=10)
    trademark_risk: int = Field(ge=1, le=10)

    @property
    def opportunity_score(self) -> float:
        weights = [0.2, 0.25, 0.2, 0.15, 0.1, 0.1]
        scores = [
            self.commercial_intent, self.designability,
            self.audience_size, 11 - self.competition_level,
            11 - self.seasonality_risk, 11 - self.trademark_risk,
        ]
        return round(sum(w * s for w, s in zip(weights, scores)), 2)

class NicheEntry(BaseModel):
    niche_name: str
    trending_query: str
    score: NicheScore
    audience: str
    analysis_summary: str

class NicheReport(BaseModel):
    entries: list[NicheEntry]
    created_at: datetime

# --- IdeaPackage ---
class IdeaPackage(BaseModel):
    niche_name: str
    audience: str
    opportunity_score: float
    final_approved_title: str
    final_approved_bullet_points: list[str]
    final_approved_description: str
    final_approved_keywords_tags: list[str]
    design_style: str
    created_at: datetime

# --- DesignPrompt ---
class DesignPrompt(BaseModel):
    idea_niche_name: str
    prompt_text: str
    design_style: str
    color_mood_notes: Optional[str] = None
    created_at: datetime

# --- ComplianceReport ---
class ComplianceReport(BaseModel):
    idea_niche_name: str
    compliance_status: str  # "approved" | "rejected" | "needs_review"
    # Primary statuses: "approved" (passed all checks) or "rejected" (failed checks).
    # "needs_review" is used when the result is ambiguous and requires human judgment.
    compliance_notes: str
    risk_terms_detected: list[str] = Field(default_factory=list)
    created_at: datetime
```

### 4.2 Configuration Schema

```python
from pydantic import SecretStr
from pathlib import Path
from datetime import time

class AppConfig(BaseModel):
    # API Keys
    poe_access_key: SecretStr
    airtable_api_key: SecretStr
    airtable_base_id: str

    # LLM Settings
    llm_model: str = "gpt-4o"
    image_model: str = "dall-e-3"
    max_tokens: int = 4000
    temperature: float = 0.7

    # Pipeline Settings
    min_niche_score: float = 6.5
    max_designs_per_run: int = 10
    auto_publish: bool = False

    # Storage
    output_dir: Path = Path("./outputs")

    # Scheduler
    daily_run_time: time = time(hour=9, minute=0)
    weekly_full_run_day: int = 0  # Monday
    timezone: str = "Asia/Riyadh"

    # Monitoring
    log_level: str = "INFO"
```

---

## 5. Error Handling Strategy

### 5.1 pytrends / Google Trends

```python
class TrendsRateLimitError(Exception):
    """Hit rate limit - exponential backoff"""
    pass

class TrendsEmptyResultError(Exception):
    """No data returned - log and continue"""
    pass

# Strategy:
# 1. Max 5 retries with exponential backoff (1s, 2s, 4s, 8s, 16s)
# 2. Cache results to minimize repeated calls
# 3. Fallback to cached data if fresh data unavailable
```

### 5.2 Airtable API

```python
class AirtableRateLimitError(Exception):
    """429 Too Many Requests"""
    pass

class AirtableAuthError(Exception):
    """401/403 Authentication failed"""
    pass

class AirtableValidationError(Exception):
    """422 Validation failed - log and alert"""
    pass

# Strategy:
# 1. Batch writes (max 10 records per request)
# 2. Exponential backoff for rate limits
# 3. Queue failed writes for retry
# 4. Local backup of all data before Airtable write
```

### 5.3 LLM / Poe API

```python
class LLMRateLimitError(Exception):
    """Rate limited - queue and retry"""
    pass

class LLMStructuredOutputError(Exception):
    """Failed to parse structured output - retry with stricter prompt"""
    pass

class LLMContentPolicyError(Exception):
    """Content flagged - log and skip"""
    pass

# Strategy:
# 1. Retry with simplified prompt on parse failure
# 2. Structured output validation with Pydantic
# 3. Fallback models: GPT-4 -> Claude
# 4. Queue and alert on persistent failures
```

---

## 6. Scheduler Design

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

class PipelineScheduler:
    def __init__(self, config: AppConfig):
        self.scheduler = AsyncIOScheduler(timezone="Asia/Riyadh")
        self.config = config

    def setup_jobs(self):
        # Daily: trend discovery + niche scoring
        self.scheduler.add_job(
            self.daily_pipeline,
            CronTrigger(hour=9, minute=0),
            id="daily_pipeline",
            replace_existing=True,
            misfire_grace_time=3600,
        )

        # Weekly: full end-to-end pipeline (all 5 agents)
        self.scheduler.add_job(
            self.weekly_pipeline,
            CronTrigger(day_of_week="mon", hour=10, minute=0),
            id="weekly_pipeline",
            replace_existing=True,
            misfire_grace_time=7200,
        )

    async def daily_pipeline(self):
        """Run TrendScoutAgent + NicheAnalyzerAgent.
        Store results to Airtable Weekly Niche table."""
        pass

    async def weekly_pipeline(self):
        """Full pipeline:
        TrendScout -> NicheAnalyzer -> Strategist -> Designer -> Inspector -> Airtable Ideas."""
        pass
```

---

## 7. Airtable Schema

### 7.1 Ideas Table

| Field | Type | Description |
|-------|------|-------------|
| Date | Date | Creation / discovery date |
| Trend Name | Single line text | Original trending query |
| Niche Name | Single line text | Refined niche name |
| Audience | Single line text | Target audience description |
| Opportunity Score | Number | Computed viability score |
| Final Approved Title | Single line text | Listing title |
| Final Approved Bullet Points | Long text | Listing bullet points |
| Final Approved Description | Long text | Listing description |
| Final Approved Keywords/Tags | Long text | SEO keywords / tags |
| Design Prompt | Long text | Image generation prompt |
| Compliance Status | Single select | approved / rejected / needs_review |
| Compliance Notes | Long text | Inspector notes |
| Risk Terms Detected | Long text | Flagged risk terms (comma-separated) |
| Design Style | Single line text | Style direction for the design |
| Status | Single select | draft / ready / published / rejected |

### 7.2 Weekly Niche Table

| Field | Type | Description |
|-------|------|-------------|
| Niche Name | Single line text | Name of the niche |
| Week Start Date | Date | Start of the tracking week |
| Weekly Growth % | Number | Week-over-week growth percentage |
| Rising Status | Single select | rising / stable / declining |
| Opportunity Score | Number | Computed viability score |
| Notes | Long text | Additional analysis notes |

---

## 8. Local Output Package

The `OutputWriter` writes a structured folder for each approved concept. All pipeline artifacts are persisted locally before (and independently of) the Airtable upload.

### Folder Path

```
outputs/YYYY-MM-DD/trend_name/concept_01/
```

- `YYYY-MM-DD` - Pipeline run date.
- `trend_name` - Slugified original trending query (lowercase, hyphens, no spaces).
- `concept_01` - Zero-padded concept index within the trend (concept_01, concept_02, ...).

### Required Files

| File | Content |
|------|---------|
| `trend_report.json` | Serialized `TrendReport` for this run |
| `niche_report.json` | Serialized `NicheReport` with scores |
| `idea_package.json` | Serialized `IdeaPackage` (title, bullets, description, keywords, audience, style) |
| `design_prompt.json` | Serialized `DesignPrompt` (prompt text, style, color/mood notes) |
| `listing.txt` | Plain-text listing content: title, bullet points, description (human-readable) |
| `keywords.txt` | One keyword/tag per line |
| `compliance_report.json` | Serialized `ComplianceReport` (status, notes, risk terms) |
| `final_summary.txt` | Human-readable summary of the full pipeline result for this concept |

---

## 9. Deployment Notes

### 9.1 FastAPI + fastapi-poe Setup

```python
# main.py
from fastapi import FastAPI
from fastapi_poe import PoeBot
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_scheduler()
    yield
    await shutdown_scheduler()

app = FastAPI(title="AMZ_Designy", lifespan=lifespan)

poe_bot = DesignyPoeBot()
app.post("/poe/webhook")(poe_bot.get_endpoint())
```

### 9.2 Railway Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p outputs logs
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${PORT:-8000}"]
```

### 9.3 Environment Variables

```bash
# .env.template
# Required
POE_ACCESS_KEY=
AIRTABLE_API_KEY=
AIRTABLE_BASE_ID=

# LLM
LLM_MODEL=gpt-4o
IMAGE_MODEL=dall-e-3
MAX_DESIGNS_PER_RUN=10
MIN_NICHE_SCORE=6.5

# Scheduler
DAILY_RUN_HOUR=9
WEEKLY_RUN_DAY=0
TIMEZONE=Asia/Riyadh

# Monitoring
LOG_LEVEL=INFO

# Storage
OUTPUT_DIR=./outputs
```

---

## 10. Testing Suggestions

### 10.1 Unit Test Priority

```
Priority 1 - Core Business Logic:
├── tests/test_niche_scoring.py       # NicheScore.opportunity_score
├── tests/test_idea_package.py        # IdeaPackage validation
├── tests/test_compliance_rules.py    # Risk term detection, policy checks
└── tests/test_design_prompt.py       # Prompt construction

Priority 2 - External API Adapters:
├── tests/test_trends_adapter.py      # pytrends wrapper with mocks
├── tests/test_airtable_adapter.py    # Airtable client with mocks
└── tests/test_llm_adapter.py         # Poe client with mocks

Priority 3 - Integration:
├── tests/test_pipeline.py            # Full pipeline with mocked externals
└── tests/test_poe_bot.py             # Poe bot command handling
```

### 10.2 Test Fixtures

```python
# tests/conftest.py
import pytest
from datetime import datetime

@pytest.fixture
def sample_trend_report():
    return TrendReport(
        entries=[
            TrendEntry(query="funny cat shirts", volume=100000, growth_rate=35.0),
            TrendEntry(query="vintage gaming tees", volume=50000, growth_rate=20.0),
        ],
        geo="US",
        timeframe="today 1-m",
        created_at=datetime.now(),
    )

@pytest.fixture
def sample_idea_package():
    return IdeaPackage(
        niche_name="Funny Cat Shirts",
        audience="Cat lovers aged 18-35",
        opportunity_score=8.2,
        final_approved_title="Purrfectly Hilarious Cat Tee",
        final_approved_bullet_points=["Funny cat design", "Soft cotton blend"],
        final_approved_description="A hilarious cat-themed t-shirt for feline fans.",
        final_approved_keywords_tags=["cat", "funny", "t-shirt", "cat lover"],
        design_style="cartoon, bright colors",
        created_at=datetime.now(),
    )
```

---

## 11. Project Structure

```
AMZ_Designy/
├── src/
│   ├── __init__.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                # BaseAgent abstract class
│   │   ├── trend_scout.py         # TrendScoutAgent
│   │   ├── niche_analyzer.py      # NicheAnalyzerAgent
│   │   ├── strategist.py          # StrategistAgent
│   │   ├── designer.py            # DesignerAgent
│   │   └── inspector.py           # InspectorAgent
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── trend_report.py        # TrendReport, TrendEntry
│   │   ├── niche_report.py        # NicheReport, NicheEntry, NicheScore
│   │   ├── idea_package.py        # IdeaPackage
│   │   ├── design_prompt.py       # DesignPrompt
│   │   ├── compliance_report.py   # ComplianceReport
│   │   └── config.py              # AppConfig
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── pytrends_adapter.py    # Google Trends wrapper
│   │   ├── airtable_adapter.py    # Airtable API wrapper
│   │   └── poe_adapter.py         # Poe LLM wrapper
│   ├── errors/
│   │   ├── __init__.py
│   │   ├── trends_errors.py
│   │   ├── airtable_errors.py
│   │   └── llm_errors.py
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── jobs.py
│   ├── orchestrator.py            # Pipeline orchestration
│   └── config.py                  # Settings management
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── outputs/                       # Generated data (gitignored)
├── logs/                          # Application logs
├── main.py                        # FastAPI + Poe bot entrypoint
├── poe_bot.py                     # Poe bot command handlers
├── Dockerfile
├── railway.yaml
├── requirements.txt
├── pyproject.toml
└── ARCHITECTURE.md                # This document
```
