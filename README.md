# 📧 Requirement Mail Generator

This Streamlit app turns a job post into a targeted outreach email for an AI and software consulting company. It supports single-job generation from a public URL or pasted description, and bulk processing from uploaded `.xlsx` or `.csv` files. It uses Groq and LangChain to extract job details, queries a Chroma-backed portfolio to find relevant candidates, and can send outreach emails directly through SMTP.

## What it does

- Accepts job input from a public URL, pasted job description text, or uploaded spreadsheet.
- Extracts role, experience, skills, and description using Groq.
- Matches portfolio candidates using both extracted skills and deterministic text from Job Description, Key Responsibilities, Requirements, and similar sections.
- Uses a Chroma vector store backed by the local portfolio Excel file.
- Generates concise outreach emails tailored to the role.
- Sends emails directly with configurable SMTP credentials.
- Supports a configurable default receiver email when a spreadsheet row has a blank `Email` value.
- Shows which fetch path was used for each uploaded row: `loader` or `html-fallback`.
- Supports batch resume from a chosen row after partial runs or Groq rate limits.

**Example scenario:**

- A client is hiring for a technical or functional role.
- RSI wants to pitch relevant delivery capability and available talent.
- The app drafts a first-pass outreach email based on the job description and matched portfolio profiles.

![App screenshot](imgs/img.png)

## Architecture Diagram

![Architecture diagram](imgs/architecture.png)

## Prerequisites

- Python 3.10+ recommended.
- A Groq API key from https://console.groq.com/keys.
- A local portfolio file in `app/resource/`. The current app reads `app/resource/Resource Details Sample.xlsx` by default.
- SMTP credentials if you want to send emails from the app.

## Setup

1. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

2. Configure environment variables in `app/.env`.

   You can copy `app/.env.example` and update it with your values:

    ```env
    GROQ_API_KEY=your_groq_api_key
    GROQ_MODEL=llama-3.1-8b-instant
    SMTP_SERVER=smtp.gmail.com
    SMTP_PORT=587
    SENDER_EMAIL=your_email@example.com
    SENDER_PASSWORD=your_16_char_app_password
    DEFAULT_FALLBACK_RECIPIENT=default.receiver@example.com
    ```

3. Confirm your portfolio data file exists at `app/resource/Resource Details Sample.xlsx`.

4. Start the Streamlit app:

    ```bash
    streamlit run app/main.py
    ```

## How to use

1. Choose an input method in the app:
    - `URL` for a public careers page.
    - `Paste Job Description` for copied text from portals such as LinkedIn or other login-protected sites.
    - `Upload File` for `.xlsx` or `.csv` files containing `Job Link` and `Email` columns.
2. Submit the job content.
3. Review the extracted job details and generated email.
4. For uploaded files, optionally set `Resume from row` before running batch processing.
5. Send emails from the UI or copy the generated output.

## Spreadsheet Processing

For uploaded `.xlsx` and `.csv` files:

- Required columns: `Job Link`, `Email`
- Optional metadata columns improve matching quality: `Job Title`, `Technology`, `Company`, `Posted`, `Location`, `Experience`
- If `Email` is blank for a row, the app sends to `DEFAULT_FALLBACK_RECIPIENT`
- Each row shows whether content came from `loader` or `html-fallback`
- If Groq rate limits are hit, you can restart from a chosen row using `Resume from row`

## Matching Behavior

Candidate matching is not limited to the LLM-generated skills list.

- The app still uses extracted skills when available.
- It also builds match queries from the job role, description, and text sections such as `Job Description`, `Key Responsibilities`, `Responsibilities`, and `Requirements` found in the scraped page.
- This helps preserve important terms such as `SCM`, `Oracle Fusion`, and similar domain phrases even when a script-heavy job page produces noisy extraction output.

## Notes and limitations

- URL scraping works best for public pages that do not block automated requests.
- LinkedIn and other authenticated job portals usually need the pasted-text flow.
- Script-heavy job boards such as Naukri may fall back to HTML/script extraction. Results are usually usable, but page noise can still affect extraction quality.
- The app trims scraped text before calling Groq to reduce token usage.
- The default Groq model is set to `llama-3.1-8b-instant` to reduce token pressure and rate-limit issues.
- Portfolio records are loaded into the local Chroma store on app use.
- The generated email can include matched candidates when the portfolio returns strong results.
- Gmail sending requires a 16-character App Password, not your normal account password.

## Project Structure

```text
app/
  .env.example      Example runtime configuration
  chains.py        Groq prompts and email generation
  mail_sender.py   SMTP configuration and email sending
  main.py          Streamlit UI and app flow
  portfolio.py     Chroma-backed portfolio loading and matching
  utils.py         Text cleaning helpers
  resource/        Portfolio source files
vectorstore/       Local Chroma persistence
imgs/              README images
```

## License

This project is licensed under the MIT License. See `LICENSE` for details.
