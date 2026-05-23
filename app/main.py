import streamlit as st

try:
    from .chains import Chain
    from .portfolio import Portfolio
    from .utils import DEFAULT_WEB_HEADERS, build_match_queries, build_row_job_context, clean_text, limit_text_for_llm, load_url_text
    from .mail_sender import MailSender
except ImportError:
    from chains import Chain
    from portfolio import Portfolio
    from utils import DEFAULT_WEB_HEADERS, build_match_queries, build_row_job_context, clean_text, limit_text_for_llm, load_url_text
    from mail_sender import MailSender
import re
import os
from dotenv import load_dotenv

# Load environment variables at startup.
# Priority: app/.env overrides root .env when both are present.
APP_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
ROOT_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(ROOT_ENV_PATH)
load_dotenv(APP_ENV_PATH, override=True)

DEFAULT_FALLBACK_RECIPIENT_ENV_KEY = "DEFAULT_FALLBACK_RECIPIENT"
LEGACY_DEFAULT_RECEIVER_ENV_KEY = "DEFAULT_RECEIVER_EMAIL"


def get_default_receiver_from_env():
    # Support old key name for backward compatibility.
    return os.getenv(
        DEFAULT_FALLBACK_RECIPIENT_ENV_KEY,
        os.getenv(LEGACY_DEFAULT_RECEIVER_ENV_KEY, ""),
    )


def format_processing_result(result):
    message = result.get('message', '')
    source = result.get('source', '')
    if source:
        return f"{message} [source: {source}]"
    return message


def get_rate_limit_message(error):
    error_text = str(error)
    lowered = error_text.lower()
    if "rate limit" not in lowered and "rate_limit_exceeded" not in lowered:
        return None

    retry_match = re.search(r"Please try again in\s+([^\.]+(?:\.[^\s]+)?s)", error_text, re.IGNORECASE)
    retry_after = retry_match.group(1) if retry_match else "a short while"
    return (
        f"Groq rate limit reached for the configured model. "
        f"Retry after {retry_after}."
    )


def get_batch_progress_value(current_index, start_index, rows_to_process):
    return min((current_index - start_index + 1) / max(rows_to_process, 1), 1.0)


@st.cache_resource
def get_chain():
    return Chain()


@st.cache_resource
def get_portfolio():
    return Portfolio()

