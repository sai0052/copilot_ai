# 🚀 CodePilot AI

> **An AI-powered autonomous coding agent that analyzes repositories, understands coding tasks, modifies code, runs tests, and reports results.**

CodePilot AI is a full-stack AI engineering project designed to automate parts of the software development workflow.

Instead of manually searching through a repository, identifying relevant files, making changes, and running tests, CodePilot AI uses an LLM-powered agent to perform these steps through a controlled tool-based workflow.

---

## ✨ Features

### 🤖 Autonomous AI Coding Agent
- Understand natural-language coding tasks
- Analyze software repositories
- Search and inspect source code
- Create execution plans
- Modify project files
- Run tests
- Analyze test results
- Report execution results

### 📂 Local Repository Support
- Select a project folder
- Import a local folder through the browser
- Enter a repository path manually
- Register and scan repositories
- Switch between projects
- View the repository file tree

### 🧠 AI Task Modes

| Mode | Purpose |
|------|---------|
| **Implement** | Build or modify functionality |
| **Code Review** | Analyze existing code |
| **Explain** | Explain code and project behavior |
| **Issue** | Diagnose and fix bugs |

### 🐛 Issue / Bug Fixing
Users can describe an issue in natural language and optionally provide additional problem information.

Example:

```text
Fix the failing cart tests and correctly implement the discount calculation.
```

### 🔍 Repository Analysis
The agent can inspect Python, JavaScript, TypeScript, FastAPI, Flask, React, Node.js, configuration files, and other supported project files.

### 🛠️ Agent Tools
Typical tools include:

```text
search_code
read_file
write_file
run_tests
run_command
```

### 🧪 Automated Testing
The agent can modify code, run tests, analyze failures, make corrections, and verify the result.

### 📊 Agent Activity
The UI displays tool execution, searches, tests, files changed, execution status, errors, and final results.

### 📝 Execution Plan
For complex tasks, the agent can create and track a plan before making changes.

### 🔀 Git-Aware Workflow
CodePilot AI is designed to work with Git repositories and can require a Git branch before modifying repository files.

---

# 🏗️ Architecture

```text
                        ┌─────────────────────┐
                        │    CodePilot UI     │
                        │ React + TypeScript  │
                        └──────────┬──────────┘
                                   │ HTTP API
                                   ▼
                        ┌─────────────────────┐
                        │   FastAPI Backend   │
                        └──────────┬──────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
       ┌──────────────┐    ┌───────────────┐    ┌──────────────┐
       │ Repository   │    │  AI Agent     │    │  Execution   │
       │ Analysis     │    │ Orchestrator  │    │  Engine      │
       └──────────────┘    └───────┬───────┘    └──────────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │    Groq LLM     │
                          │ OpenAI-Compatible│
                          │      API        │
                          └─────────────────┘
```

---

# 🔄 Agent Workflow

```text
                   User Task
                       │
                       ▼
              Repository Selection
                       │
                       ▼
               Repository Scan
                       │
                       ▼
               Project Context
                       │
                       ▼
                AI Agent Planning
                       │
                       ▼
                Search Relevant Code
                       │
                       ▼
                 Read Files
                       │
                       ▼
               Analyze Repository
                       │
                       ▼
                Modify Code
                       │
                       ▼
                 Run Tests
                       │
                       ▼
              Analyze Test Results
                       │
                       ▼
              Verify Modifications
                       │
                       ▼
                 Final Result
```

---

# 🧰 Technology Stack

## Frontend
- React
- TypeScript
- Vite
- HTML
- CSS

## Backend
- Python
- FastAPI
- Pydantic
- Uvicorn

## AI
- Groq API
- OpenAI-compatible API
- `openai/gpt-oss-120b`

## Database
- SQLite

## Testing
- Pytest
- Frontend build/test tooling

## Development
- VS Code
- Git
- GitHub
- Node.js
- npm
- Python Virtual Environment

---

# 📁 Project Structure

```text
codepilot-ai/
│
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   ├── api/
│   │   ├── database/
│   │   ├── embeddings/
│   │   ├── execution/
│   │   ├── llm/
│   │   ├── repository/
│   │   ├── schemas/
│   │   ├── tools/
│   │   ├── utils/
│   │   ├── config.py
│   │   └── main.py
│   │
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.*
│
├── sample_projects/
├── scripts/
├── data/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
└── start_codepilot.bat
```

> The exact structure may evolve as the project develops.

---

# ⚙️ Requirements

Install:

- Python 3.11+
- Node.js 18+
- npm
- Git

Verify:

```bash
python --version
node --version
npm --version
git --version
```

---

# 🔑 Environment Variables

Create a `.env` file in the project root.

Example:

