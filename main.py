import email
import imaplib
import json
import logging
import os
import re
from email.header import decode_header

import requests
import urllib3
from dotenv import load_dotenv
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

# Load environment variables from .env file
load_dotenv(".env")

# Get environment variables
IMAP_SERVER = os.getenv("IMAP_SERVER")
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANKI_CONNECT_URL = os.getenv("ANKI_CONNECT_URL")

# Create an instance of the OpenAI client
OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY)

# Logging configuration
# logging.basicConfig(level=logging.INFO)


def check_email():
    # Log the start of the email checking process
    logging.info("Checking email for YouTube links...")

    # Connect to the email server
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, PASSWORD)
    mail.select("inbox")

    # Search for all unread emails
    status, messages = mail.search(None, "UNSEEN")
    email_ids = messages[0].split()

    logging.info(f"Found {len(email_ids)} unread emails.")

    # Pattern to extract YouTube video ID from either full URL or shortened URL
    pattern = (
        r"(?:https?://(?:www\.)?youtube\.com/watch\?v=|https?://youtu\.be/)([\w-]+)"
    )

    youtube_video_ids = []

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
                    video_ids = re.findall(pattern, body)
                    youtube_video_ids.extend(video_ids)
        else:
            body = msg.get_payload(decode=True).decode()
            video_ids = re.findall(pattern, body)
            youtube_video_ids.extend(video_ids)

    # Close the connection and logout
    mail.close()
    mail.logout()

    print(
        f"Found {len(email_ids)} unread emails with {len(youtube_video_ids)} YouTube links."
    )
    return youtube_video_ids


def extract_transcript_from_youtube(video_id):
    # Get the transcript for the YouTube video
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    # Format the transcript as plain text
    formatted_transcript = TextFormatter().format_transcript(transcript)
    # Remove newlines from the formatted transcript and return it
    return formatted_transcript.replace("\n", " ")


def openai_call(prompt, model="gpt-4o-mini"):
    chat_completion = OPENAI_CLIENT.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model=model,
    )

    return chat_completion.choices[0].message.content


def summarize_transcript(transcript):
    logging.info("Summarizing the YouTube video transcript with OpenAI API...")

    # Define the prompt with the preparatory instruction and append the transcript
    with open("prompts/summarization.txt", "r") as file:
        prompt = file.read().strip()

    full_prompt = f"{prompt}: {transcript}"

    message = openai_call(full_prompt.replace("\n", ""))

    # Return the summary
    return message


def generate_flashcards_from_summary(summary, language="english"):
    logging.info("Generating flashcards from the summarized transcript...")

    with open("prompts/flashcard_generation.txt", "r") as file:
        prompt = file.read().strip()

    flashcards_prompt = f"{prompt}\n\n{summary}"

    # Call the OpenAI API to generate flashcards
    flashcards = openai_call(flashcards_prompt)

    # Convert to json
    flashcards_json = json.loads(flashcards)

    # Placeholder for your OpenAI API code to generate flashcards
    return flashcards_json


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


def save_to_file(content: str, path: str = ""):
    # Save the summarized transcript to a file
    # Get the title from first line
    title = (
        content.split("\n")[0]
        .replace("#", "")
        .replace("*", "")
        .strip()
        .lower()
        .replace(" ", "_")
    )
    with open(os.path.join(path, f"{title}.md"), "w") as file:
        file.write(content)


def anki_request(action, **params):
    return {"action": action, "params": params, "version": 6, "key": "myankikey"}


def anki_invoke(action, **params):
    requestJson = json.dumps(anki_request(action, **params)).encode("utf-8")
    print("Requesting:", requestJson)
    response = json.load(
        urllib3.request.urlopen(
            urllib3.request.Request("http://127.0.0.1:8765", requestJson)
        )
    )
    print("Response:", response)
    if len(response) != 2:
        raise Exception("response has an unexpected number of fields")
    if "error" not in response:
        raise Exception("response is missing required error field")
    if "result" not in response:
        raise Exception("response is missing required result field")
    if response["error"] is not None:
        raise Exception(response["error"])
    return response["result"]


def add_anki_card(deck_name, note_type, front, back, tags=None):
    # Define the card note structure
    note = {
        "deckName": deck_name,
        "modelName": note_type,
        "fields": {"Front": front, "Back": back},
        "tags": tags or [],
        "options": {"allowDuplicate": False},
        "audio": [],
        "video": [],
        "picture": [],
    }

    # Prepare the request payload
    payload = {
        "action": "addNote",
        "version": 6,
        "params": {"note": note},
        "key": "myankikey",
    }

    # Send the request to AnkiConnect
    response = requests.post("http://localhost:8765", json=payload)

    # Check the response
    if response.status_code == 200:
        result = response.json()
        if "error" in result and result["error"] is None:
            print("Card added successfully!")
        else:
            print(f"Error adding card: {result['error']}")
    else:
        print(f"HTTP Error: {response.status_code}")


def main():
    video_ids = check_email()
    # video_ids = ["pmOi0crbkEE"]
    for video_id in video_ids:
        # Get the transcript for the YouTube video
        transcript = extract_transcript_from_youtube(video_id)
        # Get the summary of the transcript
        summarized_transcript = summarize_transcript(transcript)
        # Save the summarized transcript to a file
        save_to_file(summarized_transcript)
        # Generate flashcards from the summarized transcript
        flashcards = generate_flashcards_from_summary(summarized_transcript)
        # Upload the flashcards to Anki
        for card in flashcards:
            add_anki_card(
                "YouTube Flashcards", "Basic", card["question"], card["answer"]
            )


if __name__ == "__main__":
    main()
