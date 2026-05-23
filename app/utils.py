import re

import requests
from bs4 import BeautifulSoup
from langchain_community.document_loaders import WebBaseLoader


DEFAULT_WEB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.google.com/",
}


def clean_text(text):
    # Remove HTML tags
    text = re.sub(r'<[^>]*?>', '', text)
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    # Remove special characters
    text = re.sub(r'[^a-zA-Z0-9 ]', '', text)
    # Replace multiple spaces with a single space
    text = re.sub(r'\s{2,}', ' ', text)
    # Trim leading and trailing whitespace
    text = text.strip()
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text


def limit_text_for_llm(text, max_chars=6000):
    cleaned = clean_text(text)
    if len(cleaned) <= max_chars:
        return cleaned

    truncated = cleaned[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > int(max_chars * 0.8):
        truncated = truncated[:last_space]
    return truncated.strip()


def extract_match_sections(text, max_section_chars=500):
    if not text:
        return []

    normalized_text = clean_text(text)
    lowered = normalized_text.lower()
    markers = (
        "job description",
        "jobdescription",
        "key responsibilities",
        "keyresponsibilities",
        "responsibilities",
        "requirements",
        "required skills",
        "preferred skills",
        "skills",
    )

    sections = []
    for marker in markers:
        start = 0
        while True:
            marker_index = lowered.find(marker, start)
            if marker_index == -1:
                break
            section = normalized_text[marker_index:marker_index + max_section_chars].strip()
            if section:
                sections.append(section)
            start = marker_index + len(marker)

    return sections


def build_match_queries(job, source_text, max_queries=8):
    queries = []

    if isinstance(job, dict):
        skills = job.get("skills", []) or []
        if isinstance(skills, str):
            skills = [skills]
        queries.extend(str(skill).strip() for skill in skills if str(skill).strip())

        for field_name in ("role", "description"):
            value = str(job.get(field_name, "")).strip()
            if value:
                queries.append(value)

    queries.extend(extract_match_sections(source_text))

    deduped_queries = []
    seen = set()
    for query in queries:
        normalized_query = clean_text(query)
        if len(normalized_query) < 3:
            continue
        dedupe_key = normalized_query.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped_queries.append(normalized_query)
        if len(deduped_queries) >= max_queries:
            break

    return deduped_queries


def _extract_html_text(html):
    soup = BeautifulSoup(html, "html.parser")
    visible_text = soup.get_text(" ", strip=True)
    if len(clean_text(visible_text)) >= 50:
        return visible_text

    script_chunks = []
    markers = (
        "jobdetails",
        "jobdescription",
        "description",
        "requirements",
        "skills",
        "experience",
        "designation",
        "role",
        "__next_data__",
    )
    for script in soup.find_all("script"):
        script_text = script.get_text(" ", strip=True)
        if not script_text:
            continue
        lowered = script_text.lower()
        if any(marker in lowered for marker in markers):
            script_chunks.append(script_text)

    if not script_chunks:
        script_chunks = [
            script.get_text(" ", strip=True)
            for script in soup.find_all("script")
            if script.get_text(" ", strip=True)
        ]

    return " ".join([visible_text, *script_chunks])


def load_url_text(url, min_chars=50, headers=None, timeout=20):
    request_headers = headers or DEFAULT_WEB_HEADERS

    try:
        loader = WebBaseLoader([url], requests_kwargs={"headers": request_headers})
        pages = loader.load()
    except Exception:
        pages = []

    if pages:
        loader_text = clean_text(pages[0].page_content)
        if len(loader_text) >= min_chars:
            return loader_text, "loader"
    else:
        loader_text = ""

    response = requests.get(url, headers=request_headers, timeout=timeout)
    response.raise_for_status()
    html_text = clean_text(_extract_html_text(response.text))
    if html_text:
        return html_text, "html-fallback"

    return loader_text, "empty"


def build_row_job_context(row):
    fields = []
    field_mapping = (
        ("Job Title", "Job title"),
        ("Technology", "Technology"),
        ("Company", "Company"),
        ("Posted", "Posted"),
        ("Location", "Location"),
        ("Experience", "Experience"),
        ("Email", "Contact email"),
        ("Job Link", "Source URL"),
    )

    for column_name, label in field_mapping:
        value = row.get(column_name, "") if hasattr(row, "get") else ""
        if value is None:
            continue
        value = str(value).strip()
        if not value or value.lower() == "nan":
            continue
        fields.append(f"{label}: {value}")

    if not fields:
        return ""

    return (
        "Uploaded spreadsheet metadata for this job. Use it as reliable context if the scraped page is noisy or incomplete. "
        + " ".join(fields)
    )