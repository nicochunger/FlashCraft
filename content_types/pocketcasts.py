# import os
# import time

import requests
import whisper
from bs4 import BeautifulSoup
from tqdm import tqdm


# Function to download the MP3 file
def download_mp3(episode_url):
    """
    Downloads an MP3 file from a given episode URL.
    This function takes an episode URL, retrieves the webpage content,
    parses it to find the direct MP3 download link, and then downloads
    the MP3 file to the local filesystem.
    Args:
        episode_url (str): The URL of the episode page containing the MP3 download link.
    Returns:
        str: The filename of the downloaded MP3 file if successful, otherwise None.
    Raises:
        requests.exceptions.RequestException: If there is an issue with the HTTP request.
        IOError: If there is an issue writing the MP3 file to the local filesystem.
    """

    response = requests.get(episode_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        download_button = soup.find("a", class_="download-button")

        if download_button and "href" in download_button.attrs:
            download_link = download_button["href"]
            print(f"Direct MP3 URL: {download_link}")

            # Download the MP3 file
            mp3_response = requests.get(download_link, stream=True)
            if mp3_response.status_code == 200:
                filename = download_link.split("/")[-1].split("?")[
                    0
                ]  # Get filename from URL
                with open(filename, "wb") as f:
                    for chunk in mp3_response.iter_content(1024):
                        f.write(chunk)
                print(f"Downloaded: {filename}")
                return filename
            else:
                print("Failed to download the MP3 file.")
                print(f"Status code: {mp3_response}")
        else:
            print("MP3 link not found.")
    else:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")
    return None


# Function to transcribe the audio file using Whisper
def transcribe_audio(filename):
    """
    Transcribe an audio file using Whisper.

    Args:
        audio_file_path (str): The path to the audio file.

    Returns:
        str: The transcribed text.
    """
    model = whisper.load_model("base")
    audio = model.load_audio(filename)
    duration = model.get_duration(audio)

    # Initialize the progress bar
    with tqdm(total=duration, unit="s", desc="Transcribing") as pbar:
        result = ""
        for chunk in model.transcribe(audio, progress_callback=pbar.update):
            result += chunk["text"]
            pbar.update(chunk["duration"])

    return result
