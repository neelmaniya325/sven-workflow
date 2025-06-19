from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from docx import Document
import tempfile
import os
import logging
import re
import requests

app = FastAPI()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# === Mistral API Configuration ===
MISTRAL_API_KEY = "KrA2y6opwresdJRHVcEQShbCt9KPwxTs"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-medium"  # You can also try "mistral-small" or "mistral-tiny"


# === Utility Functions ===


def should_skip(text: str) -> bool:
    """Ignore very short or uninformative text."""
    if not text or len(text.strip()) < 3:
        return True
    if re.fullmatch(r"[\d\-.:/() ]+", text):  # skip numeric/date-only text
        return True
    if len(text.split()) < 2:
        return True
    return False


def call_mistral_api(text: str) -> str:
    """Send the text to Mistral API and get masked version."""
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }

    prompt = (
        "Mask all sensitive or confidential words in the following text by replacing them with '***'. "
        "Return only the modified text.\n\n"
        f"Text:\n{text}"
    )

    payload = {
        "model": MISTRAL_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 512,
    }

    try:
        response = requests.post(MISTRAL_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(f"Mistral API error: {e}")
        return text  # fallback to original


def process_document(doc: Document):
    """Process paragraphs and table cells with Mistral API."""
    for para in doc.paragraphs:
        if not should_skip(para.text):
            original = para.text
            new_text = call_mistral_api(original)
            if original != new_text:
                logging.info(f"Paragraph replaced:\n→ {original}\n→ {new_text}")
                para.text = new_text

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if not should_skip(cell.text):
                    original = cell.text
                    new_text = call_mistral_api(original)
                    if original != new_text:
                        logging.info(
                            f"Table cell replaced:\n→ {original}\n→ {new_text}"
                        )
                        cell.text = new_text


# === FastAPI Endpoint ===


@app.post("/replace_sensitive_words_doc/")
async def replace_sensitive_words_doc(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported.")

    try:
        # Save uploaded file to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(await file.read())
            temp_input_path = tmp.name

        doc = Document(temp_input_path)
        process_document(doc)

        # Save the modified document
        output_dir = "./modified_docs"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"modified_{file.filename}")
        doc.save(output_path)

        return FileResponse(
            output_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=f"modified_{file.filename}",
        )

    except Exception as e:
        logging.exception("Failed to process DOCX file")
        raise HTTPException(status_code=500, detail="Failed to process the DOCX file.")

    finally:
        if os.path.exists(temp_input_path):
            os.remove(temp_input_path)
