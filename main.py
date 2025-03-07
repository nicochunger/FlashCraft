# /// script
# dependencies = [
#   "requests<3",
#   "google-api-python-client",
#   "youtube-transcript-api",
#   "openai",
#   "python-dotenv",
# ]
# ///

## NEW NAME: FlashCraft

import argparse
import email
import imaplib
import json
import logging
import math
import os
import pathlib
import re
import subprocess
import time
from email.header import decode_header
from threading import Lock

# import json_repair
import requests
import tiktoken
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from openai import OpenAI
from werkzeug.utils import secure_filename

from content_types.books import process_book_attachment
from content_types.youtube import (
    extract_transcript_from_youtube,
    get_youtube_video_details,
)

# Get the script's directory for absolute path resolution
SCRIPT_DIR = pathlib.Path(__file__).parent.absolute()
DOWNLOADS_DIR = SCRIPT_DIR / "downloads"
PROMPTS_DIR = SCRIPT_DIR / "prompts"
TEMPLATES_DIR = SCRIPT_DIR / "templates"

# Load environment variables from .env file in script directory
load_dotenv(SCRIPT_DIR / ".env")
# Get environment variables
IMAP_SERVER = os.getenv("IMAP_SERVER")
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
YOUTUBE_DATA_API_KEY = os.getenv("YOUTUBE_DATA_API_KEY")
ANKI_CONNECT_URL = os.getenv("ANKI_CONNECT_URL")
ANKI_API_KEY = os.getenv("ANKI_API_KEY")

# Parse command-line arguments
parser = argparse.ArgumentParser(description="FlashCraft: Generate flashcards content.")
parser.add_argument(
    "-m",
    "--model",
    type=str,
    default="gpt-4o",
    help="The LLM model to use for OpenAI API calls.",
    choices=["gpt-4o", "gpt-4o-mini"],
)
parser.add_argument(
    "--mode",
    type=str,
    default="cli",
    choices=["cli", "web"],
    help="Run mode: 'cli' for command line (email checking) or 'web' for web interface",
)
args = parser.parse_args()

# Use the model argument in the openai_call function
LLM_MODEL = args.model

# Create an instance of the OpenAI client
OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY)

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set the logging level
    format="%(asctime)s - %(levelname)s - %(message)s",  # Log format
)

# Define the list of supported ebook file extensions
# SUPPORTED_TEXT_FILE_EXTENSIONS = (
#     ".azw",
#     ".azw3",
#     ".cbz",
#     ".cbr",
#     ".cbc",
#     ".chm",
#     ".docx",
#     ".epub",
#     ".fb2",
#     ".html",
#     ".htmlz",
#     ".lit",
#     ".lrf",
#     ".mobi",
#     ".odt",
#     # ".pdf",
#     ".pdb",
#     ".pml",
#     ".prc",
#     ".rb",
#     ".rtf",
#     ".snb",
#     ".tcr",
#     ".txt",
#     ".txtz",
# )


