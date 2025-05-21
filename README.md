# Next.js Site Tester with Playwright and Allure

This project provides a robust testing framework to automatically generate, build, run, and visually test Next.js applications based on LLM-generated code snippets. It leverages Pytest for test orchestration, Playwright for browser automation (screenshots and video recording), and Allure Report for interactive test reporting.

## Features

-   **Automated Site Generation:** Creates a full Next.js project structure from LLM-generated code blocks (e.g., `<Edit filename="...">`).
-   **Dependency Management:** Installs npm dependencies and integrates `shadcn/ui` components.
-   **Code Formatting & Linting:** Applies Prettier formatting.
-   **Automated Fixes:** Includes regex-based fixes for common LLM-generated syntax errors and Next.js API deprecations.
-   **Build Verification:** Checks if the generated Next.js application builds successfully.
-   **Live Server Testing:** Launches the Next.js development server.
-   **Visual Regression (Basic):** Captures full-page screenshots.
-   **Animation Recording:** Records video (webm) and converts to GIF to capture animations and scrolling behavior.
-   **Parametrized Testing:** Runs tests for multiple sites from a CSV dataset.
-   **Rich Reporting:** Generates interactive Allure Reports with attached screenshots, videos, GIFs, and detailed build logs.

## Project Setup

1.  **Clone this repository** (or create the directory structure manually).

2.  **Install Node.js and npm:**
    Ensure Node.js (v18+ recommended) and npm are installed on your system.
    You can download them from [nodejs.org](https://nodejs.org/).

3.  **Install FFmpeg:**
    FFmpeg is required for converting video recordings to GIF.
    -   **macOS (Homebrew):** `brew install ffmpeg`
    -   **Linux (Debian/Ubuntu):** `sudo apt update && sudo apt install ffmpeg`
    -   **Windows:** Download binaries from [ffmpeg.org](https://ffmpeg.org/) and add to PATH.

4.  **Create a Python Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate # On Windows: .\venv\Scripts\activate
    ```

5.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    This will install `pytest`, `playwright`, `requests`, and `allure-pytest`.

6.  **Install Playwright Browser Drivers:**
    ```bash
    playwright install
    ```

7.  **Place your CSV Data:**
    Place your `Unified Data.csv` file in the root directory of this project.
    Ensure it contains the necessary columns (by default: `output_tesslate_response`, `metadata_framework`, `input_question`).

## Running Tests

To run the tests and generate the Allure report:

1.  **Execute Pytest:**
    ```bash
    pytest -s --alluredir=allure-results
    ```
    -   `-s`: To display `print()` statements (progress logs).
    -   `--alluredir=allure-results`: Specifies the directory where Allure test results (raw data) will be stored.

2.  **View Allure Report:**
    After the tests complete, generate and open the interactive HTML report:
    ```bash
    allure serve allure-results
    ```
    This command will build the report and open it in your default web browser.

### Customizing CSV Column Names

If your CSV file uses different column names for the generated code, framework, or input question, you can specify them using command-line options:

```bash
pytest -s --alluredir=allure-results \
    --csv-output-field="output_response" \
    --csv-framework-field="metadata_framework" \
    --csv-input-field="input_question"
```

```bash
./run_tests_in_docker.sh -s --alluredir=allure-results
```
or
```bash
./run_tests_in_docker.sh -s --alluredir=allure-results --csv-output-field="my_code_output"
```