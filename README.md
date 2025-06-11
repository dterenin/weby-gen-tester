# Next.js Testing Framework

Automated testing framework for LLM-generated Next.js applications using Pytest, Playwright, and Allure reporting.

## Setup

1. **Prerequisites:**
   - Node.js 18+
   - Python 3.8+
   - FFmpeg

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

## Usage
**Run tests:**
```bash
pytest -s --alluredir=allure-results
```
**View report:**
```bash
allure serve allure-results
```

```bash
allure serve allure-results
```
**Custom CSV columns:**
```bash
pytest -s --alluredir=allure-results \
  --csv-output-field="your_field" \
  --csv-framework-field="framework_field" \
  --csv-input-field="input_field"
```

## Features
- Generates Next.js projects from LLM code blocks
- Installs dependencies and shadcn/ui components
- Applies formatting and automated fixes
- Verifies builds and runs live servers
- Captures screenshots and videos
- Generates interactive Allure reports