def check_email():
    """Check the email inbox for unread emails containing YouTube links or book attachments.

    Returns:
        dict: A dictionary with keys 'youtube' and 'books'.
            'youtube' is a list of YouTube video IDs extracted from unread emails.
            'books' is a list of file paths to downloaded .epub or .mobi files.
    """
    logging.info("Checking email for content...")

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
    book_file_paths = []
    documents_file_paths = []

    for email_id in email_ids:
        # Fetch the email by ID
        status, msg_data = mail.fetch(email_id, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])

        # Get the email subject
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding if encoding else "utf-8")

        # Check if the email contains a YouTube link or book attachments
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    body = part.get_payload(decode=True).decode()
                    video_ids = re.findall(pattern, body)
                    youtube_video_ids.extend(video_ids)
                elif (
                    part.get_content_maintype() == "application" and part.get_filename()
                ):
                    filename = part.get_filename()
                    if filename.lower().endswith(("epub", "mobi", ".pdf")):
                        filepath = DOWNLOADS_DIR / filename
                        if not DOWNLOADS_DIR.exists():
                            DOWNLOADS_DIR.mkdir()
                        with open(filepath, "wb") as f:
                            f.write(part.get_payload(decode=True))
                        # Check if the file is a book or a document
                        if filename.lower().endswith((".epub", ".mobi")):
                            book_file_paths.append(filepath)
                        else:
                            documents_file_paths.append(filepath)
                    else:
                        logging.info(
                            f"Unsupported file format for attachment: {filename}"
                        )
        else:
            body = msg.get_payload(decode=True).decode()
            video_ids = re.findall(pattern, body)
            youtube_video_ids.extend(video_ids)

    # Close the connection and logout
    mail.close()
    mail.logout()

    logging.info(
        f"Found {len(email_ids)} unread emails with:"
        f"\n\t{len(youtube_video_ids)} YouTube links."
        f"\n\t{len(book_file_paths)} books."
        f"\n\t{len(documents_file_paths)} documents."
    )
    # Remove duplicate video IDs
    unique_youtube_video_ids = list(set(youtube_video_ids))

    # If there were duplicate video IDs, log the number of duplicates removed
    if len(unique_youtube_video_ids) < len(youtube_video_ids):
        logging.info(
            f"Removed {len(youtube_video_ids) - len(unique_youtube_video_ids)} duplicate video IDs."
        )
    return {
        "youtube": unique_youtube_video_ids,
        "books": book_file_paths,
        "documents": documents_file_paths,
    }


def openai_call(prompt, model=LLM_MODEL):
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
    with open(PROMPTS_DIR / "summarization.txt", "r") as file:
        prompt = file.read().strip()

    full_prompt = f"{prompt}: {transcript}"

    message = openai_call(full_prompt.replace("\n", ""))

    # Return the summary
    return message


def calc_num_questions(num_tokens):
    """Calculate the number of questions to generate based on the number of tokens.

    Args:
        num_tokens (int): The number of tokens in the text.

    Returns:
        int: The number of questions to generate.
    """
    return round(math.sqrt(num_tokens) / 25)


def generate_flashcards(text, language="english", custom_num_questions=None):
    """Generate flashcards from a text.

    Args:
        text (str): The input text.
        language (str): The language for the flashcards.
        custom_num_questions (int, optional): Custom number of questions to generate.

    Returns:
        dict: A JSON object containing the generated flashcards.
    """
    logging.info("Generating flashcards from the input text...")

    with open(PROMPTS_DIR / "flashcard_generation.txt", "r") as file:
        prompt = file.read().strip()

    flashcards_prompt = f"{prompt}\n\n{text}"
    flashcards_prompt = flashcards_prompt.replace("[LANGUAGE]", language)

    # Use custom number of questions if provided, otherwise calculate based on tokens
    if custom_num_questions is not None:
        num_questions = custom_num_questions
    else:
        num_tokens = len(flashcards_prompt.split())
        encoding = tiktoken.encoding_for_model(LLM_MODEL)
        num_tokens = len(encoding.encode(flashcards_prompt))
        logging.info(f"Number of tokens: {num_tokens}")
        num_questions = calc_num_questions(num_tokens)

    logging.info(f"Number of questions to generate: {num_questions}")
    flashcards_prompt = flashcards_prompt.replace("[NUM_QUESTIONS]", str(num_questions))

    # Call the OpenAI API to generate flashcards
    flashcards = openai_call(flashcards_prompt, model="gpt-4o-mini")

    # Clean the output
    flashcards = (
        flashcards.replace("```json\n", "").replace("```", "").replace("\n", "").strip()
    )

    # Convert to json
    flashcards_json = json.loads(flashcards)

    # Improve the flashcards
    logging.info("Improving flashcards quality...")
    improved_flashcards = improve_flashcards(flashcards_json)
    logging.info(
        f"Improved flashcards: {len(improved_flashcards)} cards after improvement."
    )

    return improved_flashcards


