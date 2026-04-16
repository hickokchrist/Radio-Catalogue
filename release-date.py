import pandas as pd
import requests
import time
from datetime import datetime

def update_catalogue_dates(input_csv, output_csv):
    df = pd.read_csv(input_csv)
    df['release_year'] = pd.NA
    df['release_month'] = pd.NA
    
    print(f"Starting REST API lookup for {len(df)} tracks...")
    
    # 1. Spoof a standard browser User-Agent to bypass Apple's WAF
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for index, row in df.iterrows():
        title = str(row['title'])
        artist = str(row['artists']).split(',')[0] 
        
        # 2. Let requests handle the query string encoding natively
        params = {
            'term': f"{title} {artist}",
            'entity': 'song',
            'limit': 1
        }
        
        url = "https://itunes.apple.com/search"
        
        try:
            # Pass the params and headers into the GET request
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('resultCount', 0) > 0:
                release_date_str = data['results'][0].get('releaseDate')
                
                if release_date_str:
                    dt = datetime.strptime(release_date_str, "%Y-%m-%dT%H:%M:%SZ")
                    df.at[index, 'release_year'] = dt.year
                    df.at[index, 'release_month'] = dt.month
                    print(f"[SUCCESS] {title} -> {dt.year}-{dt.month:02d}")
                else:
                    print(f"[MISSING DATE] {title}")
            else:
                print(f"[NOT FOUND] {title}")
                
        except requests.exceptions.RequestException as e:
            print(f"[NETWORK ERROR] Fetching {title}: {e}")
        
        # Maintain the 1-second delay to avoid rate limiting
        time.sleep(1)

    df.to_csv(output_csv, index=False)
    print(f"\nUpdate complete. Saved to {output_csv}")

if __name__ == "__main__":
    update_catalogue_dates('catalogue.csv', 'catalogue_updated.csv')