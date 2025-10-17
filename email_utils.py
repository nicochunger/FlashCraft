"""Utility functions for retrieving and managing email content via IMAP."""

from __future__ import annotations

import email
import imaplib
import logging
import re
from email.header import decode_header
from pathlib import Path
from typing import Dict, List, Tuple


YOUTUBE_URL_PATTERN = re.compile(
    r"(?:https?://(?:www\.)?youtube\.com/watch\?v=|https?://youtu\.be/)([\w-]+)"
)


def check_email(
    imap_server: str,
    username: str,
    password: str,
    downloads_dir: Path,
) -> Tuple[imaplib.IMAP4_SSL | None, List[Dict[str, object]]]:
    """Check the email inbox for unread content and return message payloads.

    Args:
        imap_server: IMAP server hostname.
        username: Email account username.
        password: Email account password.
        downloads_dir: Directory where attachments should be saved.

    Returns:
        A tuple containing the IMAP connection (or ``None`` if unavailable) and a list
        of message payload dictionaries with the message UID, subject, and discovered
        YouTube IDs, book files, and document files.
    """

    if not imap_server or not username or not password:
        logging.error("Missing email credentials; skipping inbox check.")
        return None, []

    logging.info("Checking email for content...")

    mail = imaplib.IMAP4_SSL(imap_server)
    mail.login(username, password)
    mail.select("inbox")

    status, data = mail.uid("search", None, "UNSEEN")
    if status != "OK":
        logging.error("Failed to search for unread emails: %s", status)
        return mail, []

    email_uids = data[0].split()

    messages_payload: List[Dict[str, object]] = []

    for uid in email_uids:
        status, msg_data = mail.uid("fetch", uid, "(BODY.PEEK[])")
        if status != "OK":
            logging.error("Failed to fetch email UID %s: %s", uid.decode(), status)
            continue

        uid_str = uid.decode()

        if not msg_data or msg_data[0] is None:
            logging.error("Empty payload when fetching email UID %s", uid_str)
            continue

        raw_email = msg_data[0][1]
        if not isinstance(raw_email, (bytes, bytearray)):
            logging.error("Unexpected payload type for email UID %s", uid_str)
            continue

        msg = email.message_from_bytes(raw_email)

        subject_header = msg.get("Subject", "")
        decoded_subject = decode_header(subject_header)
        subject_parts = []
        for part, encoding in decoded_subject:
            if isinstance(part, bytes):
                subject_parts.append(
                    part.decode(encoding if encoding else "utf-8", errors="ignore")
                )
            else:
                subject_parts.append(part)
        subject = "".join(subject_parts).strip()

        youtube_video_ids: List[str] = []
        book_file_paths: List[Path] = []
        documents_file_paths: List[Path] = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload_bytes = part.get_payload(decode=True)
                    if not payload_bytes:
                        continue
                    charset = part.get_content_charset() or "utf-8"
                    body = payload_bytes.decode(charset, errors="ignore")
                    youtube_video_ids.extend(YOUTUBE_URL_PATTERN.findall(body))
                elif (
                    part.get_content_maintype() == "application"
                    and part.get_filename()
                ):
                    filename = part.get_filename()
                    if not filename:
                        continue
                    lower_filename = filename.lower()
                    if lower_filename.endswith(("epub", "mobi", ".pdf")):
                        downloads_dir.mkdir(exist_ok=True)
                        filepath = downloads_dir / filename
                        with open(filepath, "wb") as f:
                            payload = part.get_payload(decode=True)
                            if payload is None:
                                logging.warning(
                                    "Skipping attachment with no payload from UID %s: %s",
                                    uid_str,
                                    filename,
                                )
                                continue
                            f.write(payload)
                        if lower_filename.endswith((".epub", ".mobi")):
                            book_file_paths.append(filepath)
                        else:
                            documents_file_paths.append(filepath)
                    else:
                        logging.info(
                            "Unsupported file format for attachment from UID %s: %s",
                            uid_str,
                            filename,
                        )
        else:
            payload_bytes = msg.get_payload(decode=True)
            if payload_bytes:
                charset = msg.get_content_charset() or "utf-8"
                body = payload_bytes.decode(charset, errors="ignore")
                youtube_video_ids.extend(YOUTUBE_URL_PATTERN.findall(body))

        unique_youtube_video_ids = list(set(youtube_video_ids))
        if len(unique_youtube_video_ids) < len(youtube_video_ids):
            logging.info(
                "Removed %s duplicate video IDs for email UID %s.",
                len(youtube_video_ids) - len(unique_youtube_video_ids),
                uid_str,
            )

        messages_payload.append(
            {
                "uid": uid_str,
                "subject": subject,
                "youtube": unique_youtube_video_ids,
                "books": book_file_paths,
                "documents": documents_file_paths,
            }
        )

    logging.info("Found %d unread emails to process.", len(messages_payload))

    return mail, messages_payload


def mark_email_seen(mail_client: imaplib.IMAP4_SSL | None, uid: str) -> None:
    """Mark the specified email message as seen."""
    if not mail_client:
        return
    uid_bytes = uid.encode()
    status, _ = mail_client.uid("STORE", uid_bytes, "+FLAGS", "(\\Seen)")
    if status != "OK":
        logging.error("Failed to mark email UID %s as seen: %s", uid, status)


def mark_email_unread(mail_client: imaplib.IMAP4_SSL | None, uid: str) -> None:
    """Remove the seen flag from the specified email message."""
    if not mail_client:
        return
    uid_bytes = uid.encode()
    status, _ = mail_client.uid("STORE", uid_bytes, "-FLAGS", "(\\Seen)")
    if status != "OK":
        logging.error("Failed to mark email UID %s as unread: %s", uid, status)


def close_email_connection(mail_client: imaplib.IMAP4_SSL | None) -> None:
    """Close the IMAP connection gracefully."""
    if not mail_client:
        return
    try:
        mail_client.close()
    except imaplib.IMAP4.error:
        pass
    finally:
        try:
            mail_client.logout()
        except Exception:
            pass
