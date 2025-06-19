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

OLLAMA_URL = "http://localhost:11434/api/generate"  # ✅ Correct endpoint for prompt-based models like gemma3

def call_ollama_gemma3(text: str) -> str:
    prompt = f"Identify all sensitive words in the following text and replace them with asterisks (***):\n\n{text}"

    payload = {
        "model": "gemma3:latest",  # ✅ Exact name from `ollama list`
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        return result.get("response", text).strip()
    except Exception as e:
        logging.error(f"Ollama Gemma error: {e}")
        return text

def should_skip(text: str) -> bool:
    if not text or len(text.strip()) < 3:
        return True
    if re.fullmatch(r"[\d\-.:/() ]+", text):
        return True
    if len(text.split()) < 2:
        return True
    return False

@app.post("/replace_sensitive_words_doc/")
async def replace_sensitive_words_doc(file: UploadFile = File(...)):
    if not file.filename.endswith(".docx"):
        return {"error": "Only .docx files are supported."}

    # Save uploaded DOCX to temp
    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    with open(temp_input.name, "wb") as f:
        f.write(await file.read())

    doc = Document(temp_input.name)

    # Process paragraphs
    for para in doc.paragraphs:
        if not should_skip(para.text):
            original = para.text
            para.text = call_ollama_gemma3(original)
            if original != para.text:
                logging.info(f"Paragraph replaced: '{original}' → '{para.text}'")

    # Process tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if not should_skip(cell.text):
                    original = cell.text
                    cell.text = call_ollama_gemma3(original)
                    if original != cell.text:
                        logging.info(f"Table cell replaced: '{original}' → '{cell.text}'")

    # Save and return modified doc
    output_dir = "./modified_docs"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "modified.docx")
    doc.save(output_path)

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="modified.docx"
    )