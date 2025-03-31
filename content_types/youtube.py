from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter


def get_youtube_video_details(video_id, api_key):
    """Fetch the title and channel name of a YouTube video by its ID.

    Args:
        video_id (str): The ID of the YouTube video.

    Returns:
        tuple: A tuple containing the video title and channel name, or (None, None) if not found.
    """
    # Initialize the YouTube API client
    youtube = build("youtube", "v3", developerKey=api_key)

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
    transcript = YouTubeTranscriptApi.get_transcript(video_id, ["en", "es", "de", "fr"])
    # Format the transcript as plain text
    formatted_transcript = TextFormatter().format_transcript(transcript)
    # Remove newlines from the formatted transcript and return it
    return formatted_transcript.replace("\n", " ")