```env
LLM_API_KEY=your_groq_api_key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-120b

LLM_TIMEOUT_SECONDS=90
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.2

APP_HOST=0.0.0.0
APP_PORT=8010

APP_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174

DATABASE_URL=sqlite:///./data/codepilot.db
LOG_LEVEL=INFO

AGENT_MAX_ITERATIONS=5
AGENT_REQUIRE_GIT_BRANCH=true
AGENT_SHOW_DIFF_BEFORE_APPROVE=false

CONTEXT_MAX_TOKENS=12000
FILE_MAX_BYTES=1048576

COMMAND_TIMEOUT_SECONDS=120
COMMAND_OUTPUT_MAX_BYTES=200000

ALLOWED_COMMANDS=pytest,python,python3,pip,pip3,npm,npx,node,git

EMBEDDINGS_ENABLED=false
EMBEDDINGS_PROVIDER=sentence_transformers
EMBEDDINGS_MODEL=all-MiniLM-L6-v2
```

> **Important:** Never commit `.env` or real API keys to GitHub. Commit only `.env.example` with placeholder values.

---

# 📥 Installation

Clone the repository:

```bash
git clone https://github.com/sai0052/copilot_ai.git
cd copilot_ai
```

---

# 🐍 Backend Setup

Create a virtual environment:

```bash
python -m venv .venv
```

Activate on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Then activate:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r backend/requirements.txt
```

---

# 🌐 Frontend Setup

```powershell
cd frontend
npm install
cd ..
```

---

# ▶️ Running the Application

CodePilot AI requires both backend and frontend processes.

## Start Backend

From the project root:

```powershell
.venv\Scripts\Activate.ps1
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Backend:

```text
http://127.0.0.1:8010
```

Keep this terminal running.

## Start Frontend

Open another terminal:

```powershell
cd frontend
npm run dev
```

Vite will display the frontend URL, for example:

```text
http://localhost:5173
```

or:

```text
http://localhost:5174
```

Open the displayed URL in your browser.

---

# ❤️ Backend Health Check

Endpoint:

```text
GET /health
```

Open:

```text
http://127.0.0.1:8010/health
```

PowerShell:

```powershell
curl.exe http://127.0.0.1:8010/health
```

A successful response confirms that the backend is running.

---

# 🧑‍💻 Using CodePilot AI

## 1. Start the Application
Start both backend and frontend.

## 2. Select a Repository
Select a project folder, import a local folder, or enter a repository path manually.

Example:

```text
C:\Projects\my-project
```

## 3. Select a Task Mode

```text
Implement
Code Review
Explain
Issue
```

## 4. Enter a Task

Example:

```text
Fix the failing cart tests and correctly implement the discount calculation.
```

## 5. Add an Optional Problem Description

Example:

```text
The cart total is incorrect when a discount is applied.
The existing tests are also failing because of an invalid assertion.
```

## 6. Run the Agent

Click:

```text
Run Agent
```

The agent analyzes the repository, plans the task, makes changes, runs tests, and reports the result.

---

# 🧪 Testing

Run backend tests:

```powershell
pytest backend/tests
```

Verbose:

```powershell
pytest backend/tests -v
```

Build frontend:

```powershell
cd frontend
npm run build
```

---

# 🧪 Sample Projects

Sample projects can be used to test:

- Repository scanning
- Code search
- Bug fixing
- Test execution
- Agent planning
- Code modification
- Test verification

Example:

```text
sample_projects/
```

Sample projects may contain intentional bugs, failing tests, missing implementations, or incorrect logic.

---

# 🛠️ Example Task

Suppose a repository contains:

```python
def apply_discount(total, discount):
    pass
```

A user can submit:

```text
Implement apply_discount and fix the failing cart tests.
```

The agent can:

```text
1. Search for apply_discount
2. Read the implementation
3. Read related tests
4. Determine expected behavior
5. Implement the function
6. Fix related test problems
7. Run the test suite
8. Analyze results
9. Report the final result
```

---

# 🔧 Agent Tools

### `search_code`
Searches the repository for relevant code.

### `read_file`
Reads source files required for analysis.

### `write_file`
Creates or modifies project files.

### `run_tests`
Runs the repository's tests.

### `run_command`
Executes approved development commands.

The command allowlist can be configured using:

```env
ALLOWED_COMMANDS=pytest,python,python3,pip,pip3,npm,npx,node,git
```

---

# 🔐 Security Considerations

Because CodePilot AI can modify files and execute commands, security is important.

Recommended protections include:

- Command allowlists
- Execution timeouts
- Output-size limits
- Git branch requirements
- Environment-variable secrets
- Repository isolation
- Input validation
- LLM request limits
- Error handling
- Secret-safe logging

Do not run the agent against sensitive repositories unless appropriate safeguards are in place.

---

# 🧠 LLM Configuration

