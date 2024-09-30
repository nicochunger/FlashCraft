# FlashCraft
# An Anki Flashcard Generator using AI

This is a personal project to test LLMs for an application that is useful to me and where the API is needed and connot be done with the usual chat interfaces.

## Application Overview
This application automates the process of creating Anki flashcards from different types of content like educational YouTube videos, podcasts, audio files, articles, websites, etc. It extracts the text or transcript from the content, summarizes it to capture key concepts, generates flashcards based on this information, and uploads these cards directly to an Anki deck using the AnkiConnect API. The application can be triggered via email, allowing you to send links from any device, including your phone.

## How the Application Works

1. **Email Trigger:**
   - The application is set up to monitor a specific email account for new messages. When you want to create flashcards from a piece of content, you send an email to this account with the link.
   - The application uses the IMAP protocol to log in to the email account and check for new, unread emails.

2. **Transcript Extraction:**
   - Once a YouTube link is identified, the application uses the YouTube Data API (or a similar tool) to extract the transcript of the video. If the video has no transcript, the process stops here.
   - If the content is a podcast or audio file it uses whisper to transcribe it.

3. **Flashcard Generation using OpenAI API:**
   - The extracted transcript is processed using the OpenAI API, which summarizes the content and identifies key concepts.
   - The application then generates flashcards in a question-answer format, capturing the essential information from the content.

4. **Upload to Anki:**
   - The generated flashcards are formatted according to Anki’s structure and uploaded to a specific deck in your Anki account using the AnkiConnect API.
   - This allows you to review the content through Anki's spaced repetition system.

5. **Automation via Cron Job:**
   - A cron job is set up on your Linux system to run the script at regular intervals (e.g., four times a day). This automation ensures that any new emails with YouTube links are processed without manual intervention.
