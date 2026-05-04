import streamlit as st
from langchain_community.document_loaders import WebBaseLoader

from chains import Chain
from portfolio import Portfolio
from utils import clean_text


def create_streamlit_app(llm, portfolio, clean_text):
    st.title("📧 Requirement Mail Generator")

    input_mode = st.radio("Input method:", ["URL", "Paste Job Description"], horizontal=True)

    data = None

    if input_mode == "URL":
        url_input = st.text_input("Enter a URL:", value="https://careers.hcltech.com/job/Sr-Tech-Lead-GenAI-VectorDBand-MySQL/91729-en_US")
        st.caption("⚠️ LinkedIn and other login-required sites cannot be scraped. Use 'Paste Job Description' for those.")
        submit_button = st.button("Submit")
        if submit_button:
            try:
                loader = WebBaseLoader([url_input])
                pages = loader.load()
                if not pages:
                    st.error("Could not load the page. The URL may require login or block scrapers (e.g. LinkedIn).")
                    return
                raw = clean_text(pages.pop().page_content)
                if len(raw.strip()) < 100:
                    st.error("The page returned too little content. This URL may require authentication (e.g. LinkedIn). Use 'Paste Job Description' instead.")
                    return
                data = raw
            except Exception as e:
                st.error(f"An Error Occurred: {e}")
                return
    else:
        pasted = st.text_area("Paste the job description here:", height=300)
        submit_button = st.button("Submit")
        if submit_button:
            if not pasted.strip():
                st.error("Please paste a job description.")
                return
            data = clean_text(pasted)

    if submit_button and data:
        with st.spinner("Extracting job details and generating email..."):
            try:
                portfolio.load_portfolio()
                jobs = llm.extract_jobs(data)
                if not jobs:
                    st.warning("No job postings could be extracted from the content.")
                    return
                for i, job in enumerate(jobs):
                    st.subheader(f"Job {i+1}: {job.get('role', 'Unknown Role')}")
                    with st.expander("Extracted Job Details"):
                        st.markdown(f"**Role:** {job.get('role', 'N/A')}")
                        st.markdown(f"**Experience:** {job.get('experience', 'N/A')}")
                        skills = job.get('skills', [])
                        st.markdown(f"**Skills:** {', '.join(skills) if skills else 'N/A'}")
                        st.markdown(f"**Description:** {job.get('description', 'N/A')}")
                    links = portfolio.query_links(skills)
                    
                    email = llm.write_mail(job, links)
                    st.markdown("**Generated Cold Email:**")
                    st.text_area("Copy the email below:", value=email, height=400, key=f"email_{i}")
            except Exception as e:
                st.error(f"An Error Occurred: {e}")


if __name__ == "__main__":
    chain = Chain()
    portfolio = Portfolio()
    st.set_page_config(layout="wide", page_title="Cold Email Generator", page_icon="📧")
    create_streamlit_app(chain, portfolio, clean_text)


