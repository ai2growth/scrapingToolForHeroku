def start_scraping_task(file_path, api_key, selected_columns, instructions, row_limit):
    import pandas as pd

    df = pd.read_csv(file_path)

    # Validate and clean data
    if 'websites' in df.columns:
        website_col = 'websites'
    else:
        website_col = 'Websites'

    valid_rows = df[website_col].dropna().unique()
    results = []
    for row in valid_rows[:row_limit]:
        try:
            scraped_data = scrape_website(row)
            enriched_data = gpt_enrich(scraped_data, api_key, instructions)
            results.append({website_col: row, 'scraped_data': scraped_data, **enriched_data})
        except Exception as e:
            print(f"Skipping row {row}: {e}")

    # Output results
    output_file = file_path.replace('.csv', '_processed.csv')
    pd.DataFrame(results).to_csv(output_file, index=False)
    return output_file
