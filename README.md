# 🚀 MCP Workflow Proxy — Redfish Edition

> **82.0% Tool Reduction • 74.7% Token Savings • 133 Endpoints → 24 High-Value MCP Tools**
>
> A Model Context Protocol (MCP) server that simplifies a raw 133-endpoint DMTF Redfish spec into **21 semantic workflow tools** + **3 advanced meta-tools**. This gives LLM agents (like Claude or Cursor) the power to manage entire server infrastructures with plain English, eliminating context window bloat and tool selection confusion.

---

## ⚡ Key Highlights
* **82.0% Tool Count Reduction:** Collapses 133 raw, confusing API endpoints into 24 intelligent, semantic MCP tools.
* **74.7% Token Footprint Savings:** Reduces tool definition size from **12,060+** tokens down to **3,058** tokens (and **99.3% savings** compared to raw OpenAPI spec ingestion).
* **Zero Runtime LLM Cost:** Workflow execution runs locally in a pure Python engine. No LLM calls are made at runtime, ensuring sub-second execution times and deterministic behavior.
* **Hierarchical Exposure ("Tier Toggle"):** Provides high-level abstractions but exposes an escape hatch toolset if the LLM needs to call raw endpoints.
* **Stateful Cache Integration:** Implements an in-memory TTL cache for GET calls that automatically invalidates on state-changing requests (POST/PATCH/PUT/DELETE) within a workflow execution.
* **Dynamic Natural Language Builder:** Generate new workflow YAML templates on-the-fly using plain English prompts, which hot-reload directly into the active MCP server tools without server downtime.
* **Rich Observability Dashboard:** FastAPI-powered dashboard with real-time SSE execution tracing, mapping visualizations, metrics charts, and a manual execution portal.

---

## 📐 High-Level Architecture

The MCP Workflow Proxy operates in a hybrid **two-phase workflow**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          1. DESIGN TIME (Offline)                           │
│                                                                             │
│  Raw OpenAPI Spec ──► parse_spec.py ──► summaries ──► LLM Clustering ──────┐│
│   (133 Endpoints)       (Person 1)     (Token-Clean)  (Design-Time Prompt)  ││
│                                                                            ││
│                                           workflows.yaml ◄─────────────────┘│
│                                     (21 Workflow Blueprints)                │
└─────────────────────────────────────────────────────────────────────────────┘
                                             │
                                             │ (Loads YAML & registers tools)
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          2. RUNTIME (Local Engine)                          │
│                                                                             │
│  AI Agent  ──► MCP Client  ──► mcp_server.py ──► workflow_engine.py         │
│  (Claude,       (FastMCP)       (stdio/SSE)       (Chaining & Conditions)   │
│   Cursor)                                               │                   │
│                                                         ▼                   │
│                                              Local Caching (GETs)           │
│                                                         │                   │
│                                                         ▼                   │
│                                                Prism Mock / Real BMC        │
│                                                  (localhost:4010)           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Repository Structure

