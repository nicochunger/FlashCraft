# /// script
# dependencies = [
#   "requests<3",
#   "google-api-python-client",
#   "youtube-transcript-api",
#   "openai",
#   "python-dotenv",
# ]
# ///

import email
import imaplib
import json
import logging
import os
import re
import subprocess
import time
from email.header import decode_header

import requests
from dotenv import load_dotenv
from googleapiclient.discovery import build
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
YOUTUBE_DATA_API_KEY = os.getenv("YOUTUBE_DATA_API_KEY")
ANKI_CONNECT_URL = os.getenv("ANKI_CONNECT_URL")
ANKI_API_KEY = os.getenv("ANKI_API_KEY")

# Create an instance of the OpenAI client
OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY)

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s",  # Log format
)


def check_email():
    """Check the email inbox for unread emails containing YouTube links.

    Returns:
        list: A list of YouTube video IDs extracted from unread emails.
    """
    logging.info("Checking email for YouTube links...")

    # Connect to the email server
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, PASSWORD)
    mail.select("inbox")

    # Search for all unread emails
    status, messages = mail.search(None, "UNSEEN")
    email_ids = messages[0].split()

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

    logging.info(
        f"Found {len(email_ids)} unread emails with {len(youtube_video_ids)} YouTube links."
    )
    return youtube_video_ids


def get_youtube_video_details(video_id):
    """Fetch the title and channel name of a YouTube video by its ID.

    Args:
        video_id (str): The ID of the YouTube video.

    Returns:
        tuple: A tuple containing the video title and channel name, or (None, None) if not found.
    """
    # Initialize the YouTube API client
    youtube = build("youtube", "v3", developerKey=YOUTUBE_DATA_API_KEY)

    # Make the API request
    request = youtube.videos().list(part="snippet", id=video_id)
    response = request.execute()

    # Extract video title and channel name
    if "items" in response and len(response["items"]) > 0:
        video_title = response["items"][0]["snippet"]["title"]
        channel_name = response["items"][0]["snippet"]["channelTitle"]
        return video_title, channel_name
    else:
        return None, None


def extract_transcript_from_youtube(video_id):
    """Extract the transcript from a YouTube video.

    Args:
        video_id (str): The ID of the YouTube video.

    Returns:
        str: The formatted transcript of the video as plain text.
    """
    # Get the transcript for the YouTube video
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    # Format the transcript as plain text
    formatted_transcript = TextFormatter().format_transcript(transcript)
    # Remove newlines from the formatted transcript and return it
    return formatted_transcript.replace("\n", " ")


def openai_call(prompt, model="gpt-4o-mini"):
    """Call the OpenAI API with a given prompt.

    Args:
        prompt (str): The prompt to send to the OpenAI API.
        model (str): The model to use for the API call.

    Returns:
        str: The response content from the OpenAI API.
    """
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
    """Summarize a YouTube video transcript using the OpenAI API.

    Args:
        transcript (str): The transcript of the YouTube video.

    Returns:
        str: The summary of the transcript.
    """
    logging.info("Summarizing the YouTube video transcript with OpenAI API...")

    # Define the prompt with the preparatory instruction and append the transcript
    with open("prompts/summarization.txt", "r") as file:
        prompt = file.read().strip()

    full_prompt = f"{prompt}: {transcript}"

    message = openai_call(full_prompt.replace("\n", ""))

    # Return the summary
    return message


def generate_flashcards_from_summary(summary, language="english"):
    """Generate flashcards from a summarized transcript.

    Args:
        summary (str): The summarized transcript.
        language (str): The language for the flashcards.

    Returns:
        dict: A JSON object containing the generated flashcards.
    """
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


def generate_tags(text):
    """Generate tags from a given text using the OpenAI API.

    Args:
        text (str): The text to generate tags from.

    Returns:
        list: A list of generated tags.
    """
    with open("prompts/tags_generation.txt", "r") as file:
        prompt = file.read().strip()

    tags_prompt = f"{prompt}\n\n{text}"

    # Call the OpenAI API to generate tags
    tags_response = openai_call(tags_prompt)
    print(tags_response)

    # Convert the response to a list of tags
    tags = tags_response.split(" ")

    return tags


def save_to_file(content: str, path: str = ""):
    """Save content to a file with a title derived from the content.

    Args:
        content (str): The content to save.
        path (str): The directory path to save the file in.
    """
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