def generate_tags(text):
    """Generate tags from a given text using the OpenAI API.

    Args:
        text (str): The text to generate tags from.

    Returns:
        list: A list of generated tags.
    """
    with open(PROMPTS_DIR / "tags_generation.txt", "r") as file:
        prompt = file.read().strip()

    tags_prompt = f"{prompt}\n\n{text}"

    # Call the OpenAI API to generate tags
    tags_response = openai_call(tags_prompt)

    # Convert the response to a list of tags
    tags = tags_response.split(" ")

    return tags


def save_to_file(content: str, path: str = ""):
    """Save content to a file with a title derived from the content."""
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
    save_path = SCRIPT_DIR / path if path else SCRIPT_DIR
    with open(save_path / f"{title}.md", "w") as file:
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

    if not deck_exists(deck_name):
        create_deck(deck_name)

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
    response = requests.post(ANKI_CONNECT_URL, json=payload)

    # Check the response
    if response.status_code == 200:
        result = response.json()
        if not ("error" in result and result["error"] is None):
            print(f"Error syncing media: {result['error']}")
    else:
        print(f"HTTP Error: {response.status_code}")


def improve_flashcards(flashcards):
    """Improve the generated flashcards by removing duplicates and overlapping information.

    Args:
        flashcards (dict): The generated flashcards.

    Returns:
        dict: The improved flashcards.
    """
    logging.info("Improving flashcards quality...")

    # Create the review prompt
    review_prompt = """Review these flashcards and improve them by:
    1. Removing any duplicate information between cards
    2. Reformulating questions that cover similar content to make them more distinct
    3. Ensuring questions are distinct and cover different aspects
    4. Maintaining essential information
    5. Making questions more specific and clear
    
    Important: Keep the same number of flashcards as the original.
    
    Return only the improved JSON array of flashcards.
    
    Original flashcards:
    """

    # Convert flashcards to string and send for review
    flashcards_str = json.dumps(flashcards, indent=2)
    improved_flashcards = openai_call(review_prompt + flashcards_str, model="gpt-4o")

    # Clean and parse the response
    improved_flashcards = (
        improved_flashcards.replace("```json\n", "")
        .replace("```", "")
        .replace("\n", "")
        .strip()
    )

    return json.loads(improved_flashcards)


def process_youtube_videos(video_ids):
    """Process YouTube videos by extracting the transcript, generating flashcards, and uploading them to Anki.

    Args:
        video_ids (list): The list of YouTube video IDs to process.
    """
    logging.info(f"Processing {len(video_ids)} YouTube videos...")
    total_videos = len(video_ids)

    for idx, video_id in enumerate(video_ids):
        video_progress_base = (idx / total_videos) * 100
        video_progress_step = 100 / total_videos

        logging.info("----------------------------------")
        logging.info(f"Processing video with ID: {video_id}")
        update_progress(
            f"Processing video {idx + 1} of {total_videos}...", video_progress_base
        )

        # Get the title and channel name of the YouTube video
        update_progress(
            f"Fetching video details for video {idx + 1}...",
            video_progress_base + video_progress_step * 0.2,
        )
        video_title, channel_name = get_youtube_video_details(
            video_id, YOUTUBE_DATA_API_KEY
        )
        logging.info(f"Channel name: {channel_name}")
        logging.info(f"Video title: {video_title}")

        # Get the transcript for the YouTube video
        update_progress(
            f"Extracting transcript for: {video_title}...",
            video_progress_base + video_progress_step * 0.4,
        )
        transcript = extract_transcript_from_youtube(video_id)

        # Generate flashcards from the transcript
        update_progress(
            f"Generating flashcards for: {video_title}...",
            video_progress_base + video_progress_step * 0.6,
        )
        flashcards = generate_flashcards(transcript)
        logging.info(f"Created {len(flashcards)} flashcards for the video.")

        # Generate tags for the flashcards
        update_progress(
            f"Generating tags for: {video_title}...",
            video_progress_base + video_progress_step * 0.8,
        )
        tags = generate_tags(flashcards)
        logging.info(f"Generated {len(tags)} tags: {tags}.")

        # Upload the flashcards to Anki
        update_progress(
            f"Uploading flashcards for: {video_title}...",
            video_progress_base + video_progress_step * 0.9,
        )
        for i, card in enumerate(flashcards):
            card_progress = (i / len(flashcards)) * (video_progress_step * 0.1)
            update_progress(
                f"Uploading card {i + 1} of {len(flashcards)} for: {video_title}...",
                video_progress_base + video_progress_step * 0.9 + card_progress,
            )
            # Add channel name and video title as a header to the card
            front = (
                f"<h1>{channel_name}</h1><h2>{video_title}</h2><br>{card['question']}"
            )
            add_anki_card(
                f"YouTube::{channel_name}",
                "Basic",
                front,
                card["answer"],
                tags=tags,
            )
        logging.info("Uploaded flashcards to Anki.")


