# YouTube to Anki Flashcard Generator

This is a personal project to test LLMs for an application that is useful to me and where the API is needed and connot be done with the usual chat interfaces.

## Application Overview
This application automates the process of creating Anki flashcards from educational YouTube videos. It extracts the transcript from a YouTube video, summarizes the content to capture key concepts, generates flashcards based on this information, and uploads these cards directly to an Anki deck using the AnkiConnect API. The application can be triggered via email, allowing you to send YouTube links from any device, including your phone.

## How the Application Works

1. **Email Trigger:**
   - The application is set up to monitor a specific email account for new messages. When you want to create flashcards from a YouTube video, you send an email to this account with the video link.

2. **IMAP Email Monitoring:**
   - The application uses the IMAP protocol to log in to the email account and check for new, unread emails. It scans the email content for YouTube links.

3. **YouTube Transcript Extraction:**
   - Once a YouTube link is identified, the application uses the YouTube Data API (or a similar tool) to extract the transcript of the video. If the video has no transcript, the process stops here.

4. **Flashcard Generation using OpenAI API:**
   - The extracted transcript is processed using the OpenAI API, which summarizes the content and identifies key concepts.
   - The application then generates flashcards in a question-answer format, capturing the essential information from the video.

5. **Upload to Anki:**
   - The generated flashcards are formatted according to Anki’s structure and uploaded to a specific deck in your Anki account using the AnkiConnect API.
   - This allows you to review the content through Anki's spaced repetition system.

6. **Upload to Notion:**
    - The application also uploads the video summaries to your Notion account using the Notion API.        
    - This allows you to keep a centralized, easily accessible record of the key concepts and summaries from your educational videos.

7. **Automation via Cron Job:**
   - A cron job is set up on your Linux system to run the script at regular intervals (e.g., four times a day). This automation ensures that any new emails with YouTube links are processed without manual intervention.
