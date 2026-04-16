# Social Media Transcriber & Notion Importer

A Python-based application that transcribes audio from social media and video sources (like YouTube, TikTok, etc.) using OpenAI Whisper and saves the transcriptions to a Notion database.

## 🚀 Features
- **Accurate Transcription**: Powered by the OpenAI Whisper API/model.
- **Notion Integration**: Automatically creates new pages in a Notion database with titles and formatted transcriptions.
- **Download Automation**: Handles audio extraction from URLs.
- **Configurable**: Environment-based configuration for easy secret management.
- **History Tracking**: Keeps track of processed files to avoid duplicates.

## 🛠️ Setup

### Prerequisites
- [Python](https://www.python.org/downloads/) (v3.9+)
- [FFmpeg](https://ffmpeg.org/) (required for audio processing)
- A [Notion Internal Integration Token](https://www.notion.so/my-integrations)
- A Notion Database ID

### Installation
1.  Clone the repository:
    ```bash
    git clone https://github.com/drummerweed/social-transcriber.git
    cd social-transcriber
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Configure environment variables:
    - Create a `.env` file in the root directory (copy from `.env.example`).
    - Add your `NOTION_TOKEN`, `NOTION_DATABASE_ID`, and `WEBHOOK_TOKEN`.

### Running the App
Start the application:
```bash
python main.py
```

## 🐳 Docker Deployment
You can also run this application using Docker:
```bash
docker-compose up -d
```

## 📄 License
MIT
