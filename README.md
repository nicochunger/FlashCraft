# FlashCraft
# An Anki Flashcard Generator using AI

This is a personal project to test LLMs for an application that is useful to me and where the API is needed and connot be done with the usual chat interfaces.

## Application Overview
This application automates the process of creating Anki flashcards from different types of content like educational YouTube videos, documents, books, podcasts, audio files, articles, etc. It extracts the text or transcript from the content, generates flashcards aimed for long term learning, and uploads these cards directly to your Anki account. The content is sent to the application via email, allowing you to send links or files from any device.

## How the Application Works

1. **Email Trigger:**
   - The application is set up to monitor a specific email account for new messages. When you want to create flashcards from a piece of content, you send an email to this account with the link or file.
   - The application uses the IMAP protocol to log in to the email account and check for new, unread emails.

2. **Content Extraction:**
   - Once a YouTube link is identified, the application uses the YouTube Data API to extract the transcript of the video. If the video has no transcript, the process stops here.
   - If the email contains a text file it extracts the raw text from it.
   - If the content is a podcast or audio file it uses speech-to-text to transcribe it (*not yet implemented*).

3. **Flashcard Generation using OpenAI API:**
   - The extracted content is processed using the OpenAI API to generate flashcards in a question-answer format, capturing the essential and key information from the content.

4. **Upload to Anki:**
   - The generated flashcards are formatted according to Anki’s structure and uploaded in an organized way to your Anki account using the AnkiConnect API.
   - This allows you to review and learn the content through Anki's spaced repetition system.

5. **(optional) Automation via Cron Job:**
   - To automate the running of **FlashCraft**, a cron job can be set up on your Linux system to run the script at regular intervals (e.g., four times a day). This automation ensures that any new emails are processed without manual intervention.


## Setup Instructions
These instructions are for me to not forget how to set everything up in case I have to start it from scratch. To get the FlashCraft application up and running, follow these steps to configure the necessary APIs and email IMAP settings.

1. **Email IMAP Configuration**

   To use a Gmail account for IMAP access, follow these steps:

   1. Enable IMAP in Gmail:

      - Go to your Gmail account settings.
      - Navigate to the "Forwarding and POP/IMAP" tab.
      - Enable IMAP access.
  
   2. Generate an App Password:

      - Go to your Google Account settings.
      - Navigate to the "Security" tab.
      - Enable 2-factor authentication if you haven't already.
      - Under "Signing in to Google," select "App passwords."
      - Generate a new app password for "Mail" and "Other (Custom name)".
      - Use this app password in your `.env` file instead of your regular Gmail password.

2. **API Configuration**

   You need to configure several APIs to use this application. Follow the steps below to set up each API:

   1. OpenAI API:

      - Sign up for an OpenAI account at OpenAI.
      - Generate an API key from the OpenAI dashboard.
      - Add the API key to your `.env` file as OPENAI_API_KEY.
   
   2. YouTube Data API:

      - Go to the Google Cloud Console.
      - Create a new project or select an existing project.
      - Enable the YouTube Data API v3 for your project.
      - Generate an API key from the "Credentials" tab.
      - Add the API key to your `.env` file as YOUTUBE_DATA_API_KEY.

   3. AnkiConnect API:

      - Install the AnkiConnect add-on in your Anki application.
      - Ensure Anki is running and AnkiConnect is enabled.
      - Add the AnkiConnect URL to your .env file as ANKI_CONNECT_URL.

3. **Environment Variables**

   Create a `.env` file in the root directory of your project and add the following environment variables:

   ```python
   IMAP_SERVER="imap.gmail.com"
   EMAIL="your-email@gmail.com"
   PASSWORD="your-app-password"
   OPENAI_API_KEY="your-openai-api-key"
   YOUTUBE_DATA_API_KEY="your-youtube-data-api-key"
   ANKI_CONNECT_URL="http://localhost:8765"
   ANKI_API_KEY="your-anki-api-key"
   ```

   Replace the placeholder values with your actual credentials and API keys.

4. **Install Dependencies**
   
   Ensure you have all the necessary dependencies installed. You can install them using pip:

   ```
   pip install requests google-api-python-client youtube-transcript-api openai python-dotenv
   ```

5. **Run the Application**

   You can run the application using the following command:

   ```
   python main.py
   ```

6. **Set Up Cron Job (Optional)**

   To automate the script execution, you can set up a cron job on your Linux system:

   1. Open the crontab editor:

      ```
      crontab -e
      ```

   2. Add a new cron job to run the script at regular intervals (e.g., four times a day):

      ```
      0 */6 * * * /usr/bin/python3 /path/to/your/project/main.py
      ```

   Replace `/path/to/your/project/main.py` with the actual path to your script.

   By following these steps, you should have the FlashCraft application up and running, ready to generate Anki flashcards from various content sources.