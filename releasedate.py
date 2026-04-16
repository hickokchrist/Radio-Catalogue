import pandas as pd
import requests
import time

def update_catalogue_dates_mb(input_csv, output_csv):
    df = pd.read_csv(input_csv)
    df['release_year'] = pd.NA
    df['release_month'] = pd.NA
    
    print(f"Starting MusicBrainz API lookup for {len(df)} tracks...")
    
    # MusicBrainz strictly enforces descriptive User-Agents
    headers = {
        'User-Agent': 'SonicStewCatalogueUpdater/1.0 ( your-email@example.com )'
    }
    
    for index, row in df.iterrows():
        title = str(row['title'])
        artist = str(row['artists']).split(',')[0] 
        
        # Lucene query syntax for MusicBrainz
        query = f'recording:"{title}" AND artist:"{artist}"'
        url = "https://musicbrainz.org/ws/2/recording"
        
        params = {
            'query': query,
            'fmt': 'json',
            'limit': 1
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Navigate the JSON structure to find the earliest release date
            if data.get('recordings') and len(data['recordings']) > 0:
                recording = data['recordings'][0]
                releases = recording.get('releases', [])
                # ... (inside your loop)
                if releases and 'date' in releases[0]:
                    date_str = str(releases[0]['date']).strip()
                    
                    if date_str:
                        parts = date_str.split('-')
                        # Robust check: Only convert if the string is numeric
                        if parts[0].isdigit():
                            df.at[index, 'release_year'] = int(parts[0])
                            
                            # Safely handle the month if it exists
                            if len(parts) > 1 and parts[1].isdigit():
                                df.at[index, 'release_month'] = int(parts[1])
                            
                            print(f"[SUCCESS] {title} -> {date_str}")
                        else:
                            print(f"[DATA ERROR] {title} has invalid date format: {date_str}")
                    else:
                        print(f"[MISSING DATE] {title} has empty date field")
                else:
                    print(f"[NOT FOUND] {title} date not in release info")
# ...
                
        except requests.exceptions.RequestException as e:
            print(f"[NETWORK ERROR] {title}: {e}")
            
        # Strict 1.2-second delay to guarantee compliance with MB's rate limiting
        time.sleep(1.2)

    df.to_csv(output_csv, index=False)
    print(f"\nUpdate complete. Saved to {output_csv}")

if __name__ == "__main__":
    update_catalogue_dates_mb('catalogue.csv', 'catalogue_updated.csv')