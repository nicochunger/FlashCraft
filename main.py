import email
import imaplib
import os
import re
from email.header import decode_header

import openai
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get environment variables
IMAP_SERVER = os.getenv("IMAP_SERVER")
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANKI_CONNECT_URL = os.getenv("ANKI_CONNECT_URL")

# Print environment variables
print(IMAP_SERVER)
print(EMAIL)
print(PASSWORD)
print(OPENAI_API_KEY)
print(ANKI_CONNECT_URL)
print()

# Set up OpenAI API
openai.api_key = OPENAI_API_KEY


def check_email():
    # Connect to the email server
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, PASSWORD)
    mail.select("inbox")

    # Search for all unread emails
    status, messages = mail.search(None, "UNSEEN")
    email_ids = messages[0].split()

    pattern = r"(https?://(?:www\.youtube\.com/watch\?v=|youtu\.be/)[\w-]+)"

    for email_id in email_ids:
        # Fetch the email by ID
        status, msg_data = mail.fetch(email_id, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])

        # Get the email subject
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding if encoding else "utf-8")

        # Check if the email contains a YouTube link
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode()
                    youtube_links = re.findall(pattern, body)

        else:
            body = msg.get_payload(decode=True).decode()
            youtube_links = re.findall(pattern, body)

    # Close the connection and logout
    mail.close()
    mail.logout()

    return youtube_links


def extract_transcript_from_youtube(youtube_link):
    # Placeholder for your transcript extraction code
    return "Sample transcript from " + youtube_link


def generate_flashcards_from_transcript(transcript):
    # Placeholder for your OpenAI API code to generate flashcards
    return [{"question": "Sample Question", "answer": "Sample Answer"}]


def upload_to_anki(flashcards):
    # Placeholder for your AnkiConnect API code
    for card in flashcards:
        requests.post(
            ANKI_CONNECT_URL,
            json={
                "action": "addNote",
                "version": 6,
                "params": {
                    "note": {
                        "deckName": "YouTube Flashcards",
                        "modelName": "Basic",
                        "fields": {"Front": card["question"], "Back": card["answer"]},
                        "options": {"allowDuplicate": False},
                        "tags": [],
                    }
                },
            },
        )


def main():
    youtube_links = check_email()
    for link in youtube_links:
        transcript = extract_transcript_from_youtube(link)
        flashcards = generate_flashcards_from_transcript(transcript)
        upload_to_anki(flashcards)


if __name__ == "__main__":
    # main()

    check_email()

    pass
