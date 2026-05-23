import os
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException
from dotenv import load_dotenv

APP_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
ROOT_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(ROOT_ENV_PATH)
load_dotenv(APP_ENV_PATH, override=True)

class Chain:
    def __init__(self):
        groq_api_key = os.getenv("GROQ_API_KEY")
        groq_model = os.getenv("GROQ_MODEL")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY is not set. Please add it to your .env file.")
        self.llm = ChatGroq(temperature=0, groq_api_key=groq_api_key, model_name=groq_model)

    def extract_jobs(self, cleaned_text):
        prompt_extract = PromptTemplate.from_template(
            """
            ### SCRAPED TEXT FROM WEBSITE:
            {page_data}
            ### INSTRUCTION:
            The scraped text is from the career's page of a website.
            Your job is to extract the job postings and return them in JSON format containing the following keys: `role`, `experience`, `skills` and `description`.
            Only return the valid JSON.
            ### VALID JSON (NO PREAMBLE):
            """
        )
        chain_extract = prompt_extract | self.llm
        res = chain_extract.invoke(input={"page_data": cleaned_text})
        try:
            json_parser = JsonOutputParser()
            res = json_parser.parse(res.content)
        except OutputParserException:
            raise OutputParserException("Context too big. Unable to parse jobs.")
        return res if isinstance(res, list) else [res]

    @staticmethod
    def _build_candidate_summary(links):
        if not links:
            return "No strong candidate matches were found."

        summary_lines = []
        seen_candidates = set()

        for match_group in links:
            for candidate in match_group:
                name = candidate.get("Candidate Name", "").strip()
                matched_skill = candidate.get("Skill", "").strip()
                notice_period = candidate.get("Notice Period (Days)", "").strip()
                if not name or not matched_skill:
                    continue

                dedupe_key = (name, matched_skill)
                if dedupe_key in seen_candidates:
                    continue
                seen_candidates.add(dedupe_key)

                notice_text = f"{notice_period} days" if notice_period else "Available on request"
                summary_lines.append(
                    f"- {name} | Matched skill: {matched_skill} | Notice period: {notice_text}"
                )

        return "\n".join(summary_lines) if summary_lines else "No strong candidate matches were found."

    def write_mail(self, job, links):
        has_matches = any(match_group for match_group in links)
        candidate_summary = self._build_candidate_summary(links)
        prompt_email = PromptTemplate.from_template(
            """
            ### JOB DESCRIPTION:
            {job_description}

            ### MATCHED TALENT SUMMARY:
            {candidate_summary}

            ### INSTRUCTION:
            You are Abhishek, a business development executive at RSI. RSI is an AI & Software Consulting company dedicated to facilitating
            the seamless integration of business processes through automated tools. 
            Over our experience, we have empowered numerous enterprises with tailored solutions, fostering scalability, 
            process optimization, cost reduction, and heightened overall efficiency. 
            Your job is to write a short cold email to the client regarding the job mentioned above describing the capability of RSI 
            in fulfilling their needs.
            If matched talent is available, include a compact section with up to 3 strongest candidates using only name, matched skill, and notice period.
            If matched talent is not available, do not mention candidates and write a capability-only email.
            Do not include candidate email addresses, raw JSON, scores, distances, overlap tokens, or the phrase "matched candidates from portfolio".
            Keep the message concise, credible, and sales-oriented, ending with a clear call to action.
            Do not provide a preamble.
            ### EMAIL (NO PREAMBLE):

            """
        )
        chain_email = prompt_email | self.llm
        res = chain_email.invoke(
            {
                "job_description": str(job),
                "candidate_summary": candidate_summary if has_matches else "No strong candidate matches were found.",
            }
        )
        return res.content