from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from docx import Document
import tempfile
import os
import logging
import re
import requests

app = FastAPI()
logging.basicConfig(level=logging.INFO)

OLLAMA_URL = "http://localhost:11434/api/chat"  # Ollama chat model endpoint


# === PII masking prompt ===
def call_ollama_gemma3(text: str) -> str:
    prompt = f"""
Replace all personally identifiable information (PII) from the following text using the rules below. Replace each sensitive word or phrase with three asterisks (***). Do not remove punctuation or formatting. Keep structure intact.

First, check and replace these specific data types if they exist:
- First name
- Last name / Surname
- Date of birth (Day and Month)
- Place of birth
- Place of residence (City, District)
- Street and house number
- Postal code (ZIP code)
- Telephone number
- Email address
- Names of relatives (Parents, children, partners, etc.)
- Names of involved professionals (teachers, therapists, expert witnesses)
- Names of institutions (schools, clinics, etc.)
- Employer or training institution names
- Occupation titles if identifying
- Court names (e.g., 'Hamburg District Court')
- Case numbers, file numbers
- Vehicle license plate numbers
- IP addresses
- Social security numbers
- Patient or client numbers
- Bank account or insurance numbers
- Specific event dates (e.g., 'Accident on 14.02.')
- Photos or scan references
- Handwriting samples
- Direct quotes with names (e.g., "Mr. X said:")
- Nicknames or initials (if identifiable)
- Proper names in attachments (e.g., school reports)
- URLs, domain names, or online accounts
- GPS or route data

After replacing the above, also check for and mask any other sensitive or personal data using ***.

Now clean the following text:

{text}
"""

    payload = {
        "model": "gemma3:latest",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        return result.get("message", {}).get("content", text).strip()
    except Exception as e:
        logging.error(f"Ollama Gemma error: {e}")
        return text


# === Text skipping rule ===
def should_skip(text: str) -> bool:
    if not text or len(text.strip()) < 3:
        return True
    if re.fullmatch(r"[\d\-.:/() ]+", text):
        return True
    if len(text.split()) < 2:
        return True
    return False


# === Main API Endpoint ===
@app.post("/replace_sensitive_words_doc/")
async def replace_sensitive_words_doc(file: UploadFile = File(...)):
    if not file.filename.endswith(".docx"):
        return {"error": "Only .docx files are supported."}

    # Save uploaded file
    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    with open(temp_input.name, "wb") as f:
        f.write(await file.read())

    doc = Document(temp_input.name)

    # Extract text blocks and positions
    text_blocks = []
    positions = []

    for i, para in enumerate(doc.paragraphs):
        if not should_skip(para.text):
            text_blocks.append(para.text)
            positions.append(("paragraph", i))

    for ti, table in enumerate(doc.tables):
        for ri, row in enumerate(table.rows):
            for ci, cell in enumerate(row.cells):
                if not should_skip(cell.text):
                    text_blocks.append(cell.text)
                    positions.append(("table", ti, ri, ci))

    if not text_blocks:
        return {"error": "No suitable text found for processing."}

    # Batch replace using delimiter
    delimiter = "\n---BLOCK---\n"
    full_batch = delimiter.join(text_blocks)
    cleaned_batch = call_ollama_gemma3(full_batch)
    cleaned_blocks = cleaned_batch.split(delimiter)

    if len(cleaned_blocks) != len(text_blocks):
        logging.warning("Mismatch between original and modified block count.")
        return {"error": "Mismatch in processed text blocks. Try smaller batches."}

    # Apply cleaned text
    for idx, cleaned in enumerate(cleaned_blocks):
        pos = positions[idx]
        if pos[0] == "paragraph":
            doc.paragraphs[pos[1]].text = cleaned
        elif pos[0] == "table":
            ti, ri, ci = pos[1:]
            doc.tables[ti].rows[ri].cells[ci].text = cleaned

    # Save and return
    output_dir = "./modified_docs"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "modified.docx")
    doc.save(output_path)

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="modified.docx"
    )