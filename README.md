::: {align="center"}
# 🛰️ Digital Footprint Tracer

### Discover identities · Correlate evidence · Investigate public footprints

![Release](https://img.shields.io/badge/release-v1.0.0-22c55e?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-TypeScript-3178C6?style=for-the-badge&logo=react&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)

`GitHub` · `Steam` · `Twitch` · `Stack Exchange`
:::

> 🔎 **A matching name is evidence --- not proof of identity.**

### ⚡ What DFT does

  -----------------------------------------------------------------------
  Stage                               Purpose
  ----------------------------------- -----------------------------------
  🔍 **Discover**                     Find public identity candidates

  🧩 **Correlate**                    Score reusable cross-provider
                                      identity signals

  ✅ **Verify**                       Keep ambiguous matches
                                      operator-confirmed

  🛰️ **Investigate**                  Execute provider-native public-data
                                      capabilities

  📦 **Report**                       Export linked identities and
                                      observations as JSON
  -----------------------------------------------------------------------

------------------------------------------------------------------------

> A provider-aware public identity discovery, cross-platform
> correlation, and digital-footprint investigation system.

Digital Footprint Tracer (DFT) is a full-stack OSINT-oriented
application for discovering public identities, correlating profiles
across multiple platforms, executing provider-specific public-data
capabilities, and producing structured investigation reports.

> **A matching name is evidence --- not proof of identity.**

Instead of blindly assuming that similarly named accounts belong to the
same person, DFT separates **discovery**, **correlation**, **operator
confirmation**, and **provider-native investigation** into distinct
stages.

------------------------------------------------------------------------

## Current Release

**Version:** `v1.0.0`

### Supported Providers

  Provider                               Discovery   Native Identifier Resolution   Investigation
  ---------------- ------------------------------- ------------------------------ ---------------
  GitHub                                        ✅                             ✅              ✅
  Steam              Limited / identifier-oriented                             ✅              ✅
  Twitch                                        ✅                             ✅              ✅
  Stack Exchange                                ✅                             ✅              ✅

DFT is designed so additional providers can be added through
provider-specific discovery adapters and capability implementations.

------------------------------------------------------------------------

## Table of Contents

-   [Overview](#overview)
-   [Why This Project Exists](#why-this-project-exists)
-   [Core Architecture](#core-architecture)
-   [Investigation Workflow](#investigation-workflow)
-   [Identity Discovery](#identity-discovery)
-   [Cross-Provider Correlation](#cross-provider-correlation)
-   [Conditional Search Behaviour](#conditional-search-behaviour)
-   [Provider Identity Resolution](#provider-identity-resolution)
-   [Supported Inputs](#supported-inputs)
-   [Provider Capabilities](#provider-capabilities)
-   [Investigation Reports](#investigation-reports)
-   [Tech Stack](#tech-stack)
-   [Project Structure](#project-structure)
-   [Installation](#installation)
-   [Environment Configuration](#environment-configuration)
-   [Docker Infrastructure](#docker-infrastructure)
-   [Running the Backend](#running-the-backend)
-   [Running Celery](#running-celery)
-   [Running the Frontend](#running-the-frontend)
-   [Production Build Check](#production-build-check)
-   [API Architecture](#api-architecture)
-   [Adding a New Provider](#adding-a-new-provider)
-   [Correlation Philosophy](#correlation-philosophy)
-   [Why DFT Does Not Use ML Yet](#why-dft-does-not-use-ml-yet)
-   [Known Limitations](#known-limitations)
-   [Privacy and Responsible Use](#privacy-and-responsible-use)
-   [Security](#security)
-   [Troubleshooting](#troubleshooting)
-   [Release Checklist](#release-checklist)
-   [Roadmap](#roadmap)
-   [Future SaaS Direction](#future-saas-direction)
-   [Design Principles](#design-principles)
-   [Disclaimer](#disclaimer)
-   [Contributing](#contributing)
-   [License](#license)

------------------------------------------------------------------------

## 🎯 Overview

A traditional username lookup asks:

> "Does this username exist on another website?"

DFT attempts to solve a broader problem:

> "Given a public identity, what other provider-specific identities may
> correspond to the same subject, how strong is the evidence connecting
> them, and what public information can be retrieved from verified
> identities?"

The system operates at multiple levels:

``` text
Human Query
    ↓
Public Identity Discovery
    ↓
Candidate Ranking
    ↓
Operator Selects Anchor Identity
    ↓
Cross-Provider Signal Expansion
    ↓
Candidate Correlation
    ↓
Provider Identity Confirmation
    ↓
Capability Execution
    ↓
Public Observations
    ↓
Structured Investigation Report
```

------------------------------------------------------------------------

## Why This Project Exists

Public identity investigation becomes difficult when the same person
uses:

-   different usernames across platforms
-   abbreviated or modified names
-   platform-specific identifiers
-   vanity URLs
-   numeric account IDs
-   unrelated handles
-   multiple accounts with identical display names

A simple exact-string search cannot reliably solve this problem.

At the same time, automatically declaring two profiles to be the same
person based only on a name match creates dangerous false positives.

DFT addresses this by separating the problem into four layers:

1.  **Discovery** --- find plausible public identities.
2.  **Correlation** --- measure how strongly discovered candidates
    resemble the selected anchor identity.
3.  **Verification** --- automatically link only sufficiently strong
    identities and require operator confirmation when evidence is
    ambiguous.
4.  **Investigation** --- execute provider-native capabilities only
    against resolved identities.

------------------------------------------------------------------------

## 🏗️ Core Architecture

``` mermaid
flowchart TD
    A[User Query] --> B[Discovery Engine]

    B --> C1[GitHub Discovery Adapter]
    B --> C2[Steam Discovery Adapter]
    B --> C3[Twitch Discovery Adapter]
    B --> C4[Stack Exchange Discovery Adapter]

    C1 --> D[Candidate Pool]
    C2 --> D
    C3 --> D
    C4 --> D

    D --> E[Scoring and Ranking]
    E --> F[Operator Selects Anchor Identity]

    F --> G[Subject]
    G --> H[Signal Expansion]

    H --> I[Cross-Provider Discovery]
    I --> J[Identity Correlator]

    J --> K1[Verified Identity]
    J --> K2[Possible Match]
    J --> K3[Unresolved Provider]

    K2 --> L[Operator Confirmation]
    K3 --> M[Manual Provider-Native Fallback]

    K1 --> N[Subject Identities]
    L --> N
    M --> N

    N --> O[Capability Executor]

    O --> P1[GitHub Provider]
    O --> P2[Steam Provider]
    O --> P3[Twitch Provider]
    O --> P4[Stack Exchange Provider]

    P1 --> Q[Observations]
    P2 --> Q
    P3 --> Q
    P4 --> Q

    Q --> R[Investigation Report]
```

------------------------------------------------------------------------

## 🔄 Investigation Workflow

### Step 1 --- Search

The operator enters a public name or identifier.

``` text
Shreyash Singh
```

The discovery layer searches supported public providers.

### Step 2 --- Candidate Selection

DFT returns ranked candidates rather than silently choosing one.

A candidate can contain:

``` text
provider
provider_user_id
username
display_name
profile_url
confidence
match_type
reasons
identifiers
public metadata
```

The operator selects the identity that should become the investigation
anchor.

### Step 3 --- Subject Creation

The selected identity becomes a logical `Subject`.

``` text
Subject
│
├── GitHub Identity
├── Steam Identity
├── Twitch Identity
└── Stack Exchange Identity
```

A person is **not** equivalent to a GitHub username or SteamID.

### Step 4 --- Automatic Correlation

DFT extracts reusable public signals from the anchor.

``` text
Shreyash Singh
shreyashsingh
singhshreyash75-eng
```

These signals are passed through public discovery adapters. Results are
deduplicated and scored against the anchor.

### Step 5 --- Resolve Ambiguity

Possible outcomes:

-   **Verified** --- sufficient evidence exists or the identity has been
    explicitly verified.
-   **Possible** --- candidates exist, but evidence is insufficient for
    automatic linking. Operator confirmation is required.
-   **Unresolved** --- no reliable candidate was discovered. A known
    provider-native identifier may be supplied as a fallback.

### Step 6 --- Investigation

Only resolved provider identities are used for provider-native
investigation.

Capabilities differ by provider and may include:

``` text
profile.read
repositories.read
posts.read
badges.read
comments.read
reputation.read
```

### Step 7 --- Report

Provider results are normalized into observations and included in the
final investigation report, which can be exported as JSON.

------------------------------------------------------------------------

## Identity Discovery

Discovery adapters implement provider-specific search behavior while
exposing a common normalized candidate model.

``` python
class DiscoveryAdapter:
    async def search(
        self,
        query: str,
    ) -> list[DiscoveryCandidate]:
        ...
```

The `DiscoveryEngine` orchestrates adapters concurrently.

A failure in one provider should not prevent other providers from
returning results:

``` text
GitHub failure
      ↓
Steam still runs
Twitch still runs
Stack Exchange still runs
```

This provides graceful degradation when external APIs are unavailable or
rate-limited.

------------------------------------------------------------------------

## 🧩 Cross-Provider Correlation

Correlation is intentionally separate from discovery.

**Discovery asks:** Could this profile be relevant?

**Correlation asks:** How much evidence connects this profile to the
selected anchor?

Signals may include:

-   exact public display-name agreement
-   username similarity
-   token overlap
-   provider-native identifier evidence
-   reusable public handles
-   profile URLs
-   public website information
-   provider metadata

The correlator produces:

``` text
score
reasons
auto_link
```

Example:

``` json
{
  "score": 0.61,
  "reasons": [
    "Exact public display-name match"
  ],
  "auto_link": false
}
```

A same-name match may be useful evidence, but it is **not enough to
claim that two accounts belong to the same person**.

------------------------------------------------------------------------

## Conditional Search Behaviour

Different providers expose fundamentally different search capabilities.
DFT does not pretend that every provider supports the same discovery
model.

### GitHub

GitHub supports broad public identity discovery. Useful inputs include
display name, username, and profile URL.

### Steam

Steam is strongly identifier-oriented. Human-name search is not treated
as equivalent to GitHub-style user discovery.

Reliable resolution uses:

``` text
SteamID64
vanity name
community profile URL
```

### Twitch

Twitch discovery is primarily based on broadcaster/channel identity.

DFT supports:

``` text
Twitch login
display-name-oriented discovery
Twitch profile URL
```

For profile URLs, the broadcaster login is extracted before
provider-native resolution.

### Stack Exchange

Stack Exchange identities are site-specific. The same network account
may have different site user IDs across the Stack Exchange network.

DFT preserves:

``` text
site
site_user_id
account_id
```

separately.

------------------------------------------------------------------------

## Provider Identity Resolution

Automatic correlation cannot always recover the correct provider
identity.

For example:

``` text
GitHub username:
developer_name_123

Twitch username:
completelyDifferentHandle
```

If no public evidence connects those handles, automatically asserting
ownership would be incorrect.

DFT therefore provides manual provider-native fallback resolution. This
is a deliberate part of the architecture --- not a failure of
correlation.

------------------------------------------------------------------------

## ⌨️ Supported Inputs

### GitHub

Supported forms may include:

``` text
username
display name
GitHub profile URL
```

### Steam

Supported exact-resolution forms:

``` text
SteamID64
vanity name
community profile URL
```

Examples:

``` text
7656119XXXXXXXXXX
myvanityname
https://steamcommunity.com/id/myvanityname
https://steamcommunity.com/profiles/7656119XXXXXXXXXX
```

A bare numeric SteamID64 must contain exactly 17 digits.

### Twitch

Supported forms:

``` text
username/login
display-name search
profile URL
```

Example:

``` text
https://www.twitch.tv/exampleuser
```

### Stack Exchange

Supported forms:

``` text
display name
site:user_id
public profile URL
```

Examples:

``` text
Shreyash Singh
stackoverflow:12345678
https://stackoverflow.com/users/12345678/example
meta.stackexchange:1234567
https://meta.stackexchange.com/users/1234567/example
```

> Account-edit URLs such as `/users/edit/...` are not public identity
> URLs and are intentionally not treated as public profile identifiers.

------------------------------------------------------------------------

## Provider Capabilities

Provider capabilities are explicitly declared instead of being
hard-coded into the investigation UI.

``` text
Provider
   ↓
Capability Definitions
   ↓
Requested Capabilities
   ↓
Capability Executor
   ↓
Filtered Observations
```

### GitHub

Public developer-footprint signals can include profile and
repository-related observations depending on configured capabilities.

### Steam

Steam resolution uses provider-native Steam identity information and
public profile information exposed through the Steam Web API.
Availability of gaming/activity information depends on profile privacy
settings.

### Twitch

Twitch uses provider-native broadcaster identity information.
Availability depends on Twitch API capabilities and public channel
information.

### Stack Exchange

Current capabilities include:

``` text
profile.read
posts.read
badges.read
reputation.read
comments.read
associated.read
```

Provider identity distinguishes `site_user_id` from `account_id` because
they represent different scopes in the Stack Exchange network.

------------------------------------------------------------------------

## 📊 Investigation Reports

DFT normalizes provider output into structured observations.

Each provider result may contain:

``` text
provider
status
supported
executed
requested_capabilities
executed_capabilities
observations
errors
```

### JSON Export

The v1 JSON report contains:

``` json
{
  "report_version": "1.0",
  "generated_at": "...",
  "generator": {
    "application": "Digital Footprint Tracer",
    "format": "JSON"
  },
  "query": "...",
  "selected_identity": {},
  "identity_correlation": {},
  "summary": {},
  "providers": []
}
```

`selected_identity` records the original anchor selected by the
operator.

`identity_correlation` records provider identities linked to the logical
subject:

``` json
{
  "identity_correlation": {
    "subject_id": "...",
    "anchor_provider": "github",
    "linked_identity_count": 4,
    "linked_identities": [],
    "unresolved_providers": []
  }
}
```

The summary includes provider counts, evidence counts, failures, skipped
providers, total observations, and observed confidence.

### Provider Status Model

Provider execution can terminate with statuses including:

``` text
SUCCESS
NOT_FOUND
RATE_LIMITED
TIMEOUT
FAILED
SKIPPED
```

`NOT_FOUND` does not mean `FAILED`, and a rate-limited provider does not
invalidate successful evidence returned by other providers.

------------------------------------------------------------------------

## 🛠️ Tech Stack

### Backend

-   Python
-   FastAPI
-   Pydantic
-   SQLAlchemy
-   PostgreSQL
-   HTTPX
-   Celery
-   Redis
-   Docker

### Frontend

-   React
-   TypeScript
-   Vite

### External APIs

-   GitHub
-   Steam
-   Twitch
-   Stack Exchange

------------------------------------------------------------------------

## Project Structure

``` text
Digital-footprint-tracer/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   ├── core/
│   │   ├── db/
│   │   ├── discovery/
│   │   │   ├── adapters/
│   │   │   ├── engine.py
│   │   │   ├── schemas.py
│   │   │   └── scoring.py
│   │   ├── identity/
│   │   │   ├── correlation.py
│   │   │   ├── resolution.py
│   │   │   └── schemas.py
│   │   ├── investigations/
│   │   ├── jobs/
│   │   │   ├── celery_app.py
│   │   │   └── tasks.py
│   │   └── providers/
│   │       └── username/
│   └── ...
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── pages/
│   │   └── types/
│   └── ...
│
├── docker-compose.yml
└── README.md
```

------------------------------------------------------------------------

## 📦 Installation

### Prerequisites

Recommended local environment:

``` text
Python 3.x
Node.js
npm
PostgreSQL
Redis
Docker + Docker Compose
```

Clone the repository:

``` bash
git clone <YOUR_REPOSITORY_URL>
cd "Digital footprint tracer"
```

### Backend Setup

``` bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

``` powershell
.venv\Scripts\activate
```

Install backend dependencies using the dependency file included in the
repository.

If the project uses `requirements.txt`:

``` bash
pip install -r backend/requirements.txt
```

------------------------------------------------------------------------

## Environment Configuration

Create your local environment file from the provided example:

``` bash
cp .env.example .env
```

Typical configuration categories include:

``` env
DATABASE_URL=
REDIS_URL=

GITHUB_TOKEN=

STEAM_API_KEY=

TWITCH_CLIENT_ID=
TWITCH_CLIENT_SECRET=

STACKEXCHANGE_API_KEY=
```

> Exact environment variable names must match the repository
> configuration.

Never commit `.env` or real API credentials.

Recommended `.gitignore` entries:

``` gitignore
.env
.env.*
!.env.example

.venv/
venv/

node_modules/
dist/

__pycache__/
*.pyc

.DS_Store
```

------------------------------------------------------------------------

## Docker Infrastructure

Start configured infrastructure:

``` bash
docker compose up -d
```

Check status:

``` bash
docker compose ps
```

Stop services:

``` bash
docker compose down
```

Inspect logs:

``` bash
docker compose logs
```

------------------------------------------------------------------------

## Running the Backend

``` bash
cd backend
source ../.venv/bin/activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API:

``` text
http://localhost:8000
```

FastAPI documentation:

``` text
http://localhost:8000/docs
```

------------------------------------------------------------------------

## Running Celery

DFT's Celery application lives under:

``` text
app/jobs/celery_app.py
```

Start the worker from the backend directory:

``` bash
celery -A app.jobs.celery_app:celery_app worker --loglevel=info
```

Ensure the configured broker, typically Redis, is running first.

------------------------------------------------------------------------

## Running the Frontend

``` bash
cd frontend
npm install
npm run dev
```

------------------------------------------------------------------------

## Production Build Check

Frontend:

``` bash
cd frontend
npx tsc --noEmit
npm run build
```

Backend:

``` bash
cd backend
python -m compileall -q app
```

No output from the backend compile command indicates successful
compilation.

### Recommended Development Startup

``` text
Terminal 1 → Docker / PostgreSQL / Redis
Terminal 2 → FastAPI
Terminal 3 → Celery
Terminal 4 → Vite
```

------------------------------------------------------------------------

## 🔌 API Architecture

### Identity Search

``` text
POST /api/v1/identity/search
```

Returns public identity candidates.

### Select Anchor Identity

``` text
POST /api/v1/identity/select
```

The backend re-runs discovery and verifies the selected provider
identity before trusting it.

### Automatic Correlation

``` text
POST /api/v1/subjects/{subject_id}/correlate
```

Performs cross-provider discovery and correlation from the verified
anchor.

### Resolve Known Provider Identity

``` text
POST /api/v1/subjects/{subject_id}/identities/resolve
```

Used when automatic correlation cannot identify a known provider
account.

### List Subject Identities

``` text
GET /api/v1/subjects/{subject_id}/identities
```

### Investigate Subject

``` text
POST /api/v1/subjects/{subject_id}/investigate
```

Executes configured provider capabilities against linked provider
identities.

------------------------------------------------------------------------

## Adding a New Provider

A new provider generally requires two layers.

### 1. Discovery Adapter

``` text
query
  ↓
provider-native search
  ↓
DiscoveryCandidate[]
```

Normalize:

``` text
provider
provider_user_id
username
display_name
profile_url
confidence
identifiers
metadata
```

### 2. Provider Capability Implementation

``` text
verified provider identity
        ↓
provider API
        ↓
public observations
```

The provider must then be registered with the relevant
discovery/provider registries and exposed to the investigation layer.

------------------------------------------------------------------------

## Correlation Philosophy

DFT treats identity correlation as an evidence problem.

It deliberately avoids:

``` text
same display name = same person
```

Instead:

``` text
same display name = one correlation signal
```

Ambiguous candidates remain operator-confirmed. The architecture favors
**precision and explainability** over aggressive automatic linking.

------------------------------------------------------------------------

## Why DFT Does Not Use ML Yet

Version 1 intentionally uses deterministic evidence-based correlation.

Machine learning becomes justified once a sufficiently large labeled
dataset exists:

``` text
(anchor identity, candidate identity)
        ↓
SAME PERSON

or

DIFFERENT PERSON
```

A future ML-assisted architecture could be:

``` text
Deterministic Retrieval
        ↓
Candidate Generation
        ↓
Feature Extraction
        ↓
ML Reranker / Identity Classifier
        ↓
Calibrated Probability
        ↓
Evidence Explanation
        ↓
Operator Confirmation
```

Potential features include username similarity, display-name similarity,
location agreement, website overlap, biography similarity, linked-domain
overlap, provider metadata, and temporal signals.

ML would augment the current architecture rather than replace
provider-native discovery.

------------------------------------------------------------------------

## Known Limitations

-   Identity correlation is probabilistic; a high score is not proof of
    identity.
-   DFT is designed around publicly accessible information and
    configured provider APIs.
-   Not every provider supports broad user discovery.
-   Unrelated handles may be impossible to correlate without additional
    public evidence.
-   Display names are not unique.
-   Results depend on provider uptime, quotas, authentication, rate
    limits, privacy settings, and API changes.
-   Failure to discover a profile does not prove that the profile does
    not exist.

------------------------------------------------------------------------

## Privacy and Responsible Use

DFT should be used only for legitimate and authorized purposes involving
publicly accessible information.

Intended areas include:

-   security research
-   OSINT education
-   public identity analysis
-   authorized investigations
-   defensive security
-   identity-resolution research

It is **not** intended to bypass authentication, access private
accounts, evade platform controls, or obtain non-public information.

Users are responsible for complying with applicable laws, platform
terms, organizational policies, and consent requirements.

------------------------------------------------------------------------

## 🔒 Security

### API Credentials

Provider credentials must remain server-side. Never expose secrets in
frontend source code.

### Environment Files

Do not commit:

``` text
.env
API keys
OAuth secrets
database credentials
Redis credentials
```

If a credential has ever been committed publicly, removing it later is
not sufficient --- **rotate it**.

### Identity Trust

The frontend should not be allowed to fabricate trusted provider
identities. DFT re-verifies discovered identities server-side before
persistence where applicable.

------------------------------------------------------------------------

## Troubleshooting

### Backend cannot connect to PostgreSQL

``` bash
docker compose ps
```

Verify `DATABASE_URL`.

### Redis/Celery connection error

``` bash
docker compose up -d
celery -A app.jobs.celery_app:celery_app worker --loglevel=info
```

### Steam profile does not resolve

Prefer a 17-digit SteamID64, vanity name, or full public community URL.

### Twitch URL does not resolve

Use:

``` text
https://www.twitch.tv/<login>
```

or the broadcaster login directly.

### Stack Exchange URL does not resolve

Use the public profile URL:

``` text
https://meta.stackexchange.com/users/1234567/example
```

not:

``` text
/users/edit/...
```

You may also use:

``` text
meta.stackexchange:1234567
```

### TypeScript reports unused imports

``` bash
npx tsc --noEmit
npm run build
```

Remove genuinely unused imports rather than suppressing the compiler
globally.

------------------------------------------------------------------------

## Release Checklist

``` text
[ ] Docker infrastructure starts
[ ] PostgreSQL is available
[ ] Redis is available
[ ] FastAPI starts
[ ] Celery worker becomes ready
[ ] Frontend TypeScript check passes
[ ] Vite production build passes
[ ] GitHub smoke test passes
[ ] Steam smoke test passes
[ ] Twitch smoke test passes
[ ] Stack Exchange smoke test passes
[ ] Correlated identities are correct
[ ] Provider reports open correctly
[ ] JSON export works
[ ] .env is not tracked
[ ] API secrets are not committed
[ ] Working tree is clean
```

------------------------------------------------------------------------

## 🗺️ Roadmap

### v1.0

-   [x] Public identity discovery
-   [x] Candidate ranking
-   [x] Anchor identity selection
-   [x] Persistent logical subjects
-   [x] Multi-provider identities
-   [x] Cross-provider correlation
-   [x] Operator confirmation
-   [x] Manual provider-native fallback
-   [x] GitHub integration
-   [x] Steam integration
-   [x] Twitch integration
-   [x] Stack Exchange integration
-   [x] Provider capability execution
-   [x] Public observations
-   [x] Provider reports
-   [x] JSON report export
-   [x] Docker-backed infrastructure
-   [x] Celery worker architecture

### v1.x

Potential improvements:

-   additional providers
-   correlation-quality test suite
-   provider latency instrumentation
-   caching
-   improved ranking
-   richer evidence provenance
-   asynchronous investigation UX
-   improved retry/backoff strategies
-   investigation history
-   report schema evolution

### v2

Potential larger architecture:

-   identity graph visualization
-   more provider families
-   account relationship graphs
-   calibrated identity probabilities
-   optional ML-assisted reranking
-   larger-scale asynchronous execution
-   advanced investigation workflows
-   workspace-level investigations

------------------------------------------------------------------------

## ☁️ Future SaaS Direction

The current project is structured as a foundation rather than a one-off
username checker.

``` text
Users / Organizations
        ↓
Workspaces
        ↓
Investigations
        ↓
Subjects
        ↓
Identity Graph
        ↓
Provider Identities
        ↓
Capability Jobs
        ↓
Evidence
        ↓
Reports
```

Potential SaaS infrastructure:

``` text
Authentication
RBAC
Usage quotas
Billing
Background job orchestration
Persistent investigation history
Audit logs
Provider credential management
Rate-limit coordination
Caching
Observability
Team workspaces
Scheduled investigations
Webhook/API access
```

------------------------------------------------------------------------

## Design Principles

### Provider Neutrality

The orchestration layer should not depend on provider-specific
identifiers.

### Evidence Over Assumptions

Similarity is treated as evidence, not identity proof.

### Graceful Degradation

One failed provider should not destroy an investigation.

### Explainability

Correlation results should expose reasons rather than only opaque
scores.

### Public-Data Boundaries

Provider integrations operate within configured public APIs and publicly
accessible identity information.

### Extensibility

New providers should plug into discovery and capability contracts rather
than require architecture rewrites.

------------------------------------------------------------------------

## Example End-to-End Flow

``` text
1. User searches:
   "Example Person"

2. DFT discovers:
   GitHub candidate A
   GitHub candidate B
   Twitch candidate C
   Stack Exchange candidates

3. Operator selects:
   GitHub candidate A

4. DFT creates:
   Subject

5. DFT expands public signals.

6. Cross-provider discovery executes.

7. DFT reports:
   GitHub         VERIFIED
   Steam          UNRESOLVED
   Twitch         POSSIBLE
   Stack Exchange POSSIBLE

8. Operator confirms or supplies provider-native identities.

9. Provider capabilities execute.

10. Public observations are normalized.

11. Investigation completes.

12. JSON report is exported.
```

------------------------------------------------------------------------

## Disclaimer

Digital Footprint Tracer provides public-data discovery and correlation
assistance.

Its output should not be treated as definitive proof that multiple
online accounts belong to the same natural person.

Identity matches should be independently verified before being used for
consequential decisions.

------------------------------------------------------------------------

## Contributing

When contributing a new provider:

1.  implement provider-native discovery
2.  normalize candidates
3.  preserve stable provider identifiers
4.  define capabilities
5.  return normalized observations
6.  isolate provider failures
7.  avoid asserting identity from weak evidence
8.  add tests for identifier normalization and failure cases

Pull requests should avoid introducing provider-specific assumptions
into the core orchestration layer.

------------------------------------------------------------------------

## License - Apache 2.0

------------------------------------------------------------------------

## Digital Footprint Tracer v1.0.0

**Discover → Correlate → Verify → Investigate → Report**

Built as an extensible foundation for public identity resolution and
multi-provider digital-footprint analysis.
