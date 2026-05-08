import yt_dlp
import os
import uuid

from config_manager import config_manager
from history_manager import history_manager

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def download_audio(url: str, req_id: str = None) -> tuple[str, str]:
    """
    Downloads audio from the given URL using yt-dlp.
    Returns a tuple containing (absolute_path_to_audio_file, video_title).
    """
    def _progress_hook(d):
        if req_id and req_id in history_manager.cancelled_tasks:
            raise Exception("Download cancelled by user")

    filename = f"{uuid.uuid4()}"
    
    # Basic options
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, filename + '.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        # Use a real browser User-Agent to avoid simple blocking
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'progress_hooks': [_progress_hook],
    }
    
    # Check for cookies file in config
    cookies_file = config_manager.get("cookies_file")
    if cookies_file and os.path.exists(cookies_file):
        ydl_opts['cookiefile'] = cookies_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Unknown Title')
        
        # yt-dlp appends the extension dynamically
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(filename) and not f.endswith('.part'):
                return os.path.abspath(os.path.join(DOWNLOAD_DIR, f)), title
                
        raise FileNotFoundError(f"Downloaded file not found for {url}")
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "instagram" in url.lower() and ("empty media response" in error_msg or "Sign in" in error_msg):
             raise Exception("Instagram blocked the download. Please ensure cookies.txt is valid.")
        elif "youtube" in url.lower() and ("Sign in" in error_msg or "confirm your age" in error_msg):
             raise Exception("YouTube blocked the download (Age/Login restricted). Consider updating cookies.txt.")
        raise Exception(f"Download failed: {error_msg}")
    except Exception as e:
        raise Exception(f"Error downloading {url}: {str(e)}")


def download_video_file(url: str, quality: str = 'best') -> tuple[str, str]:
    """
    Downloads video from the given URL using yt-dlp.
    Returns a tuple containing (absolute_path_to_video_file, video_title).
    """
    filename = f"vid_{uuid.uuid4()}"
    
    # Base options
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, filename + '.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    if quality == 'best':
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    else:
        # Try to get best video up to requested height + best audio, fallback to best overall
        ydl_opts['format'] = f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best'
        
    ydl_opts['merge_output_format'] = 'mp4'

    cookies_file = config_manager.get("cookies_file")
    if cookies_file and os.path.exists(cookies_file):
        ydl_opts['cookiefile'] = cookies_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Unknown Video')
            
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(filename) and not f.endswith('.part') and not f.endswith('.ytdl'):
                return os.path.abspath(os.path.join(DOWNLOAD_DIR, f)), title
                
        raise FileNotFoundError(f"Downloaded video file not found for {url}")
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "instagram" in url.lower() and ("empty media response" in error_msg or "Sign in" in error_msg):
             raise Exception("Instagram blocked the download. Please ensure cookies.txt is valid.")
        elif "youtube" in url.lower() and ("Sign in" in error_msg or "confirm your age" in error_msg):
             raise Exception("YouTube blocked the download (Age/Login restricted). Consider updating cookies.txt.")
        raise Exception(f"Video download failed: {error_msg}")
    except Exception as e:
        raise Exception(f"Error downloading video {url}: {str(e)}")
