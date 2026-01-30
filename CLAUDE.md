# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Email Agent (邮件日报) - A local application that fetches Gmail emails via OAuth, generates daily email reports using GPT, and displays them in a local web interface to reduce manual email checking.

**Tech Stack**: FastAPI backend, Gmail API (OAuth 2.0), OpenAI API (GPT), SQLite + SQLAlchemy, Jinja2 templates (MVP), optional React/Vite for future frontend.

**Language**: Documentation is primarily in Chinese. Code should follow English naming conventions.

## Architecture

The application follows a modular pipeline architecture:

```
User → Web UI → FastAPI → Gmail API → Preprocess → OpenAI GPT → Report Assembly → SQLite → Web UI
```

### Core Module Boundaries

- **FastAPI**: Routes, auth middleware, request/response models
- **Gmail Integration** (`app/integrations/gmail/`): OAuth flow, message/thread fetching, header/snippet parsing
- **Preprocess** (`app/core/`, `app/services/`): Deduplication, thread merging, plain text extraction, unified data structures
- **OpenAI** (`app/integrations/openai/`): Prompt construction, GPT API calls, structured JSON output parsing
- **ReportAssembler** (`app/services/`): Combines GPT output with email references into report entities
- **SQLite** (`app/db/`): Persists reports and email metadata/summaries (not full email bodies by default)
- **Web UI** (`app/web/`): Consumes APIs and templates only, doesn't directly access Gmail/OpenAI

### Directory Structure

```
app/
  main.py              # Entry point and route mounting
  web/                 # Jinja2 templates and static resources
  integrations/
    gmail/             # OAuth, fetching, parsing
    openai/            # Prompts, API calls, retry logic
  core/                # Config, logging, time ranges, deduplication
  db/                  # Models, migrations (optional), DAOs
  services/            # Report generation pipeline
scripts/               # CLI scripts (generate daily report, backfill history)
data/                  # Local data (tokens, db, export files) - gitignored
```

## Configuration

### Environment Variables (`.env`)

- `OPENAI_API_KEY`: OpenAI API key (required)
- `OPENAI_MODEL`: Model name, defaults to `gpt-4o-mini`
- `APP_BASE_URL`: Local callback base URL, e.g., `http://127.0.0.1:8000`

### Google OAuth Setup

