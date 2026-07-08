# 🏟️ Unity26 — AI Stadium Companion for FIFA World Cup 2026

**Unity26** is a GenAI-powered multi-agent stadium assistant designed for international fans attending the **FIFA World Cup 2026**. 

Built to run with **zero paid infrastructure** using the Google Gemini free-tier API, the application features an advanced multi-agent orchestrator, real-time local RAG capabilities, deterministic safety guardrails, and an immersive, KPRverse-inspired responsive frontend UI.

---

## 📖 Table of Contents
1. [Project Overview](#-project-overview)
2. [What It Actually Does](#-what-it-actually-does)
3. [Architecture & Pipeline Flow](#-architecture--pipeline-flow)
4. [Agent System Details](#-agent-system-details)
5. [Real-Time Simulation Controls](#-real-time-simulation-controls)
6. [Security & Guardrails](#-security--guardrails)
7. [Local RAG System](#-local-rag-system)
8. [Installation & Setup](#-installation--setup)
9. [Verification & Testing](#-verification--testing)

---

## 🌟 Project Overview

During a major tournament like the FIFA World Cup 2026, tens of thousands of international fans encounter language barriers, crowded gates, unfamiliar safety protocols, and complex stadium policies. **Unity26** bridges these gaps by providing:
* **Multilingual support** across 6 major fan languages.
* **Deterministic crowd safety navigation** to reroute fans away from unsafe/blocked gates.
* **Real-time environmental evaluation** (e.g., heat warnings and advisories).
* **Accessibility-first navigation** for wheelchair users.
* **Instant policy lookup** via local RAG retrieval (e.g., bag policies, prohibited items).

---

## 🎯 What It Actually Does

Unity26 acts as a conversational companion that updates dynamically based on the live stadium state.

1. **Intelligent Query Routing:** Determines if a fan is looking for directions, policies, transit advice, or in need of emergency assistance.
2. **Safe Navigation Recommendations:** Scores gates based on distance, wheelchair accessibility, and live crowd density. If a gate's density exceeds **85%**, the safety agent vetoes it and redirects the fan.
3. **Live Heat Advisories:** Monitors stadium temperature. At **35°C+**, it appends hydration warnings; at **42°C+**, it triggers an extreme heat protocol with cooling station directions.
4. **Instant Emergency Broadcast:** If a critical crisis is detected (e.g., "fire", "crowd crush"), the app halts regular processing and displays an immersive evacuation screen with evacuation directions.
5. **Speech Integration:** Fans can speak their queries using the Web Speech API and listen to spoken assistant responses in their chosen language.

---

## ⚙️ Architecture & Pipeline Flow

Unity26 implements a **deterministic orchestrator loop** designed to run efficiently with a maximum of **2 Gemini API calls** per query:

```
[User Query]
     │
     ▼
┌──────────────────────────────────────────┐
│  1. GUARDRAILS (Input sanitisation)      │  <- Sanitises XSS, blocks injections
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  2. ROUTER AGENT (Gemini Call #1)        │  <- Classifies intent & extracts entities
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  3. DECISION ENGINE (Pure Python)        │  <- Ranks routes, filters by distance/a11y
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  4. SAFETY AGENT (Deterministic Rules)   │  <- Applies crowd density & heat limits
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  5. LOCAL RAG RETRIEVER (If policy query)│  <- Fetches vector context locally
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  6. RESPONSE AGENT (Gemini Call #2)      │  <- Streams natural language answer
└──────────────────┬───────────────────────┘
                   ▼
┌──────────────────────────────────────────┐
│  7. GUARDRAILS (Output validation)       │  <- Cross-checks approved gates
└──────────────────┬───────────────────────┘
                   ▼
[Streaming Response to UI] & [Trace Logs]
```

---

## 🤖 Agent System Details

### 1. Router Agent
* **Role:** Acts as the entry gatekeeper.
* **Technology:** Uses `gemini-2.0-flash` with structured JSON output schema.
* **Outputs:** Classifies queries into `navigation`, `amenity_search`, `policy_question`, `transport`, `emergency`, or `general_chat`. It also extracts entities like `amenity_type` (e.g., restroom) and assesses the query's urgency level.

### 2. Decision Engine
* **Role:** Calculates physical routes and finds amenities.
* **Technology:** Pure Python geometry and array operations.
* **Logic:** Calculates Euclidean distances between the fan's coordinates and stadium facilities. Disqualifies closed gates and filters out non-wheelchair-accessible options if the fan's profile requires wheelchair access.

### 3. Safety Agent
* **Role:** Evaluates constraints and applies hard logic checks.
* **Technology:** Pure Python rule engine (zero LLM calls to prevent jailbreaks).
* **Logic:** 
  * If crowd density at a recommended gate is `> 85%`, it vetoes the gate, issues a warning, and requests rerouting.
  * If temperature is `>= 35°C`, it attaches a heat warning.
  * If temperature is `>= 42°C`, it attaches an extreme heat danger warning and triggers cooling protocols.

### 4. Local RAG Retriever
* **Role:** Fetches stadium policies from static documents.
* **Technology:** Local `sentence-transformers` (`all-MiniLM-L6-v2`) and local `chromadb`.
* **Logic:** Vectorizes the user's query and fetches relevant policy clauses on startup (no external vector database cost).

### 5. Response Agent
* **Role:** Synthesizes response context into a natural, friendly chat message.
* **Technology:** `gemini-2.0-flash` streaming tokens.
* **System Prompt:** Instructs the model to write directly in the fan's chosen language, respect the safety warnings, and only recommend gates approved by the Safety Agent.

---

## 🎛️ Real-Time Simulation Controls

The frontend includes a toggleable **Control Panel** (inspired by futuristic WebGL control terminals) that lets developers and judges test the system's reactivity:

1. **Gate Crowd Density Sliders:** Drag to adjust crowd density (0% to 100%) for any of the 8 stadium gates. Setting a gate to >85% will cause the Safety Agent to steer subsequent chat recommendations to other gates.
2. **Gate Open/Close Toggles:** Toggle any gate closed to see it instantly disappear from recommendations and turn grey on the SVG stadium map.
3. **Stadium Temperature Slider:** Adjust the live stadium temperature from 10°C to 50°C. 
   * **Normal (10°C - 34°C):** Blue/Green display pill.
   * **Warning (35°C - 41°C):** Amber display pill; prompts hydration advisories.
   * **Danger (42°C - 50°C):** Red pulsing display pill; triggers cooling station directions.
4. **Trigger Emergency Button:** Simulates a critical stadium incident. The next query immediately fires the emergency broadcast overlay, instructing fans to stay calm and evacuate.

---

## 🛡️ Security & Guardrails

* **Input Sanitisation:** Checks special character-to-letter ratios to prevent payload injection and blocks prompt injection keywords (e.g., `ignore previous instructions`).
* **Output Validation:** Scans the LLM's final response for gate names. If the LLM mistakenly recommends a vetoed or closed gate, the guardrail intercepts, overrides the output, and prints an approved safety route instead.
* **CORS Policies:** Configured with explicit origins for local hosting (e.g., `localhost:3000`, `localhost:5500`, `localhost:8000`) rather than wildcard `*` settings.
* **Rate Limiting:** Protects the free Gemini API tier by limiting users to a maximum of 10 requests per minute per session.

---

## 📂 Project Structure

```
Virtual_Promptwars_ch4_FIFA/
├── backend/
│   ├── agents/
│   │   ├── router.py          # Intent classification agent
│   │   ├── safety.py          # Deterministic safety rules agent
│   │   └── responder.py       # Natural language responder agent
│   ├── mock_data/
│   │   ├── amenities.json     # Food, restroom, medical coordinates
│   │   ├── gates.json         # Stadium gate telemetry
│   │   └── stadium_policies.json  # RAG source documents
│   ├── tests/                 # Comprehensive Pytest suite
│   ├── app.py                 # FastAPI Web Server
│   ├── orchestrator.py        # Central multi-agent pipeline
│   ├── retriever.py           # Local Sentence-Transformers RAG
│   ├── guardrails.py          # Input and output validation rules
│   └── requirements.txt       # Python dependencies
├── frontend/
│   ├── index.html             # Redesigned premium HTML5 UI
│   ├── style.css              # Custom styling & animations
│   └── app.js                 # Frontend speech, SVG map & API logic
├── .env                       # API keys (gitignored)
└── README.md                  # System manual (this file)
```

---

## 🚀 Installation & Setup

### 1. Clone the repository
Navigate into the workspace folder containing the code files:
```powershell
cd c:\Users\Lenovo\OneDrive\Desktop\Virtual_Promptwars_ch4_FIFA
```

### 2. Install dependencies
Install backend requirements using Python 3.14 (or your current Python environment):
```powershell
pip install -r backend/requirements.txt
```

### 3. Add API Keys
Create a `.env` file in the root folder with your Gemini API key:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
```

### 5. Launch the Backend Server
Run the FastAPI application with Uvicorn:
```powershell
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```
On startup, Unity26 will download the embedding model, build the local Chroma database, index the stadium policy JSON, and bind to `http://127.0.0.1:8000`.

### 6. Launch the Frontend
Open the `frontend/index.html` file using your web server of choice. For the best experience (avoiding browser file-system security blockages), serve it locally using a utility like **Live Server** (Port 5500) or python's HTTP server:
```powershell
python -m http.server 5500 --directory frontend
```
Then navigate to `http://127.0.0.1:5500` in your web browser.

---

## 🧪 Verification & Testing

Verify that all systems are operational by running the test suite:
```powershell
python -m pytest backend/tests/ -v
```
This executes 43 unit tests covering:
* **Decision Engine logic:** Route ranking and accessibility filtering.
* **Safety Agent conditions:** Gate veto thresholds and temperature warnings.
* **Guardrails security:** Input sanitisation, XSS defenses, output gate matching, and session rate limiting.
