import pandas as pd
import os

# Create sample data with ONLY working URLs (HCL Tech works, Naukri/LinkedIn don't)
data = {
    'Job Link': [
        'https://careers.hcltech.com/job/Sr-Tech-Lead-GenAI-VectorDBand-MySQL/91729-en_US',
        'https://careers.hcltech.com/job/Sr-Tech-Lead-GenAI-VectorDBand-MySQL/91729-en_US',
        'https://careers.hcltech.com/job/Sr-Tech-Lead-GenAI-VectorDBand-MySQL/91729-en_US'
    ],
    'Email': [
        'your_email@gmail.com',
        'your_email@gmail.com',
        'your_email@gmail.com'
    ],
    'Job Title': [
        'Sr Tech Lead - GenAI (Row 1)',
        'Sr Tech Lead - GenAI (Row 2)',
        'Sr Tech Lead - GenAI (Row 3)'
    ]
}

df = pd.DataFrame(data)

# Save to Excel - overwrite the old one
output_path = 'app/resource/sample_job_links_with_urls.xlsx'
df.to_excel(output_path, index=False)

print(f"✅ Updated sample file: {output_path}")
print(f"All rows now use HCL Tech URL (Naukri/LinkedIn blocked by scraper protection)")
print(f"\nData preview:")
print(df.to_string())
