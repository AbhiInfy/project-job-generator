# 📧 Requirement Mail Generator

This Streamlit app turns a job post into a targeted outreach email for an AI and software consulting company. It can either scrape a public job page from a URL or accept a pasted job description, extract the role requirements with Groq and LangChain, and generate a concise cold email. It also queries a Chroma-backed internal portfolio to surface relevant candidate matches.

## What it does

- Accepts job input from a public URL or pasted job description text.
- Extracts role, experience, skills, and description using Groq.
- Searches the portfolio vector store for the most relevant candidate matches.
- Generates a short sales-oriented email tailored to the role.

**Example scenario:**

- A client is hiring for a GenAI or software engineering role.
- RSI wants to pitch relevant delivery capability and available talent.
- The app drafts a first-pass outreach email based on the job description and portfolio matches.

![App screenshot](imgs/img.png)

## Architecture Diagram

![Architecture diagram](imgs/architecture.png)

## Prerequisites

- Python 3.10+ recommended.
- A Groq API key from https://console.groq.com/keys.
- A local portfolio file in `app/resource/`. The current app reads `app/resource/Resource Details Sample.xlsx` by default.

## Setup

1. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

2. Create a `.env` file in the project root and add your Groq settings:

    ```env
    GROQ_API_KEY=your_groq_api_key
    GROQ_MODEL=llama-3.1-70b-versatile
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
2. Submit the job content.
3. Review the extracted job details.
4. Copy the generated email from the output area.

## Notes and limitations

- URL scraping works best for public pages that do not block automated requests.
- LinkedIn and other authenticated job portals usually need the pasted-text flow.
- Because the default portfolio source is an `.xlsx` file, you may also need `openpyxl` available in your environment for `pandas.read_excel()`.
- Portfolio records are loaded into the local Chroma store on app use.
- The generated email can include up to three matched candidates when the portfolio returns strong results.

## Project Structure

```text
app/
  chains.py        Groq prompts and email generation
  main.py          Streamlit UI and app flow
  portfolio.py     Chroma-backed portfolio loading and matching
  utils.py         Text cleaning helpers
  resource/        Portfolio source files
vectorstore/       Local Chroma persistence
imgs/              README images
```

## License

This project is licensed under the MIT License. See `LICENSE` for details.