def process_books(books):
    """
    Process a book files by converting them to text, generating flashcards, and uploading them to Anki.

    Args:
        books (list): The list of paths to the book files.
    """
    logging.info(f"Processing {len(books)} new books...")
    for ebook_path in books:
        try:
            # Convert ebook to text
            book_content = process_book_attachment(ebook_path)

            # Generate flashcards from the text
            flashcards = generate_flashcards(book_content)
            logging.info(f"Created {len(flashcards)} flashcards from the book.")

            # Generate tags for the flashcards
            tags = generate_tags(flashcards)
            logging.info(f"Generated tags: {tags}.")

            # Use the book filename to infer the author and title
            author_name = openai_call(
                f"Return just the author name of the book inferred from this filename: {ebook_path}. The answer should ONLY contain the name of the author and nothing else.",
                model="gpt-4o-mini",
            )
            logging.info(f"Author name: {author_name}")
            book_title = openai_call(
                f"Return just the title of the book inferred from this filename: {ebook_path}. The answer should ONLY contain the name of the book and nothing else.",
                model="gpt-4o-mini",
            )
            logging.info(f"Book title: {book_title}")

            # Upload the flashcards to Anki
            for card in flashcards:
                front = (
                    f"<h1>{author_name}</h1><h2>{book_title}</h2><br>{card['question']}"
                )
                add_anki_card(
                    f"Books::{author_name}",
                    "Basic",
                    front,
                    card["answer"],
                    tags=tags,
                )
            logging.info(
                f"Uploaded flashcards for book '{author_name} - {book_title}' to Anki."
            )

        except Exception as e:
            logging.error(f"Error processing book '{ebook_path}': {e}")


def process_documents(documents):
    """
    Process a document files by converting them to text, generating flashcards, and uploading them to Anki.

    Args:
        documents (list): The list of paths to the document files.
    """
    logging.info(f"Processing {len(documents)} new documents...")
    for document_path in documents:
        try:
            # Convert document to text
            text_file_path = document_path.rsplit(".", 1)[0] + ".txt"
            subprocess.run(["pdftotext", document_path, text_file_path], check=True)
            with open(text_file_path, "r") as file:
                document_content = file.read()

            # Generate flashcards from the text
            flashcards = generate_flashcards(document_content)
            logging.info(f"Created {len(flashcards)} flashcards from the document.")

            # Generate tags for the flashcards
            tags = generate_tags(flashcards)
            logging.info(f"Generated tags: {tags}.")

            # Use the document filename to infer the topic
            topic = openai_call(
                f"Return the topic or title of this document inferred from this filename: {document_path}."
                f"\nAnd these flashcards:\n{flashcards}."
                "\n\nThe answer should ONLY contain the topic or title and nothing else.",
                model="gpt-4o-mini",
            )
            logging.info(f"Topic: {topic}")

            # Upload the flashcards to Anki
            for card in flashcards:
                front = f"<h1>{topic}</h1><br>{card['question']}"
                add_anki_card(
                    f"Documents::{topic}",
                    "Basic",
                    front,
                    card["answer"],
                    tags=tags,
                )
            logging.info(f"Uploaded flashcards for document '{topic}' to Anki.")

        except Exception as e:
            logging.error(f"Error processing document '{document_path}': {e}")


