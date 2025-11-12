import json
import base64

def extract_asset_from_har(har_file_path, asset_url_substring, output_path):
    """
    Extracts a base64 encoded asset from a .har file and saves it.
    """
    try:
        with open(har_file_path, 'r', encoding='utf-8') as f:
            har_data = json.load(f)

        for entry in har_data['log']['entries']:
            if asset_url_substring in entry['request']['url']:
                content = entry['response']['content']
                if 'text' in content and content.get('encoding') == 'base64':
                    asset_data = base64.b64decode(content['text'])
                    with open(output_path, 'wb') as asset_file:
                        asset_file.write(asset_data)
                    print(f"Successfully extracted and saved {asset_url_substring} to {output_path}")
                    return
        print(f"Asset with substring {asset_url_substring} not found or not base64 encoded.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    HAR_FILE = 'phantom_scraper/trademanagergroup.com.har'
    # Create the target directory
    import os
    output_dir = 'phantom_scraper/static/client_specifics/img'
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract logo
    LOGO_URL_SUBSTRING = 'client_specifics/img/logo.gif'
    LOGO_OUTPUT_PATH = os.path.join(output_dir, 'logo.gif')
    extract_asset_from_har(HAR_FILE, LOGO_URL_SUBSTRING, LOGO_OUTPUT_PATH)
