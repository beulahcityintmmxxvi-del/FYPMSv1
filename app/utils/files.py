import hashlib
import mimetypes
import os
import uuid

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.utils.errors import FileError


def allowed_extension(filename: str, stage: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if stage == "source_code":
        return ext in current_app.config["ALLOWED_SOURCE_EXTENSIONS"]
    return ext in current_app.config["ALLOWED_TEXT_EXTENSIONS"]


def unique_filename(original_name: str) -> str:
    safe_name = secure_filename(original_name)
    stem, ext = os.path.splitext(safe_name)
    return f"{stem}_{uuid.uuid4().hex}{ext.lower()}"


def file_checksum(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def save_upload(file_obj: FileStorage, stage: str, folder_prefix: str) -> dict:
    if not file_obj or not file_obj.filename:
        raise FileError("No file uploaded.")

    if not allowed_extension(file_obj.filename, stage):
        raise FileError(
            "Invalid file type. Use PDF/DOCX/TXT for chapters/proposal and ZIP for source code."
        )

    upload_root = current_app.config["UPLOAD_FOLDER"]
    target_dir = os.path.join(upload_root, folder_prefix)
    os.makedirs(target_dir, exist_ok=True)

    stored_name = unique_filename(file_obj.filename)
    full_path = os.path.join(target_dir, stored_name)

    file_obj.save(full_path)

    size = os.path.getsize(full_path)
    mime_type = mimetypes.guess_type(full_path)[0] or file_obj.mimetype

    return {
        "stored_filename": stored_name,
        "storage_path": full_path,
        "original_filename": file_obj.filename,
        "file_size": size,
        "mime_type": mime_type,
        "checksum": file_checksum(full_path),
    }