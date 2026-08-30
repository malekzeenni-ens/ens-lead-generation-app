from __future__ import annotations

import base64
import binascii
import hashlib
import re
from html import escape
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import AssistantAttachment
from app.domains.assistant.schemas import AssistantAttachmentUpload

SUPPORTED_UPLOADS = {
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
GENERATED_MEDIA_TYPES = {
    "txt": "text/plain",
    "csv": "text/csv",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class AssistantFileStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = (settings.database_path.parent / "assistant_files").resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def uploaded(
        self,
        upload: AssistantAttachmentUpload,
        *,
        conversation_id: str,
        message_id: str,
    ) -> AssistantAttachment:
        filename = self._safe_filename(upload.filename)
        extension = Path(filename).suffix.casefold()
        media_type = SUPPORTED_UPLOADS.get(extension)
        if media_type is None:
            raise DomainError(
                "ASSISTANT_ATTACHMENT_UNSUPPORTED",
                "Attach a TXT, CSV, DOCX, PNG, JPG or JPEG file.",
                status_code=415,
            )
        try:
            content = base64.b64decode(upload.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise DomainError(
                "ASSISTANT_ATTACHMENT_INVALID",
                "The attached file could not be decoded.",
            ) from exc
        if not content or len(content) > self.settings.assistant_attachment_max_bytes:
            raise DomainError(
                "ASSISTANT_ATTACHMENT_TOO_LARGE",
                "Each attachment must be between 1 byte and 5 MB.",
                status_code=413,
            )
        extracted_text, processing_status = self._inspect(extension, content)
        storage_name = f"{uuid4().hex}{extension}"
        (self.root / storage_name).write_bytes(content)
        return AssistantAttachment(
            conversation_id=conversation_id,
            message_id=message_id,
            direction="uploaded",
            filename=filename,
            media_type=media_type,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            storage_name=storage_name,
            extracted_text=extracted_text,
            processing_status=processing_status,
        )

    def generated(
        self,
        *,
        conversation_id: str,
        message_id: str,
        requested_format: str,
        suggested_filename: str,
        content: str,
    ) -> AssistantAttachment:
        if requested_format not in GENERATED_MEDIA_TYPES:
            raise DomainError("ASSISTANT_ARTIFACT_INVALID", "Unsupported generated file format.")
        stem = Path(self._safe_filename(suggested_filename)).stem or "assistant-file"
        stem = re.sub(r"[^A-Za-z0-9 _-]+", "", stem).strip()[:100] or "assistant-file"
        filename = f"{stem}.{requested_format}"
        if requested_format == "docx":
            file_content = self._docx(content)
        else:
            prefix = b"\xef\xbb\xbf" if requested_format == "csv" else b""
            file_content = prefix + content.encode("utf-8")
        if len(file_content) > self.settings.assistant_attachment_max_bytes:
            raise DomainError(
                "ASSISTANT_ARTIFACT_TOO_LARGE",
                "The generated attachment exceeded the local 5 MB limit.",
                status_code=413,
            )
        storage_name = f"{uuid4().hex}.{requested_format}"
        (self.root / storage_name).write_bytes(file_content)
        return AssistantAttachment(
            conversation_id=conversation_id,
            message_id=message_id,
            direction="generated",
            filename=filename,
            media_type=GENERATED_MEDIA_TYPES[requested_format],
            size_bytes=len(file_content),
            sha256=hashlib.sha256(file_content).hexdigest(),
            storage_name=storage_name,
            extracted_text=content[: self.settings.assistant_attachment_context_chars],
            processing_status="generated",
        )

    def path(self, attachment: AssistantAttachment) -> Path:
        candidate = (self.root / attachment.storage_name).resolve()
        if candidate.parent != self.root or not candidate.is_file():
            raise DomainError(
                "ASSISTANT_ATTACHMENT_NOT_FOUND",
                "The local attachment file is no longer available.",
                status_code=404,
            )
        return candidate

    def _inspect(self, extension: str, content: bytes) -> tuple[str | None, str]:
        if extension == ".png":
            if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                self._invalid_file()
            return None, "stored_image_text_model"
        if extension in {".jpg", ".jpeg"}:
            if not content.startswith(b"\xff\xd8") or not content.endswith(b"\xff\xd9"):
                self._invalid_file()
            return None, "stored_image_text_model"
        if extension == ".docx":
            return self._docx_text(content), "text_extracted"
        if b"\x00" in content:
            self._invalid_file()
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DomainError(
                "ASSISTANT_ATTACHMENT_ENCODING",
                "TXT and CSV attachments must use UTF-8 text encoding.",
            ) from exc
        return text[: self.settings.assistant_attachment_context_chars], "text_extracted"

    def _docx_text(self, content: bytes) -> str:
        try:
            with ZipFile(BytesIO(content)) as archive:
                info = archive.getinfo("word/document.xml")
                if info.file_size > self.settings.assistant_attachment_context_chars * 20:
                    raise DomainError(
                        "ASSISTANT_ATTACHMENT_TOO_LARGE",
                        "The Word document contains too much text for the local assistant.",
                        status_code=413,
                    )
                xml = archive.read(info)
        except (BadZipFile, KeyError) as exc:
            raise DomainError(
                "ASSISTANT_ATTACHMENT_INVALID",
                "The DOCX attachment is not a valid Word document.",
            ) from exc
        text = re.sub(r"<[^>]+>", " ", xml.decode("utf-8", errors="replace"))
        return re.sub(r"\s+", " ", text).strip()[: self.settings.assistant_attachment_context_chars]

    @staticmethod
    def _safe_filename(filename: str) -> str:
        clean = Path(filename.replace("\\", "/")).name.strip()
        if not clean or clean in {".", ".."} or any(ord(char) < 32 for char in clean):
            raise DomainError(
                "ASSISTANT_ATTACHMENT_INVALID",
                "The attachment filename is invalid.",
            )
        return clean[:255]

    @staticmethod
    def _invalid_file() -> None:
        raise DomainError(
            "ASSISTANT_ATTACHMENT_INVALID",
            "The attachment content does not match its file extension.",
        )

    @staticmethod
    def _docx(content: str) -> bytes:
        paragraphs = "".join(
            f'<w:p><w:r><w:t xml:space="preserve">{escape(line)}</w:t></w:r></w:p>'
            for line in content.splitlines()
        )
        document = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{paragraphs}<w:sectPr/></w:body></w:document>"
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>"
        )
        relationships = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" '
            'Target="word/document.xml"/></Relationships>'
        )
        output = BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            archive.writestr(ZipInfo("[Content_Types].xml"), content_types)
            archive.writestr(ZipInfo("_rels/.rels"), relationships)
            archive.writestr(ZipInfo("word/document.xml"), document)
        return output.getvalue()