app = Flask(__name__, template_folder=str(TEMPLATES_DIR))
app.config["UPLOAD_FOLDER"] = str(DOWNLOADS_DIR)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size

# Add global progress tracking
progress_data = {"message": "", "percentage": 0, "complete": False}
progress_lock = Lock()


def update_progress(message, percentage=None):
    """Update the progress data with a new message and percentage."""
    with progress_lock:
        progress_data["message"] = message
        if percentage is not None:
            progress_data["percentage"] = percentage
        progress_data["complete"] = False
    # Add a small delay to make progress visible
    time.sleep(0.5)  # 500ms delay


def reset_progress():
    """Reset the progress data."""
    with progress_lock:
        progress_data["message"] = ""
        progress_data["percentage"] = 0
        progress_data["complete"] = True


# Add progress endpoint
@app.route("/progress")
def get_progress():
    """Return the current progress data."""
    with progress_lock:
        return jsonify(progress_data)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/process_youtube", methods=["POST"])
def process_youtube():
    try:
        reset_progress()
        youtube_links = request.form.get("youtube_links", "").strip()

        if not youtube_links:
            return jsonify(
                {"success": False, "message": "Please provide YouTube links"}
            )

        pattern = (
            r"(?:https?://(?:www\.)?youtube\.com/watch\?v=|https?://youtu\.be/)([\w-]+)"
        )
        video_ids = re.findall(pattern, youtube_links)

        if not video_ids:
            return jsonify(
                {"success": False, "message": "No valid YouTube links found"}
            )

        update_progress("Starting YouTube video processing...", 0)
        process_youtube_videos(video_ids)
        reset_progress()
        return jsonify(
            {"success": True, "message": "Flashcards generated successfully!"}
        )

    except Exception as e:
        reset_progress()
        return jsonify({"success": False, "message": str(e)})


@app.route("/process_text", methods=["POST"])
def process_text():
    try:
        reset_progress()
        raw_text = request.form.get("raw_text", "").strip()
        deck_name = request.form.get("deck_name", "").strip()
        num_questions = request.form.get("num_questions", "").strip()

        if not raw_text or not deck_name:
            return jsonify(
                {"success": False, "message": "Please provide text and deck name"}
            )

        try:
            num_questions = int(num_questions) if num_questions else None
            if num_questions is not None and (num_questions < 1 or num_questions > 100):
                raise ValueError("Number of questions must be between 1 and 100")
        except ValueError as e:
            return jsonify({"success": False, "message": str(e)})

        update_progress("Generating flashcards...", 20)
        flashcards = generate_flashcards(raw_text, custom_num_questions=num_questions)

        update_progress("Generating tags...", 40)
        tags = generate_tags(flashcards)

        update_progress("Uploading to Anki...", 60)
        for i, card in enumerate(flashcards):
            percentage = 60 + (i / len(flashcards) * 40)
            update_progress(
                f"Uploading card {i + 1} of {len(flashcards)}...", percentage
            )
            add_anki_card(
                deck_name, "Basic", card["question"], card["answer"], tags=tags
            )

        reset_progress()
        return jsonify(
            {
                "success": True,
                "message": f"Generated and improved {len(flashcards)} flashcards successfully!",
            }
        )

    except Exception as e:
        reset_progress()
        return jsonify({"success": False, "message": str(e)})


