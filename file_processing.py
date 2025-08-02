import re
from datetime import datetime

def extract_date_from_filename(filename):
    """Extract date from filename using various patterns."""
    # Common date patterns in filenames
    patterns = [
        r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
        r'(\d{2}-\d{2}-\d{4})',  # MM-DD-YYYY
        r'(\d{4}_\d{2}_\d{2})',  # YYYY_MM_DD
        r'(\d{2}_\d{2}_\d{4})',  # MM_DD_YYYY
        r'(\d{8})',              # YYYYMMDD
        r'(\d{2}/\d{2}/\d{4})',  # MM/DD/YYYY
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            date_str = match.group(1)
            try:
                # Try different date formats
                for fmt in ['%Y-%m-%d', '%m-%d-%Y', '%Y_%m_%d', '%m_%d_%Y', '%Y%m%d', '%m/%d/%Y']:
                    try:
                        return datetime.strptime(date_str, fmt).date()
                    except ValueError:
                        continue
            except:
                continue
    
    return None
