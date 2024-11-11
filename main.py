import re
import openai
import json
import sqlite3
from dotenv import load_dotenv
import os
import uuid

# Load environment variables from .env file
load_dotenv()

# Set your OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    raise ValueError("OpenAI API key is not set in the environment variables.")

# Define regex patterns for initial PII detection
PII_PATTERNS = {
    "Email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b",
    "Phone": r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "Credit Card": r"\b(?:\d[ -]*?){13,16}\b",
    "Address": r"\d+ [A-Za-z]+ (St|Ave|Blvd|Ln)\b",
    "Zip Code": r"\b\d{5}(?:-\d{4})?\b",
}

# Connect to an SQLite database (or another SQL database)
conn = sqlite3.connect('pii_database.db')
cursor = conn.cursor()

# Create tables for sanitized data and PII data
cursor.execute('''
CREATE TABLE IF NOT EXISTS sanitized_data (
    id TEXT PRIMARY KEY,
    redacted_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS pii_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sanitized_id TEXT,
    pii_type TEXT NOT NULL,
    pii_value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sanitized_id) REFERENCES sanitized_data(id)
)
''')

conn.commit()

def detect_pii(text):
    """
    Detects PII in text based on regex patterns.
    """
    pii_found = {}
    for pii_type, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            pii_found[pii_type] = list(set(matches))  # Use set to avoid duplicates
    return pii_found

def detect_pii_with_gpt(text):
    """
    Uses GPT-4 to identify PII in text contextually.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Identify any Personally Identifiable Information (PII) in the following text. Provide it in JSON format."},
                {"role": "user", "content": text}
            ]
        )
        gpt_pii = json.loads(response['choices'][0]['message']['content'])  # Ensure response is JSON-formatted
        return gpt_pii
    except json.JSONDecodeError:
        print("Error: GPT-4 response is not in JSON format.")
        return {}
    except Exception as e:
        print("Error with GPT-4 API call:", e)
        return {}

def merge_pii_detections(regex_pii, gpt_pii):
    """
    Combines PII detections from regex and GPT-4, avoiding duplicates.
    """
    combined_pii = regex_pii.copy()
    for pii_type, values in gpt_pii.items():
        if pii_type in combined_pii:
            combined_pii[pii_type] = list(set(combined_pii[pii_type] + values))
        else:
            combined_pii[pii_type] = values
    return combined_pii

def redact_pii(text, pii_data):
    """
    Replaces detected PII in the text with placeholders.
    """
    redacted_text = text
    for pii_type, values in pii_data.items():
        for value in values:
            placeholder = f"<REDACTED_{pii_type.upper()}>"
            redacted_text = re.sub(re.escape(value), placeholder, redacted_text)
    return redacted_text

def save_to_sql(redacted_text, pii_data):
    """
    Saves redacted text and original PII data to an SQL database.
    """
    sanitized_id = str(uuid.uuid4())

    # Open a new database connection
    conn = sqlite3.connect('pii_database.db')
    cursor = conn.cursor()

    # Insert redacted text into sanitized_data table
    try:
        cursor.execute("INSERT INTO sanitized_data (id, redacted_text) VALUES (?, ?)", (sanitized_id, redacted_text))
        conn.commit()
    except Exception as e:
        print("Error storing redacted text:", e)
        conn.close()
        return

    # Insert PII data into pii_data table with reference to sanitized data
    pii_entries = [(sanitized_id, pii_type, value) for pii_type, values in pii_data.items() for value in values]
    try:
        cursor.executemany("INSERT INTO pii_data (sanitized_id, pii_type, pii_value) VALUES (?, ?, ?)", pii_entries)
        conn.commit()
        print("Data stored successfully in SQL database.")
    except Exception as e:
        print("Error storing PII data:", e)
    
    # Close the database connection
    conn.close()

def process_text(text):
    """
    Detects, redacts, and stores PII from the given text.
    """
    # Step 1: Initial regex-based PII detection
    regex_pii = detect_pii(text)
    
    # Step 2: Additional GPT-4 based detection
    gpt_pii = detect_pii_with_gpt(text)
    
    # Step 3: Combine regex and GPT-4 PII detections, ensuring each value is a list
    combined_pii = {}
    
    for pii_type, values in {**regex_pii, **gpt_pii}.items():
        # Ensure that each value is a list, regardless of its origin (regex or GPT)
        if not isinstance(values, list):
            values = [values]
        combined_pii[pii_type] = combined_pii.get(pii_type, []) + values

    # Step 4: Redact PII in the text
    redacted_text = redact_pii(text, combined_pii)
    
    # Step 5: Store redacted and PII data in SQL database
    save_to_sql(redacted_text, combined_pii)

    return redacted_text


# Test function
if __name__ == "__main__":
    # Sample text containing PII
    test_text = """
    John Doe's email is john.doe@example.com and he lives at 123 Elm St. His phone number is (555) 123-4567.
    """
    
    # Process the text
    redacted_output = process_text(test_text)
    print("Redacted Text:", redacted_output)

    # Close database connection
    conn.close()