Default configuration:

```env
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-120b
```

The LLM layer uses an OpenAI-compatible interface, allowing future adaptation to other compatible providers.

---

# 🚦 LLM Rate Limits

Autonomous agents can generate multiple LLM requests during a single task.

A production implementation should consider:

- Retry handling
- Exponential backoff
- Retry-after support
- Token budgeting
- Context reduction
- Maximum iteration limits
- Clear rate-limit messages

---

# 🗄️ Database

SQLite is used by default:

```env
DATABASE_URL=sqlite:///./data/codepilot.db
```

The database can store:

- Registered projects
- Project metadata
- Agent tasks
- Execution state

Local database files should generally not be committed to a public repository.

---

# 🐳 Docker

Docker configuration is provided through:

```text
docker-compose.yml
```

Build and run:

```bash
docker compose up --build
```

---

# 📸 Screenshots

Recommended screenshots:

```markdown
![CodePilot AI Dashboard](docs/screenshots/dashboard.png)
```

```markdown
![Repository Selection](docs/screenshots/repository-selection.png)
```

```markdown
![Agent Execution](docs/screenshots/agent-execution.png)
```

```markdown
![Final Result](docs/screenshots/final-result.png)
```

---

# 📈 Project Roadmap

## Current

- [x] Local repository selection
- [x] Repository scanning
- [x] Repository tree
- [x] AI task interface
- [x] Multiple task modes
- [x] Problem description
- [x] AI agent execution
- [x] Code search
- [x] File inspection
- [x] File modification
- [x] Test execution
- [x] Agent activity
- [x] Final execution result
- [x] FastAPI backend
- [x] React frontend
- [x] Groq LLM integration
- [x] SQLite database

## Future

- [ ] Advanced codebase indexing
- [ ] RAG-based code retrieval
- [ ] Vector database
- [ ] Embedding-based search
- [ ] Multi-agent architecture
- [ ] Improved context management
- [ ] Streaming LLM responses
- [ ] Better autonomous debugging
- [ ] Automatic Git branch creation
- [ ] Git diff approval
- [ ] Automatic commit generation
- [ ] Pull request generation
- [ ] GitHub integration
- [ ] GitLab integration
- [ ] More programming languages
- [ ] Improved sandboxing
- [ ] Desktop application
- [ ] Cloud deployment
- [ ] User authentication
- [ ] Team collaboration

---

# 🎯 Project Goals

CodePilot AI explores how AI agents can assist with real-world software engineering tasks.

The project demonstrates:

- Large Language Models
- Agentic AI
- Tool calling
- Autonomous coding
- Repository analysis
- Code search
- Context management
- Automated testing
- AI-assisted debugging
- Git workflows
- Full-stack AI application development

---

# 📚 AI Engineering Concepts Demonstrated

### LLM Integration
Connecting an application to an OpenAI-compatible LLM API.

### Prompt Engineering
Providing structured repository context and task information to the agent.

### Agentic Workflows
Allowing the LLM to choose and execute tools to accomplish a task.

### Tool Calling
Connecting the LLM to real software-development tools.

### Context Management
Selecting relevant project information while avoiding unnecessary context.

### Automated Verification
Using tests to verify changes made by the AI agent.

### Error Recovery
Handling failed commands, test failures, API failures, and rate limits.

### Full-Stack Development

```text
React
+
TypeScript
+
FastAPI
+
Python
+
SQLite
+
LLM APIs
```

---

# 🤝 Contributing

Contributions are welcome.

## 1. Fork the Repository

Create your own fork on GitHub.

## 2. Clone Your Fork

```bash
git clone https://github.com/sai0052/copilot_ai.git
cd copilot_ai
```

## 3. Create a Feature Branch

```bash
git checkout -b feature/my-feature
```

## 4. Make Your Changes

Implement and test your changes.

## 5. Run Tests

```bash
pytest backend/tests -v
```

## 6. Build the Frontend

```bash
cd frontend
npm run build
```

## 7. Commit

```bash
git add .
git commit -m "Add my feature"
```

## 8. Push

```bash
git push origin feature/my-feature
```

## 9. Open a Pull Request

Open a Pull Request on GitHub.

---

# 📜 License

This project is currently intended for educational, experimental, and development purposes.

A specific open-source license can be added before accepting external contributions.

---

# 👨‍💻 Author

**Sangeetham saikumar**

GitHub:

https://github.com/sai0052

Project:

https://github.com/sai0052/copilot_ai

---

# ⭐ Support

If you find this project useful or interesting, consider giving the repository a ⭐ on GitHub.

---

# 🚀 CodePilot AI

> **Analyze. Plan. Code. Test. Verify.**

An AI-powered autonomous coding agent designed to bring LLM-powered software engineering workflows into a practical development environment.