1. Create OAuth 2.0 client in [Google Cloud Console](https://console.cloud.google.com/) (Desktop or Web application)
2. Download `credentials.json` and place in project root or `data/` directory
3. Configure redirect URI: `http://127.0.0.1:<port>/auth/google/callback` (must match FastAPI port)
4. Scope required: `gmail.readonly`

## Development Commands

**Setup**:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**Run FastAPI Server**:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Generate Daily Report (CLI)**:
```bash
.venv\Scripts\python.exe scripts\generate_daily_report.py
```

**Scheduled Task**: Use Windows Task Scheduler to run the CLI script at specified times daily.

## Skills-Based Architecture

Each "Skill" is an independently testable module with clear input/output and error handling:

### SkillGmailAuth (`app/integrations/gmail/auth.py`)
- OAuth flow initiation, token refresh, permission checks
- Input: None (first time) or existing refresh token
- Output: Valid `Credentials` or redirect URL
- Error: `AuthError` on token expiry (auto-refresh); clear error codes guide re-authorization

### SkillGmailFetch (`app/integrations/gmail/fetch.py`)
- Fetch message/thread metadata and snippets by time range and filters
- Input: `date_from`, `date_to` (or "last 24h"), optional filters (unread/starred/sender/keywords)
- Output: `List[MessageSummary]` (id, thread_id, subject, from, date, snippet, labels)
- Error: Rate limiting (429) triggers backoff retry; network errors distinguished as retriable/non-retriable

### SkillEmailNormalize (`app/integrations/gmail/normalize.py`)
- Parse MIME/HTML to plain text, normalize field structure, optional language detection
- Input: Raw message or body/snippet
- Output: `NormalizedEmail` (subject, from, to, date_utc, body_plain, snippet, lang)
- Error: Parse failures fall back to snippet; log parse errors without breaking pipeline

### SkillThreadMerge (`app/services/thread_merge.py`)
- Aggregate by thread_id, deduplicate, extract context window for GPT
- Input: `List[NormalizedEmail]`
- Output: `List[ThreadContext]` (thread_id, subject, messages_ordered, combined_text with length limit)
- Error: Truncate oversized threads and mark them to avoid token limit issues

### SkillImportanceHeuristics (`app/services/importance.py`)
- Rule-based scoring (unread, starred, specific domains, keywords) for sorting/filtering
- Input: `NormalizedEmail` or `MessageSummary`; optional rule config
- Output: `importance_score` or `priority_label`
- Error: Malformed rules fall back to default weights with warning log

### SkillPromptCompose (`app/integrations/openai/prompts.py`)
- Generate stable system/user prompts from email collection
- Input: `List[ThreadContext]` or normalized emails; optional categorization/format preferences
- Output: `system_prompt`, `user_prompt` (string or message list)
- Error: Empty input returns "no emails today" placeholder without calling GPT

### SkillGptSummarize (`app/integrations/openai/summarize.py`)
- Call OpenAI API with retry/rate limiting/timeout; return structured JSON output
- Input: `system_prompt`, `user_prompt`; optional `response_format` (JSON schema)
- Output: Parsed report structure (category lists, to-dos, daily highlights)
- Error: 429/5xx retry; timeout and invalid JSON logged with clear error types; no keys/tokens in logs

### SkillReportStore (`app/db/report_store.py`)
- Save reports, link email references, query history by date
- Input: `Report` entity + `List[EmailReference]`
- Output: `report_id`; query methods return `Report` or list
- Error: DB unavailable returns friendly error; write conflicts handled idempotently or via versioning

### SkillExport (`app/services/export.py`)
- Export reports as Markdown or HTML
- Input: `Report` or `report_id`; format `md`/`html`
- Output: File path or byte stream
- Error: Report not found returns 404; missing template logs error and returns generic message

### SkillScheduler (Documentation + CLI script)
- Trigger daily report generation at fixed time (MVP: Windows Task Scheduler)
- Input: Time config (e.g., daily at 08:00); optional environment/working directory
- Output: Side effect (generate and store report)
- Error: Script catches exceptions, writes logs, exits with non-zero code for alert

## Report Generation Pipeline

Main pipeline function (`app/services/report_pipeline.py`):
```python
generate_report_for_date(date, credentials)
```

Flow:
1. GmailFetch (date range) → Normalize → ThreadMerge → Importance (sort/filter)
2. PromptCompose → GptSummarize → Assemble Report + EmailReference
3. ReportStore.save_report

Error handling: Categorize as retriable (network) vs non-retriable (permissions); propagate or return Result type.

## Data Storage

- **Default**: Only save report and email metadata/summaries (no full bodies)
- **Optional**: Configurable switch to store full email bodies
- **Security**: No API keys, OAuth tokens in logs; consider future data sanitization before OpenAI calls

## Implementation Plan

The project follows a 15-step incremental implementation plan (see `docs/IMPLEMENTATION_PLAN.md`):

**Phase 1 (Steps 1-3)**: Scaffold, config/logging, storage layer
**Phase 2 (Steps 4-5)**: Gmail OAuth and fetch
**Phase 3 (Steps 6-8)**: Email normalization, thread merging, importance scoring
**Phase 4 (Steps 9-10)**: OpenAI integration and report pipeline
**Phase 5 (Steps 11-13)**: FastAPI routes, Web UI (Jinja2), export
**Phase 6 (Steps 14-15)**: CLI scripts, scheduled tasks, documentation polish

Each step has clear deliverables and acceptance criteria. Implement sequentially to minimize rework.

## MVP Scope (First Version)

**In Scope**:
- Gmail OAuth login (read-only permissions)
- Fetch emails from last 24 hours or specified date
- GPT summarization with categorization (action needed / important / billing / social / other)
- Per-email/thread: one-sentence summary + action required + suggested next step
- Overall daily report: 3-7 key highlights + to-do list
- Local SQLite storage with history query
- Web UI to view reports, expand email references, export (Markdown or HTML)

**Out of Scope (First Version)**:
- Reply/send automation
- Multi-account/multi-team permissions
- Mobile app

## Common Issues

- **Authorization failures**: Delete local token file and re-authorize via web; confirm `credentials.json` and redirect URI match running port
- **OpenAI timeout/rate limits**: Check network and API quota; built-in retry/backoff can be tuned
- **Empty reports**: Verify time range and filter conditions; check Gmail API permissions include `gmail.readonly`
- **Export failures**: Confirm report generated and written to SQLite; check server logs for template/path errors
