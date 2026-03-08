# AI Code Reviewer

A powerful, automated code review tool powered by **Python** and **Large Language Models (Llama 3 via Groq)**. It analyzes source code files for **Clean Code** violations, **SOLID** principles adherence, security vulnerabilities, and performance bottlenecks, generating detailed Markdown reports.

## Features

- **Automated Analysis**: Scans local directories for source code files (`.py`, `.js`, `.java`, etc.).
- **AI-Powered**: Utilizes the **Llama 3** model (via Groq API) for deep code reasoning.
- **Detailed Reports**: Generates professional Markdown reports with actionable feedback and refactoring suggestions.
- **Clean Architecture**: Built with modularity, scalability, and **SOLID** principles in mind.
- **CLI Interface**: Easy-to-use Command Line Interface.

## Architecture

The project follows a modular **Source Layout** structure:

```text
src/
├── analyzer/    # Handles file system operations (SRP)
├── ai_engine/   # Decoupled LLM client (currently Groq/Llama3)
├── reports/     # Generates output formats (Markdown)
├── utils/       # Configuration & Logging (Singleton/Static patterns)
└── main.py      # Orchestrator
```

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

## Technologies

- **Language**: Python 3.10+
- **AI Model**: Llama 3 (70B Versatile)
- **API**: Groq Cloud
- **Libraries**: `groq`, `python-dotenv`

## License

This project is open-source