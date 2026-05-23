from langchain_community.document_loaders import WebBaseLoader

# Test URLs
urls = [
    'https://careers.hcltech.com/job/Sr-Tech-Lead-GenAI-VectorDBand-MySQL/91729-en_US',
    'https://www.naukri.com/job-listings-oracle-fusion-hcm-consultant-maitri-global-hyderabad-8-to-12-years-110526011892'
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.google.com/'
}

for url in urls:
    print(f"\n{'='*60}")
    print(f"Testing: {url}")
    print('='*60)
    try:
        loader = WebBaseLoader([url], requests_kwargs={"headers": headers})
        pages = loader.load()
        
        if pages:
            content = pages[0].page_content
            print(f"✅ Success! Content length: {len(content)} characters")
            print(f"First 200 chars:\n{content[:200]}")
        else:
            print("❌ No pages loaded")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {str(e)}")
