import yt_dlp
import os
import whisper

DOWNLOAD_DIR = "downloads"

ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': os.path.join(DOWNLOAD_DIR, 'test_audio.%(ext)s'),
    'quiet': False,
    'no_warnings': False,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

url = "https://youtube.com/watch?v=KBgZsV-0Fdo"

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])

# find the file
filename = None
for f in os.listdir(DOWNLOAD_DIR):
    if f.startswith("test_audio") and not f.endswith('.part'):
        filename = os.path.join(DOWNLOAD_DIR, f)
        break

if filename:
    print(f"Downloaded {filename}, size: {os.path.getsize(filename)}")
    model = whisper.load_model("base")
    try:
        res = model.transcribe(filename, fp16=False)
        print("Transcription successful!")
        print(res['text'][:100])
    except Exception as e:
        print(f"Transcription failed: {e}")
else:
    print("Download failed, file not found")
