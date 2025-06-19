from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from docx import Document
import tempfile
import os
import logging
import re

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# Add your sensitive words here
SENSITIVE_WORDS = ["Richterin "]

def mask_sensitive_words(text: str) -> str:
    # Replace each sensitive word (case-insensitive) with asterisks
    for word in SENSITIVE_WORDS:
        text = re.sub(fr"\b{word}\b", "*****", text, flags=re.IGNORECASE)
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

    # Save uploaded DOCX file
    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    with open(temp_input.name, "wb") as f:
        f.write(await file.read())

    doc = Document(temp_input.name)

    # Replace in paragraphs
    for para in doc.paragraphs:
        if not should_skip(para.text):
            original = para.text
            para.text = mask_sensitive_words(original)
            if original != para.text:
                logging.info(f"Paragraph replaced: '{original}' → '{para.text}'")

    # Replace in tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if not should_skip(cell.text):
                    original = cell.text
                    cell.text = mask_sensitive_words(original)
                    if original != cell.text:
                        logging.info(f"Table cell replaced: '{original}' → '{cell.text}'")

    # Save modified file
    output_dir = "./modified_docs"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "modified.docx")
    doc.save(output_path)

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="modified.docx"
    )