# AI Code Reviewer

A powerful, automated code review tool powered by **Python** and **Large Language Models (Llama 3 via Groq)**. It analyzes source code files for **Clean Code** violations, **SOLID** principles adherence, security vulnerabilities, and performance bottlenecks, generating detailed Markdown reports.

## Features

- **Automated Analysis**: Scans local directories for source code files (`.py`, `.js`, `.java`, etc.).
- **AI-Powered**: Utilizes the **Llama 3** model (via Groq API) for deep code reasoning.
- **Detailed Reports**: Generates professional Markdown reports with actionable feedback and refactoring suggestions.
- **Clean Architecture**: Built with modularity, scalability, and **SOLID** principles in mind.
- **Web Interface**: A professional, deployable web app (Flask) with drag &amp; drop uploads, paste-code support and in-browser rendered reviews with syntax highlighting.
- **CLI Interface**: Easy-to-use Command Line Interface.
- **Desktop GUI** (optional): A native desktop client (CustomTkinter) for offline use.

## Architecture

The project follows a modular **Source Layout** structure:

```text
src/
├── analyzer/    # Handles file system operations (SRP)
├── ai_engine/   # Decoupled LLM client (currently Groq/Llama3)
├── reports/     # Generates output formats (Markdown)
├── utils/       # Configuration & Logging (Singleton/Static patterns)
├── gui.py       # Desktop GUI (CustomTkinter) — optional, reuses the core
└── main.py      # CLI Orchestrator
webapp/
├── server.py    # Flask web server (JSON API + report downloads)
├── templates/   # Single-page front-end (index.html)
└── static/      # CSS, JS and vendored libraries
```

Every interface (Web, CLI and Desktop) is a thin presentation layer: they all
reuse `LocalFileReader`, `GroqClient` and `ReportGenerator` unchanged, so the
business logic lives in exactly one place.

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/ai-code-reviewer.git
   cd ai-code-reviewer
   ```

2. **Set up a virtual environment** (recommended):
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Mac/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration**:
   - Rename `.env.example` to `.env`.
   - Add your **Groq API Key** (Get one for free at [console.groq.com](https://console.groq.com)):
     ```env
     GROQ_API_KEY=gsk_your_key_here...
     ```

## Usage

### Web Interface (recommended)

Start the development server and open it in your browser:

```bash
python -m webapp.server
# then open http://127.0.0.1:5000
```

From the page you can:

- **Drag &amp; drop** or browse source files, or switch to **Paste code** to review a snippet on the fly.
- Set your **Groq API key** from the top-right ⚙ button (stored only in your browser) if it isn't configured server-side via `.env`.
- Click **Analyze Code**; each file gets its own tab with the review rendered as Markdown with syntax highlighting.
- **Download** the full Markdown report, which is also saved server-side to `output/`.

#### Production deployment

The server is a standard WSGI app exposed as `webapp.server:app`. To deploy behind a production server (Linux):

```bash
gunicorn "webapp.server:app" --bind 0.0.0.0:8000 --timeout 300
```

Set the `GROQ_API_KEY` environment variable (or a `.env` file) on the host. The `--timeout` is raised because LLM calls can take several seconds per file.

### Command Line Interface

Run the tool by pointing it to a directory containing code:

```bash
python -m src.main ./path/to/your/code
```

**Example:**
```bash
python -m src.main ./test_code
```

The tool will generate a report in the `output/` directory:
> `output/code_review_report_YYYYMMDD_HHMMSS.md`

### Desktop GUI (optional, offline)

A native desktop client is also available for local use:

```bash
python app.py    # or: python -m src.gui
```

## Technologies

- **Language**: Python 3.10+
- **AI Model**: Llama 3 (70B Versatile)
- **API**: Groq Cloud
- **Web**: Flask, vanilla JS, marked.js + highlight.js
- **Desktop**: CustomTkinter
- **Libraries**: `groq`, `python-dotenv`

## License

This project is open-source