def create_streamlit_app(llm, portfolio, clean_text):
    st.title("📧 Requirement Mail Generator")

    # Initialize mail sender in session state with values from .env
    if 'mail_sender' not in st.session_state:
        st.session_state.mail_sender = MailSender()
        # Load from .env if available
        if os.getenv("SENDER_EMAIL"):
            st.session_state.mail_sender.sender_email = os.getenv("SENDER_EMAIL")
        if os.getenv("SENDER_PASSWORD"):
            raw_password = os.getenv("SENDER_PASSWORD")
            st.session_state.mail_sender.sender_password = raw_password.replace(" ", "")
        if os.getenv("SMTP_SERVER"):
            st.session_state.mail_sender.smtp_server = os.getenv("SMTP_SERVER")
        if os.getenv("SMTP_PORT"):
            st.session_state.mail_sender.smtp_port = int(os.getenv("SMTP_PORT"))

    # Ensure email config is loaded from .env for any missing values
    if 'mail_sender' in st.session_state:
        if not st.session_state.mail_sender.sender_email and os.getenv("SENDER_EMAIL"):
            st.session_state.mail_sender.sender_email = os.getenv("SENDER_EMAIL")
        if not st.session_state.mail_sender.sender_password and os.getenv("SENDER_PASSWORD"):
            st.session_state.mail_sender.sender_password = os.getenv("SENDER_PASSWORD", "").replace(" ", "")
        if not st.session_state.mail_sender.smtp_server:
            st.session_state.mail_sender.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        if not st.session_state.mail_sender.smtp_port:
            st.session_state.mail_sender.smtp_port = int(os.getenv("SMTP_PORT", 587))
    
    if 'generated_emails' not in st.session_state:
        st.session_state.generated_emails = {}
    
    if 'loaded_df' not in st.session_state:
        st.session_state.loaded_df = None
    
    if 'processing_results' not in st.session_state:
        st.session_state.processing_results = []

    if 'last_processed_row' not in st.session_state:
        st.session_state.last_processed_row = 0

    if 'default_receiver_email' not in st.session_state:
        st.session_state.default_receiver_email = get_default_receiver_from_env()

    # Input method selection - Updated with File Upload option
    input_mode = st.radio(
        "Input method:", 
        ["URL", "Paste Job Description", "Upload File"], 
        horizontal=True
    )

    data = None

    submit_button = False

    if input_mode == "URL":
        url_input = st.text_input(
            "Enter a URL:", 
            value="https://careers.hcltech.com/job/Sr-Tech-Lead-GenAI-VectorDBand-MySQL/91729-en_US"
        )
        st.caption("⚠️ LinkedIn and other login-required sites cannot be scraped. Use 'Paste Job Description' for those.")
        submit_button = st.button("Submit")
        if submit_button:
            try:
                raw, source = load_url_text(url_input, min_chars=100, headers=DEFAULT_WEB_HEADERS)
                if len(raw.strip()) < 100:
                    message = "The page returned too little content. This URL may require authentication (e.g. LinkedIn) or heavy client-side rendering. Use 'Paste Job Description' instead."
                    if source == "empty":
                        message = "Could not extract readable text from the page. This URL likely blocks scrapers or serves only browser-rendered content. Use 'Paste Job Description' instead."
                    st.error(message)
                    return
                data = raw
            except Exception as e:
                st.error(f"An Error Occurred: {e}")
                return
            
    elif input_mode == "Paste Job Description":
        pasted = st.text_area("Paste the job description here:", height=300)
        submit_button = st.button("Submit")
        if submit_button:
            if not pasted.strip():
                st.error("Please paste a job description.")
                return
            data = clean_text(pasted)
        
    else:  # Upload File option
        st.markdown("### 📂 Upload Job Description File")
        st.caption("Supported formats: .xlsx, .csv - Must contain 'Job Link' and 'Email' columns")
        
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['xlsx', 'csv'],
            help="Upload a file containing job descriptions. Required columns: 'Job Link', 'Email'. Supported formats: XLSX, CSV"
        )
        
        if uploaded_file is not None:
            # Display file info
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"📄 **File name:** {uploaded_file.name}")
            with col2:
                st.info(f"📏 **File size:** {uploaded_file.size / 1024:.2f} KB")
            
            submit_button = st.button("Load & Preview", type="primary")
            
            if submit_button:
                try:
                    # Read file content based on type
                    file_extension = uploaded_file.name.split('.')[-1].lower()
                    
                    with st.spinner(f"Reading {uploaded_file.name}..."):
                        import pandas as pd
                        
                        if file_extension == 'csv':
                            df = pd.read_csv(uploaded_file)
                        elif file_extension == 'xlsx':
                            df = pd.read_excel(uploaded_file)
                        else:
                            st.error(f"Unsupported file type: {file_extension}")
                            return
                    
                    # Validate required columns
                    required_cols = ['Job Link', 'Email']
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    
                    if missing_cols:
                        st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
                        st.info(f"Available columns: {', '.join(df.columns.tolist())}")
                        return
                    
                    # Store dataframe in session state
                    st.session_state.loaded_df = df
                    st.session_state.processing_results = []
                    
                    st.success(f"✅ Successfully loaded {uploaded_file.name} with {len(df)} rows")
                    
                except Exception as e:
                    st.error(f"An Error Occurred while reading file: {e}")
                    return
        
        # Display loaded dataframe and processing options
        if st.session_state.loaded_df is not None:
            df = st.session_state.loaded_df
            
            st.markdown("---")
            st.markdown("### 📋 File Preview")
            
            # Display the dataframe
            with st.expander("View Data", expanded=True):
                st.dataframe(df, use_container_width=True)
            
            # Display processing status
            if st.session_state.processing_results:
                st.markdown("### 📊 Processing Results")
                for result in st.session_state.processing_results:
                    result_message = format_processing_result(result)
                    if result['status'] == 'success':
                        st.success(f"✅ Row {result['row_num']}: {result_message}")
                    elif result['status'] == 'error':
                        st.error(f"❌ Row {result['row_num']}: {result_message}")
                    else:
                        st.info(f"ℹ️ Row {result['row_num']}: {result_message}")
            
            # Process all rows button
            st.markdown("### ⚙️ Batch Controls")
            total_rows = len(df)
            default_resume_row = st.session_state.last_processed_row + 1 if st.session_state.last_processed_row else 1
            default_resume_row = min(max(default_resume_row, 1), max(total_rows, 1))
            resume_from_row = st.number_input(
                "Resume from row",
                min_value=1,
                max_value=max(total_rows, 1),
                value=default_resume_row,
                step=1,
                help="Start processing from this 1-based row number. Useful after a rate limit or partial run.",
            )

            col1, col2 = st.columns([1, 1])
            with col1:
                process_button = st.button("🚀 Process All Rows", type="primary", use_container_width=True)
            with col2:
                clear_button = st.button("🗑️ Clear Data", use_container_width=True)
            
            if clear_button:
                st.session_state.loaded_df = None
                st.session_state.processing_results = []
                st.session_state.last_processed_row = 0
                st.rerun()
            
            if process_button:
                # Check if mail sender is configured
                if not st.session_state.mail_sender.sender_email or not st.session_state.mail_sender.sender_password:
                    st.error("❌ Email not configured. Please configure email in the 'Email Configuration' tab first.")
                    st.stop()
                
                st.markdown("### 🔄 Processing Rows...")
                progress_bar = st.progress(0)
                status_text = st.empty()
                start_index = int(resume_from_row) - 1
                rows_to_process = max(total_rows - start_index, 0)
                
                portfolio.load_portfolio()
                
                processing_results = []
                
                for idx, row in df.iloc[start_index:].iterrows():
                    row_num = idx + 1
                    source = ""
                    
                    try:
                        import pandas as pd
                        
                        # Handle NaN values safely
                        job_link = str(row.get('Job Link', '')).strip() if pd.notna(row.get('Job Link')) else ''
                        recipient_email = str(row.get('Email', '')).strip() if pd.notna(row.get('Email')) else ''
                        fallback_receiver = (st.session_state.default_receiver_email or "").strip()
                        used_fallback_receiver = False
                        
                        # Remove 'nan' strings and clean up
                        if job_link.lower() in ('nan', ''):
                            processing_results.append({
                                'row_num': row_num,
                                'status': 'warning',
                                'message': 'Job Link is empty or invalid'
                            })
                            progress_bar.progress(get_batch_progress_value(idx, start_index, rows_to_process))
                            st.session_state.last_processed_row = row_num
                            continue
                        
                        # Check if it's a valid URL
                        if not job_link.startswith(('http://', 'https://')):
                            processing_results.append({
                                'row_num': row_num,
                                'status': 'warning',
                                'message': f'Invalid URL format: "{job_link}" (must start with http:// or https://)'
                            })
                            progress_bar.progress(get_batch_progress_value(idx, start_index, rows_to_process))
                            st.session_state.last_processed_row = row_num
                            continue
                        
                        if recipient_email.lower() in ('nan', ''):
                            recipient_email = fallback_receiver
                            used_fallback_receiver = True

                        if not recipient_email:
                            processing_results.append({
                                'row_num': row_num,
                                'status': 'error',
                                'message': 'Email is empty and no default receiver is configured'
                            })
                            progress_bar.progress(get_batch_progress_value(idx, start_index, rows_to_process))
                            st.session_state.last_processed_row = row_num
                            continue
                        
                        # Validate email format
                        if not re.match(r"[^@]+@[^@]+\.[^@]+", recipient_email):
                            processing_results.append({
                                'row_num': row_num,
                                'status': 'error',
                                'message': f'Invalid email format: {recipient_email}'
                            })
                            progress_bar.progress(get_batch_progress_value(idx, start_index, rows_to_process))
                            st.session_state.last_processed_row = row_num
                            continue
                        
                        status_text.text(f"Processing row {row_num}/{total_rows}: {job_link}")
                        row_context = build_row_job_context(row)
                        
                        # Extract job details from URL
                        with st.spinner(f"Loading job from URL... (Row {row_num})"):
                            try:
                                raw, source = load_url_text(job_link, min_chars=50, headers=DEFAULT_WEB_HEADERS)

                                if row_context:
                                    raw = f"{row_context}\n\nScraped page content:\n{raw}" if raw.strip() else row_context

                                raw = limit_text_for_llm(raw)

                                if len(raw.strip()) < 50:
                                    message = f'Page content too small ({len(raw.strip())} chars). The site may require login or browser rendering. Skipping.'
                                    if source == 'empty':
                                        message = 'Could not extract readable text from the page. The site likely blocks scrapers or requires browser rendering. Skipping.'
                                    processing_results.append({
                                        'row_num': row_num,
                                        'status': 'warning',
                                        'message': message,
                                        'source': source
                                    })
                                    progress_bar.progress(get_batch_progress_value(idx, start_index, rows_to_process))
                                    st.session_state.last_processed_row = row_num
                                    continue
                                
                            except Exception as e:
                                processing_results.append({
                                    'row_num': row_num,
                                    'status': 'error',
                                    'message': f'Failed to load URL: {str(e)}',
                                    'source': source
                                })
                                progress_bar.progress(get_batch_progress_value(idx, start_index, rows_to_process))
                                st.session_state.last_processed_row = row_num
                                continue
                        
                        # Extract jobs from content
                        with st.spinner(f"Extracting job details... (Row {row_num})"):
                            jobs = llm.extract_jobs(raw)
                            
                            if not jobs:
                                processing_results.append({
                                    'row_num': row_num,
                                    'status': 'warning',
                                    'message': 'No job details extracted',
                                    'source': source
                                })
                                progress_bar.progress(get_batch_progress_value(idx, start_index, rows_to_process))
                                st.session_state.last_processed_row = row_num
                                continue
                        
                        # Process first job and generate email
                        job = jobs[0]
                        skills = job.get('skills', [])
                        match_queries = build_match_queries(job, raw)
                        
                        with st.spinner(f"Generating email... (Row {row_num})"):
                            links = portfolio.query_links(match_queries)
                            email_body = llm.write_mail(job, links)
                        
                        # Send email
                        subject = f"Outreach: {job.get('role', 'Job Opportunity')} Position - Consulting Services"
                        
                        with st.spinner(f"Sending email to {recipient_email}... (Row {row_num})"):
                            success, message = st.session_state.mail_sender.send_email(
                                recipient_email, subject, email_body
                            )
                            
                            if success:
                                success_message = f'Email sent to {recipient_email}'
                                if used_fallback_receiver:
                                    success_message = f'Email sent to default receiver {recipient_email} (Email column was empty)'
                                processing_results.append({
                                    'row_num': row_num,
                                    'status': 'success',
                                    'message': success_message,
                                    'source': source
                                })
                            else:
                                processing_results.append({
                                    'row_num': row_num,
                                    'status': 'error',
                                    'message': f'Failed to send email: {message}',
                                    'source': source
                                })

                    except Exception as e:
                        rate_limit_message = get_rate_limit_message(e)
                        if rate_limit_message:
                            processing_results.append({
                                'row_num': row_num,
                                'status': 'error',
                                'message': rate_limit_message,
                                'source': source
                            })
                            processing_results.append({
                                'row_num': row_num,
                                'status': 'warning',
                                'message': 'Batch processing stopped early because the Groq daily token limit was reached.',
                                'source': source
                            })
                            progress_bar.progress(get_batch_progress_value(idx, start_index, rows_to_process))
                            st.session_state.last_processed_row = row_num - 1
                            break

                        processing_results.append({
                            'row_num': row_num,
                            'status': 'error',
                            'message': f'Unexpected error: {str(e)}',
                            'source': source
                        })
                        progress_bar.progress(get_batch_progress_value(idx, start_index, rows_to_process))
                        st.session_state.last_processed_row = row_num
                        continue

                    st.session_state.last_processed_row = row_num
                    progress_bar.progress(get_batch_progress_value(idx, start_index, rows_to_process))
                
                # Store results in session state
                st.session_state.processing_results = processing_results
                
                # Display summary
                st.markdown("---")
                st.markdown("### ✅ Processing Complete")
                
                success_count = len([r for r in processing_results if r['status'] == 'success'])
                error_count = len([r for r in processing_results if r['status'] == 'error'])
                warning_count = len([r for r in processing_results if r['status'] == 'warning'])
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("✅ Successful", success_count)
                with col2:
                    st.metric("❌ Errors", error_count)
                with col3:
                    st.metric("⚠️ Warnings", warning_count)
                
                # Show detailed results
                with st.expander("View Detailed Results", expanded=True):
                    for result in processing_results:
                        result_message = format_processing_result(result)
                        if result['status'] == 'success':
                            st.success(f"Row {result['row_num']}: {result_message}")
                        elif result['status'] == 'error':
                            st.error(f"Row {result['row_num']}: {result_message}")
                        else:
                            st.info(f"Row {result['row_num']}: {result_message}")
                
                st.rerun()

    if submit_button and data:
        with st.spinner("Extracting job details and generating email..."):
            try:
                portfolio.load_portfolio()
                jobs = llm.extract_jobs(limit_text_for_llm(data))
                if not jobs:
                    st.warning("No job postings could be extracted from the content.")
                    st.session_state.generated_emails = {}
                else:
                    generated_emails = {}
                    for i, job in enumerate(jobs):
                        skills = job.get('skills', [])
                        match_queries = build_match_queries(job, data)
                        links = portfolio.query_links(match_queries)
                        email = llm.write_mail(job, links)
                        generated_emails[i] = {
                            'email': email,
                            'job': job,
                            'skills': skills,
                        }
                    st.session_state.generated_emails = generated_emails
            except Exception as e:
                rate_limit_message = get_rate_limit_message(e)
                if rate_limit_message:
                    st.error(rate_limit_message)
                else:
                    st.error(f"An Error Occurred: {e}")

    if st.session_state.generated_emails:
        for i, generated_item in st.session_state.generated_emails.items():
            job = generated_item['job']
            skills = generated_item['skills']
            email = generated_item['email']

            st.subheader(f"Job {i+1}: {job.get('role', 'Unknown Role')}")
            with st.expander("Extracted Job Details"):
                st.markdown(f"**Role:** {job.get('role', 'N/A')}")
                st.markdown(f"**Experience:** {job.get('experience', 'N/A')}")
                st.markdown(f"**Skills:** {', '.join(skills) if skills else 'N/A'}")
                st.markdown(f"**Description:** {job.get('description', 'N/A')}")

            st.markdown("**Generated Cold Email:**")
            st.text_area("Copy the email below:", value=email, height=300, key=f"email_{i}")

            # Add email sending section for each job
            st.markdown("---")
            st.markdown("### ✉️ Send This Email")

            # Create tabs for different sending options
            tab1, tab2 = st.tabs(["Send Email", "Email Configuration"])

            with tab1:
                with st.form(key=f"send_email_form_{i}"):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        recipient_email = st.text_input(
                            "Recipient Email Address",
                            value=st.session_state.default_receiver_email,
                            placeholder="client@company.com",
                            help="Enter the email address for this outreach. Leave unchanged to use the default receiver.",
                            key=f"recipient_{i}"
                        )

                    with col2:
                        custom_subject = st.text_input(
                            "Email Subject (Optional)",
                            placeholder=f"Outreach: {job.get('role', 'Job Opportunity')}",
                            help="Leave blank to auto-generate subject",
                            key=f"subject_{i}"
                        )

                    send_copy = st.checkbox("Send a copy to yourself", value=True, key=f"copy_{i}")

                    # Edit email before sending
                    editable_email = st.text_area(
                        "Edit Email Before Sending (Optional)",
                        value=email,
                        height=200,
                        key=f"editable_email_{i}",
                        help="You can modify the email content before sending"
                    )

                    # Send button
                    send_button = st.form_submit_button("📤 Send Email", type="primary", use_container_width=True)

                    if send_button:
                        recipient_to_send = recipient_email.strip() or st.session_state.default_receiver_email

                        if not recipient_to_send:
                            st.error("No recipient email provided and no default receiver is configured")
                        elif not re.match(r"[^@]+@[^@]+\.[^@]+", recipient_to_send):
                            st.error("Please enter a valid email address")
                        else:
                            # Prepare subject
                            if not custom_subject:
                                subject = f"Outreach: {job.get('role', 'Job Opportunity')} Position - Consulting Services"
                            else:
                                subject = custom_subject

                            # Prepare email body
                            email_body = editable_email

                            # Send email
                            with st.spinner("Sending email..."):
                                success, message = st.session_state.mail_sender.send_email(
                                    recipient_to_send, subject, email_body
                                )

                                if success:
                                    st.success(f"✅ {message}")

                                    # Send copy to sender if requested
                                    if send_copy and st.session_state.mail_sender.sender_email:
                                        with st.spinner("Sending copy to yourself..."):
                                            copy_success, copy_message = st.session_state.mail_sender.send_email(
                                                st.session_state.mail_sender.sender_email,
                                                f"Copy: {subject}",
                                                f"Original recipient: {recipient_to_send}\n\n{email_body}"
                                            )
                                            if copy_success:
                                                st.info("📧 A copy has been sent to your email")
                                            else:
                                                st.warning(f"Could not send copy: {copy_message}")
                                else:
                                    st.error(f"❌ Failed to send email: {message}")

            with tab2:
                st.markdown("#### Configure Email Settings")

                # Show current configuration status
                col1, col2 = st.columns(2)
                with col1:
                    if st.session_state.mail_sender.sender_email:
                        st.success(f"📧 Current sender: {st.session_state.mail_sender.sender_email}")
                    else:
                        st.warning("⚠️ No sender email configured")

                with col2:
                    if st.session_state.mail_sender.sender_password:
                        pwd_len = len(st.session_state.mail_sender.sender_password)
                        if pwd_len == 16:
                            st.success(f"✅ Password configured (length: {pwd_len}/16)")
                            # Show masked password for confirmation
                            st.caption(f"Password saved: {'•' * 8} (16 characters)")
                        else:
                            st.error(f"❌ Invalid password length: {pwd_len}/16")
                    else:
                        st.warning("⚠️ No password configured")

                st.info("Configure your email settings below. Settings will be saved and persist until you clear them.")

                # Get current values from session state
                current_smtp = st.session_state.mail_sender.smtp_server
                current_port = st.session_state.mail_sender.smtp_port
                current_email = st.session_state.mail_sender.sender_email or ""
                current_default_receiver = st.session_state.default_receiver_email or ""

                # Use a form with session state persistence
                with st.form(key="email_config_persistent_form"):
                    smtp_server = st.text_input(
                        "SMTP Server",
                        value=current_smtp,
                        help="e.g., smtp.gmail.com, smtp.outlook.com"
                    )
                    smtp_port = st.number_input(
                        "SMTP Port",
                        value=current_port,
                        help="587 for TLS, 465 for SSL"
                    )
                    sender_email = st.text_input(
                        "Sender Email",
                        value=current_email,
                        placeholder="your_email@example.com"
                    )
                    default_receiver_email = st.text_input(
                        "Default Receiver Email",
                        value=current_default_receiver,
                        placeholder="default@company.com",
                        help="Used when the Email column is blank in uploaded files."
                    )
                    st.markdown("**Email Password / App Password**")
                    st.caption("Enter your 16-character Google App Password WITHOUT spaces")
                    st.code("Example: kpkcoueuboprvgud (16 characters)", language="text")

                    # Show if password is already saved
                    if st.session_state.mail_sender.sender_password:
                        st.info("🔐 A password is already saved. Enter a new password below ONLY if you want to change it.")

                    # Password input - doesn't show existing password for security
                    new_password = st.text_input(
                        "App Password",
                        type="password",
                        placeholder="Enter 16-character app password (leave blank to keep existing)",
                        help="For Gmail, use App Password from Google Account. Leave blank to keep current password."
                    )

                    # Show password strength/validation as user types
                    if new_password:
                        clean_len = len(new_password.replace(" ", ""))
                        if clean_len == 16:
                            st.success(f"✅ Valid length: {clean_len}/16 characters")
                        elif clean_len > 0:
                            st.warning(f"⚠️ Length: {clean_len}/16 characters (need exactly 16)")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        save_config = st.form_submit_button("💾 Save Configuration", use_container_width=True, type="primary")
                    with col2:
                        test_config = st.form_submit_button("🔌 Test Configuration", use_container_width=True)
                    with col3:
                        clear_config = st.form_submit_button("🗑️ Clear Credentials", use_container_width=True)

                    if save_config:
                        # Save SMTP settings
                        st.session_state.mail_sender.smtp_server = smtp_server
                        st.session_state.mail_sender.smtp_port = int(smtp_port)
                        st.session_state.mail_sender.sender_email = sender_email

                        default_receiver_email = (default_receiver_email or "").strip()
                        if default_receiver_email and not re.match(r"[^@]+@[^@]+\.[^@]+", default_receiver_email):
                            st.error(f"❌ Default Receiver Email is invalid: {default_receiver_email}")
                            st.stop()

                        st.session_state.default_receiver_email = default_receiver_email or get_default_receiver_from_env()

                        # Save password ONLY if user entered a new one
                        if new_password and new_password.strip():
                            clean_password = new_password.replace(" ", "")
                            if len(clean_password) == 16:
                                st.session_state.mail_sender.sender_password = clean_password
                                st.success(f"✅ New password saved! (Length: {len(clean_password)} characters)")
                            else:
                                st.error(f"❌ Password not saved: Must be exactly 16 characters (got {len(clean_password)})")
                        else:
                            if st.session_state.mail_sender.sender_password:
                                st.info("ℹ️ Keeping existing password (no new password entered)")
                            else:
                                st.warning("⚠️ No password entered. Please enter a password to send emails.")

                        if sender_email:
                            st.success(f"✅ Email configuration saved! Sender: {sender_email}")
                        else:
                            st.warning("⚠️ Sender email saved but is empty")

                        st.info(f"📩 Default receiver set to: {st.session_state.default_receiver_email}")

                        # Force rerun to refresh the UI and show saved values
                        st.rerun()

                    if test_config:
                        # Determine which password to use
                        if new_password and new_password.strip():
                            test_password = new_password.replace(" ", "")
                            using_new = True
                        elif st.session_state.mail_sender.sender_password:
                            test_password = st.session_state.mail_sender.sender_password
                            using_new = False
                        else:
                            st.error("❌ No password configured. Please enter a password first.")
                            st.stop()

                        if not sender_email and not st.session_state.mail_sender.sender_email:
                            st.error("❌ No sender email configured. Please enter an email.")
                            st.stop()

                        test_email = sender_email if sender_email else st.session_state.mail_sender.sender_email

                        # Create temp sender for testing
                        temp_sender = MailSender()
                        temp_sender.smtp_server = smtp_server
                        temp_sender.smtp_port = int(smtp_port)
                        temp_sender.sender_email = test_email
                        temp_sender.sender_password = test_password

                        with st.spinner("Testing email configuration..."):
                            success, message = temp_sender.validate_credentials()
                            if success:
                                st.success(f"✅ {message}")

                                # Auto-save working credentials if they were new and not saved yet
                                if using_new and new_password:
                                    st.session_state.mail_sender.sender_password = test_password
                                    st.session_state.mail_sender.smtp_server = smtp_server
                                    st.session_state.mail_sender.smtp_port = int(smtp_port)
                                    st.session_state.mail_sender.sender_email = test_email
                                    st.info("💾 Working credentials automatically saved!")
                                    st.rerun()
                            else:
                                st.error(f"❌ {message}")
                                st.info("""
                                **Troubleshooting:**
                                1. Make sure you're using a 16-character App Password
                                2. Remove ALL spaces from the password
                                3. Enable 2-Step Verification in Google Account
                                4. Generate a new App Password at: https://myaccount.google.com/apppasswords
                                """)

                    if clear_config:
                        st.session_state.mail_sender.sender_email = None
                        st.session_state.mail_sender.sender_password = None
                        st.session_state.mail_sender.smtp_server = "smtp.gmail.com"
                        st.session_state.mail_sender.smtp_port = 587
                        st.session_state.default_receiver_email = get_default_receiver_from_env()
                        st.success("✅ All credentials cleared!")
                        st.rerun()

                # Display saved configuration status outside form
                st.markdown("---")
                st.markdown("### 📋 Current Saved Configuration")

                if st.session_state.mail_sender.sender_email:
                    st.write(f"**SMTP Server:** {st.session_state.mail_sender.smtp_server}")
                    st.write(f"**SMTP Port:** {st.session_state.mail_sender.smtp_port}")
                    st.write(f"**Sender Email:** {st.session_state.mail_sender.sender_email}")
                    st.write(f"**Default Receiver:** {st.session_state.default_receiver_email}")
                    if st.session_state.mail_sender.sender_password:
                        pwd_len = len(st.session_state.mail_sender.sender_password)
                        st.write(f"**Password:** {'•' * 12} ({pwd_len} characters) ✅")
                    else:
                        st.write(f"**Password:** ❌ Not configured")
                else:
                    st.warning("No configuration saved yet. Fill out the form above and click 'Save Configuration'.")
                    
                    st.markdown("---")
    
    # Add email configuration in sidebar
    with st.sidebar:
        st.markdown("## 📧 Email Status")
        st.markdown("---")
        
        # Show current configuration status
        if st.session_state.mail_sender.sender_email:
            st.success(f"**Sender:** {st.session_state.mail_sender.sender_email}")
            st.info(f"**Default Receiver:** {st.session_state.default_receiver_email}")
            if st.session_state.mail_sender.sender_password:
                pwd_len = len(st.session_state.mail_sender.sender_password)
                if pwd_len == 16:
                    st.success(f"**Password:** ✅ Configured (16 characters)")
                else:
                    st.error(f"**Password:** ❌ Invalid length ({pwd_len}/16)")
            else:
                st.warning("**Password:** ⚠️ Not configured")
        else:
            st.warning("⚠️ Email not configured")

        # Add a manual test button that shows clear status
        st.markdown("---")
        st.markdown("---")
        
        with st.expander("📖 Email Setup Guide", expanded=False):
            st.markdown("""
            ### How to set up Gmail:
            
            1. **Enable 2-Step Verification**
               - Go to Google Account → Security
               - Turn on 2-Step Verification
            
            2. **Generate App Password**
               - Go to [App Passwords](https://myaccount.google.com/apppasswords)
               - Select app: "Mail"
               - Select device: "Other"
               - Name it "Mail Generator"
               - Copy the 16-character password
            
            3. **Configure in this app**
               - Enter the 16 characters WITHOUT spaces
               - Example: `kpkcoueuboprvgud`
               - Click "Save Configuration"
               - Click "Test Configuration"
            
            ### Common Issues:
            - **Wrong length:** App passwords are always 16 characters
            - **Spaces:** Remove all spaces from the password
            - **Regular password:** Cannot use your regular Gmail password
            """)
        
        # Quick test option
        if st.session_state.mail_sender.sender_email and st.session_state.mail_sender.sender_password:
            st.markdown("---")
            st.markdown("### 🧪 Quick Test")
            test_email_input = st.text_input("Send test to:", placeholder="your@email.com", key="sidebar_test_email")
            if st.button("Send Test Email", use_container_width=True, key="sidebar_test_button"):
                if test_email_input:
                    with st.spinner("Sending test email..."):
                        success, message = st.session_state.mail_sender.send_email(
                            test_email_input,
                            "Test Email from Requirement Mail Generator",
                            "This is a test email to verify your configuration.\n\nBest regards,\nRequirement Mail Generator"
                        )
                        if success:
                            st.success("✅ Test email sent!")
                        else:
                            st.error(f"❌ Failed: {message}")
                else:
                    st.error("Please enter an email address")


if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Cold Email Generator", page_icon="📧")
    chain = get_chain()
    portfolio = get_portfolio()
    create_streamlit_app(chain, portfolio, clean_text)