```
MCP-Workflow/
├── setup.bat                     # One-click setup for Windows
├── setup.sh                      # One-click setup for Mac/Linux
├── generate_config.py            # Auto-generates Claude Desktop config snippet
├── mcp_server.py                 # Wraps the engine as a FastMCP stdio/SSE server (Person 4)
├── workflow_engine.py            # Core runtime engine with variable chaining, loops, and conditions (Person 3)
├── workflows.yaml                # Declarative workflow blueprints (21 YAML profiles) (Person 2)
├── requirements.txt              # Python project dependencies
├── download_spec.py              # Downloads DMTF Redfish schema files (Person 1)
├── parse_spec.py                 # Merges and cleans schemas into summary format (Person 1)
├── fix_spec_for_prism.py         # Patches merged OpenAPI spec for compatibility with Prism (Person 1)
├── calculate_metrics.py          # Computes before/after tool/token metrics (Person 5)
├── nl_workflow_generator.py      # Natural language workflow synthesizer (Gemini Pro / Local Offline)
├── observability_engine.py       # Instrumented executor with timing and HTTP request tracing
├── observability_server.py       # FastAPI server serving live SSE stream and HTML dashboard
├── ARCHITECTURE.md               # Architecture diagram, clustering strategy, and trade-off analysis
├── WORKFLOW_DEFINITIONS.md       # Full mapping from raw API endpoints to workflow-level tools
├── specs/
│   ├── raw/                      # Original OpenAPI schema components (85 files)
│   ├── merged/
│   │   ├── full_spec.yaml        # Merged Redfish spec (OpenAPI 3.0 format)
│   │   └── full_spec_local.yaml  # Merged spec patched with local mock server details
│   ├── cleaned/
│   │   ├── all_endpoints.json    # Processed endpoint lists
│   │   └── endpoints_summary.yaml # Token-efficient summary for LLM design-time input
│   ├── baseline_metrics.json     # Original metrics (133 tools, 410,562 full spec tokens)
│   └── after_metrics.json        # Live metrics verification output
├── dashboard/                    # Main Observability Dashboard UI (HTML, CSS, JS)
└── prompts/
    └── workflow_generation_prompt.md # The exact Claude prompt used to group endpoints
```

---

## 🛠️ Quick Start

### Prerequisites

* **Python 3.10+**
* **Node.js 18+** (for the Prism mock server)

---

### Step 1 — Run Setup (one time only)

**Windows:**
```
setup.bat
```

**Mac/Linux:**
```bash
chmod +x setup.sh && ./setup.sh
```

This creates a virtual environment, installs all dependencies, and prints your ready-to-paste Claude Desktop config snippet. It also saves the snippet to `claude_desktop_config_snippet.json`.

---

### Step 2 — Add to Claude Desktop

Open your Claude Desktop config file:

| Platform | Path |
|---|---|
| Windows (standard) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Windows (Store/MSIX) | `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json` |
| Mac/Linux | `~/Library/Application Support/Claude/claude_desktop_config.json` |

Paste in the `mcpServers` block printed by setup. It will look like:

```json
{
  "mcpServers": {
    "redfish-workflow-proxy": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/mcp_server.py"],
      "env": {}
    }
  }
}
```

> **Note:** The setup script fills in the exact paths for your machine automatically — no manual editing required.

Save the file and **fully restart Claude Desktop**.

---

### Step 3 — Start the Mock Redfish Server

In a terminal, run:

```bash
npx.cmd @stoplight/prism-cli mock specs/merged/full_spec_local.yaml --port 4010
```

> Use `full_spec_local.yaml` (not `full_spec.yaml`) — it has all external schema refs resolved locally so Prism doesn't need internet access.

Keep this terminal open while testing.

---

### Step 4 — Test in Claude Desktop

Start a new chat and try:

* *"What tools are available?"*
* *"Run a health check on Server1."*
* *"Show me the thermal status of the chassis."*
* *"Update firmware on Server1 using image URI http://mock-server/firmware/bios-2.1.0.bin"*

---

### Step 5 — Launch the Observability Dashboard (optional)

```bash
venv/Scripts/python observability_server.py   # Windows
venv/bin/python observability_server.py       # Mac/Linux
```

Opens at `http://localhost:8765` — shows live execution traces, workflow maps, and metrics.

---

## 📊 Live Metrics & Verification

```bash
python calculate_metrics.py
```

### Measured Project Metrics:
| Metric Component | Before | After (MCP Proxy) | Reduction % | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Exposed MCP Tools** | 133 endpoints | **24 tools** (21 workflows + 3 meta) | **82.0%** | **PASS (≥80%)** |
| **Tool Definition Tokens** | 12,060+ (est.) | **3,058** | **74.7%** | **PASS (≥70%)** |
| **Full Spec Raw Ingestion** | 410,562 | **3,058** | **99.3%** | Info |