def deck_exists(deck_name):
    """Check if a specified Anki deck exists.

    Args:
        deck_name (str): The name of the deck to check.

    Returns:
        bool: True if the deck exists, False otherwise.
    """
    payload = {
        "action": "deckNames",
        "version": 6,
        "key": ANKI_API_KEY,
    }
    response = requests.post("http://localhost:8765", json=payload)
    if response.status_code != 200:
        raise Exception("Failed to fetch deck names from AnkiConnect")
    deck_names = response.json().get("result", [])
    return deck_name in deck_names


def create_deck(deck_name):
    """Create a new Anki deck.

    Args:
        deck_name (str): The name of the deck to create.
    """
    payload = {
        "action": "createDeck",
        "version": 6,
        "params": {"deck": deck_name},
        "key": ANKI_API_KEY,
    }
    response = requests.post("http://localhost:8765", json=payload)
    if response.status_code != 200:
        raise Exception("Failed to create deck in AnkiConnect")


def add_anki_card(deck_name, note_type, front, back, tags=None):
    """Add a new card to an Anki deck.

    Args:
        deck_name (str): The name of the deck to add the card to.
        note_type (str): The type of the note (card).
        front (str): The front content of the card.
        back (str): The back content of the card.
        tags (list, optional): A list of tags for the card.
    """
    full_deck_name = f"YouTube Flashcards::{deck_name}"

    if not deck_exists(full_deck_name):
        create_deck(full_deck_name)

    # Define the card note structure
    note = {
        "deckName": full_deck_name,
        "modelName": note_type,
        "fields": {"Front": front, "Back": back},
        "tags": tags or [],
        "options": {"allowDuplicate": False},
        "audio": [],
        "video": [],
        "picture": [],
    }

    send_anki_request("addNote", {"note": note})


def send_anki_request(action, params=None):
    """Send a request to AnkiConnect.

    Args:
        action (str): The action to perform.
        params (dict, optional): The parameters for the action.
    """
    # Prepare the request payload
    payload = {
        "action": action,
        "version": 6,
        "params": params or {},
        "key": ANKI_API_KEY,
    }

    # Send the request to AnkiConnect
    response = requests.post("http://localhost:8765", json=payload)

    # Check the response
    if response.status_code == 200:
        result = response.json()
        if not ("error" in result and result["error"] is None):
            print(f"Error syncing media: {result['error']}")
    else:
        print(f"HTTP Error: {response.status_code}")


def main():
    """Main function to execute the application logic."""
    # Check email for unread YouTube links
    video_ids = check_email()
    if not video_ids:
        logging.info("No new YouTube links found.")
        return

    # Open Anki
    with open("anki_output.log", "w") as f:
        anki_process = subprocess.Popen(["anki"], stdout=f, stderr=f)
    # Give Anki some time to start up
    time.sleep(5)
    # Sync Anki
    send_anki_request("sync")

    # video_ids = ["pmOi0crbkEE"]
    for video_id in video_ids:
        logging.info("----------------------------------")
        logging.info(f"Processing video with ID: {video_id}")
        # Get the title and channel name of the YouTube video
        video_title, channel_name = get_youtube_video_details(video_id)
        logging.info(f"Channel name: {channel_name}")
        logging.info(f"Video title: {video_title}")
        # Get the transcript for the YouTube video
        transcript = extract_transcript_from_youtube(video_id)
        # Get the summary of the transcript
        summarized_transcript = summarize_transcript(transcript)
        # Save the summarized transcript to a file
        save_to_file(summarized_transcript, "summaries")
        # Generate flashcards from the summarized transcript
        flashcards = generate_flashcards_from_summary(summarized_transcript)
        logging.info(f"Created {len(flashcards)} flashcards for the video.")

        # Generate tags for the flashcards
        tags = generate_tags(summarized_transcript)
        logging.info(f"Generated {len(tags)} tags: {tags}.")

        # Upload the flashcards to Anki
        for card in flashcards:
            # Add channel name and video title as a header to the card
            front = (
                f"<h1>{channel_name}</h1><h2>{video_title}</h2><br>{card['question']}"
            )
            add_anki_card(channel_name, "Basic", front, card["answer"], tags=tags)
        logging.info("Uploaded flashcards to Anki.")

    # Sync the media files with Anki
    send_anki_request("sync")
    logging.info("Sync completed!")
    # Close Anki
    anki_process.kill()


if __name__ == "__main__":
    main()
