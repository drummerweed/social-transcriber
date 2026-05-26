import whisper
import os

# Load model once at startup (or lazy load if preferred)
# 'base' is a good balance of speed and accuracy. 'small' or 'medium' are better.
try:
    model = whisper.load_model("base")
except Exception as e:
    print(f"Warning: Could not load Whisper model at startup. It will be loaded on first request. {e}")
    model = None

def transcribe_audio(audio_path: str, delete_after: bool = True) -> str:
    """
    Transcribes the audio file at the given path using OpenAI Whisper.
    Returns the transcribed text.
    """
    global model
    if model is None:
        print("Loading Whisper model...")
        model = whisper.load_model("base")

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Check for empty or too small files (prevent "reshape tensor" error)
    if os.path.getsize(audio_path) < 1000:
        raise ValueError(f"Audio file is too small ({os.path.getsize(audio_path)} bytes). Download likely failed or content is restricted.")

    print(f"Transcribing {audio_path} (Size: {os.path.getsize(audio_path)} bytes)...")
    try:
        result = model.transcribe(audio_path, fp16=False)
    except RuntimeError as e:
        if "reshape tensor of 0 elements" in str(e).lower():
            raise Exception("Transcription failed: Audio track is empty or improperly encoded. This usually happens if the video restricts direct audio ripping.")
        raise e
    finally:
        # Cleanup: remove the audio file after transcription attempt
        if delete_after:
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except OSError as err:
                print(f"Error removing file {audio_path}: {err}")

    return result["text"]