---

## 💡 How to Use the MCP Tools

### 1. High-Level Workflows (21 Tools)
These tools perform multi-step, conditional operations over the Redfish API.
* **`server_health_check`**: Runs an 8-step diagnostics pipeline across systems, processors, memory, chassis, and thermal logs.
* **`firmware_update`**: Inspects existing inventory versions, compares against targeted image URIs, triggers a simple update task, and polls the progress state.
* **`hardware_inventory_report`**: Gathers comprehensive inventory data including network cards, PCI devices, and storage arrays in a single execution.

*Example prompts for Claude:*
* *"Run a complete health status report on system Server1."*
* *"Update the server firmware using the image http://firmware.local/v2.bin"*
* *"Get the thermal levels and power stats for the chassis."*

### 2. Tier Toggle & Escape Hatch (3 Meta-Tools)
If a high-level workflow fails or the agent encounters an edge case requiring direct API access:
1. **`list_workflows_meta`**: Lists all available workflow definitions.
2. **`list_raw_endpoints`**: Returns the raw API endpoints used by a specific workflow.
3. **`run_raw_endpoint`**: Executes a direct HTTP call to the mock server, bypassing workflow abstraction.

*Example prompt sequence:*
> **User:** *"Configure a BIOS setting that isn't in the bios workflow."*
> **Claude:** calls `list_raw_endpoints("bios_configuration")`, then `run_raw_endpoint(method="PATCH", path="/redfish/v1/Systems/Server1/Bios/Settings", body_json="{\"Attributes\": {\"BootMode\": \"Uefi\"}}")`

---

## 🔍 Features in Detail

### 1. In-Memory Request Caching
Within a single workflow execution, `GET` responses are cached using `cachetools.TTLCache`. Any state-changing request (`POST`, `PATCH`, `PUT`, `DELETE`) immediately purges cached entries for that URL.

### 2. Real-Time Observability Dashboard
Run `observability_server.py` to open the web console at `http://localhost:8765`:
* **Overview Tab:** Live tool/token metrics and execution history.
* **Workflow Map:** Visualizes how workflow nodes map to raw endpoints.
* **Execution Traces:** Live SSE-driven step-by-step timing and status updates.
* **Workflow Catalog:** Searchable library of all 21 blueprints.

### 3. Natural Language Workflow Builder
In the **NL Builder** tab, write a requirement in plain English. The backend compiles a YAML workflow blueprint, appends it to `workflows.yaml`, and the server **hot-reloads** it — the new workflow instantly becomes an active MCP tool.

---

## ⚡ Extension Guide: Onboarding a New Spec in 5 Minutes

1. **Place the Spec:** Drop your raw OpenAPI YAML/JSON files into `specs/raw/`.
2. **Consolidate & Clean:** Run `python parse_spec.py` to generate `specs/cleaned/endpoints_summary.yaml`.
3. **Cluster with AI:** Use the prompt in `prompts/workflow_generation_prompt.md` with the cleaned summary.
4. **Deploy workflows.yaml:** Save the LLM output as `workflows.yaml` in the root.
5. **Start Servers:** Run `python mcp_server.py`. New workflows auto-register as MCP tools.

---

## 👥 Hackathon Team Credits

| Team Member | Role | Key Contributions |
| :--- | :--- | :--- |
| **Person 1** | Data & Mock Engineer | Spec downloading, OpenAPI parsing, Prism mock patching |
| **Person 2** | AI Clustering Architect | LLM clustering prompts, `workflows.yaml` blueprint structure |
| **Person 3** | Runtime Engine Builder | `workflow_engine.py` logic, loop/branch executor, JSONPath extraction |
| **Person 4** | MCP Server Developer | FastMCP wrapper, Dynamic tool generation, Tier Toggle implementation |
| **Person 5** | Integrator & Pitch Master | Token metrics script, Observability Dashboard, Pitch deck dashboard |

---