@app.route("/process_document", methods=["POST"])
def process_document():
    try:
        reset_progress()
        if "document" not in request.files:
            return jsonify({"success": False, "message": "No file uploaded"})

        file = request.files["document"]
        deck_name = request.form.get("deck_name", "").strip()

        if not file.filename or not deck_name:
            return jsonify(
                {"success": False, "message": "Please provide a file and deck name"}
            )

        filename = secure_filename(file.filename)
        filepath = DOWNLOADS_DIR / filename
        file.save(filepath)

        if filename.lower().endswith((".epub", ".mobi")):
            update_progress("Processing book...", 20)
            process_books([filepath])
        elif filename.lower().endswith(".pdf"):
            update_progress("Processing document...", 20)
            process_documents([filepath])
        else:
            return jsonify({"success": False, "message": "Unsupported file format"})

        reset_progress()
        return jsonify(
            {"success": True, "message": "Flashcards generated successfully!"}
        )

    except Exception as e:
        reset_progress()
        return jsonify({"success": False, "message": str(e)})


def ensure_anki_running():
    """Ensure Anki is running and ready.

    Returns:
        tuple: (bool, subprocess.Popen) - Success status and Anki process if started
    """
    # Set DISPLAY environment variable if not set (for cron jobs)
    if "DISPLAY" not in os.environ:
        os.environ["DISPLAY"] = ":0"

    # Check if Anki is already running
    try:
        anki_running = subprocess.run(
            ["pgrep", "-f", "anki"], capture_output=True, text=True
        ).stdout.strip()

        anki_process = None
        if not anki_running:
            # Open Anki if it's not running
            with open("anki_output.log", "w") as f:
                anki_process = subprocess.Popen(
                    ["anki"], stdout=f, stderr=f, env=dict(os.environ)
                )
            logging.info("Started Anki process")
        else:
            logging.info("Anki is already running")

        # Wait for Anki to be ready
        start_time = time.time()
        is_ready = False
        while time.time() - start_time < 30:  # Maximum wait time of 30 seconds
            try:
                response = requests.post(
                    ANKI_CONNECT_URL,
                    json={"action": "version", "version": 6},
                    timeout=5,
                )
                if response.status_code == 200:
                    is_ready = True
                    break
            except requests.RequestException:
                time.sleep(1)  # Check every 1 second

        if not is_ready:
            logging.error("Anki is not responding.")
            if anki_process:
                anki_process.kill()
            return False, None

        return True, anki_process

    except subprocess.CalledProcessError:
        logging.error("Failed to check if Anki is running")
        return False, None


def main():
    """Main function to execute the application logic."""
    # Check email for unread YouTube links or book attachments
    content = check_email()
    video_ids = content.get("youtube", [])
    books = content.get("books", [])
    documents = content.get("documents", [])

    if not any(content.values()):
        logging.info("No new YouTube links or book attachments found.")
        return

    success, anki_process = ensure_anki_running()
    if not success:
        return

    # Process content and sync
    try:
        send_anki_request("sync")

        if video_ids:
            process_youtube_videos(video_ids)
        if books:
            process_books(books)
        if documents:
            process_documents(documents)

        send_anki_request("sync")
        logging.info("Sync completed!")
    except Exception as e:
        logging.error(f"Error processing content: {e}")
    finally:
        # Only close Anki if we started it
        if anki_process:
            anki_process.kill()


if __name__ == "__main__":
    # Create upload folder if it doesn't exist
    DOWNLOADS_DIR.mkdir(exist_ok=True)

    if args.mode == "web":
        # Ensure Anki is running before starting the web server
        success, anki_process = ensure_anki_running()
        if not success:
            logging.error("Failed to start Anki. Exiting.")
            exit(1)

        try:
            # Run the Flask development server
            app.run(debug=True, port=5000)
        finally:
            # Clean up Anki process if we started it
            if anki_process:
                anki_process.kill()
    else:
        # Run in CLI mode (email checking)
        main()
