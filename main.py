from fastapi import FastAPI, Request, Form, BackgroundTasks, Header, HTTPException, Body, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import uvicorn
import os
import uuid
import asyncio
import traceback

# Import modules
from downloader import download_audio
from transcriber import transcribe_audio
from notion_integration import create_notion_page, get_databases
from config_manager import config_manager
from history_manager import history_manager

app = FastAPI(title='SocialTranscriber')

# Mount static files
app.mount('/static', StaticFiles(directory='static'), name='static')

templates = Jinja2Templates(directory='templates')

@app.get('/', response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request, 'index.html')

@app.get('/local', response_class=HTMLResponse)
async def read_local(request: Request):
    return templates.TemplateResponse(request, 'local.html')

@app.get('/status', response_class=HTMLResponse)
async def read_status(request: Request):
    return templates.TemplateResponse(request, 'status.html')

@app.get('/settings', response_class=HTMLResponse)
async def read_settings(request: Request):
    token = config_manager.get('notion_token')
    db_id = config_manager.get('default_database_id')
    webhook_token = config_manager.get('webhook_token')
    
    obscured_token = ""
    if token:
        visible_len = 4
        if len(token) > visible_len + 4 and token.startswith("ntn_"):
            obscured_token = f"ntn_{'*' * 10}{token[-visible_len:]}" # Obscure with fixed * for neatness or actual len. Let's use fixed length of stars.
        elif len(token) > visible_len:
            obscured_token = f"{'*' * 10}{token[-visible_len:]}"
        else:
            obscured_token = "*****"

    obscured_webhook = ""
    if webhook_token:
        visible_len = 4
        if len(webhook_token) > visible_len + 7 and webhook_token.startswith("wh_sec_"):
            obscured_webhook = f"wh_sec_{'*' * 10}{webhook_token[-visible_len:]}"
        elif len(webhook_token) > visible_len:
            obscured_webhook = f"{'*' * 10}{webhook_token[-visible_len:]}"
        else:
            obscured_webhook = "*****"

    return templates.TemplateResponse(request, 'settings.html', {
        "notion_token": obscured_token,
        "database_id": db_id or "",
        "webhook_token": obscured_webhook
    })

@app.get('/api/history')
async def get_history():
    return history_manager.get_history()

@app.delete('/api/history/{req_id}')
async def delete_history(req_id: str):
    history_manager.remove_request(req_id)
    return {"status": "success", "message": "Request cancelled and removed"}

@app.get('/api/storage-files')
async def list_storage_files():
    try:
        storage_dir = config_manager.get_storage_dir()
        if not os.path.exists(storage_dir):
            return {"files": [], "storage_dir": storage_dir}
            
        ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.webm', '.mp4', '.avi', '.mkv', '.mov', '.flac', '.ogg'}
        files = []
        for entry in os.scandir(storage_dir):
            if entry.is_file() and not entry.name.startswith('.'):
                _, ext = os.path.splitext(entry.name)
                if ext.lower() in ALLOWED_EXTENSIONS:
                    stat = entry.stat()
                    files.append({
                        "name": entry.name,
                        "path": entry.path,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime
                    })
        # Sort files by modification time descending (newest first)
        files.sort(key=lambda x: x["mtime"], reverse=True)
        return {"status": "success", "files": files, "storage_dir": storage_dir}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post('/transcribe')
async def transcribe(
    request: Request,
    url: str = Form(...)
):
    # Check Server API Token if configured
    server_token = config_manager.get('server_api_token')
    if server_token:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer ') or auth_header.split(' ')[1] != server_token:
             return JSONResponse(content={'error': 'Unauthorized'}, status_code=401)

    database_id = config_manager.get('default_database_id')
    req_id = history_manager.add_request(url, 'Web UI')
    
    try:
        print(f'Processing {url}...')
        
        # 1. Download
        history_manager.update_request(req_id, 'Downloading')
        audio_path, title = await run_in_threadpool(download_audio, url)
        
        if req_id in history_manager.cancelled_tasks:
            history_manager.cancelled_tasks.remove(req_id)
            print(f'Task {req_id} cancelled during /transcribe.')
            return JSONResponse(content={'status': 'cancelled'}, status_code=200)

        # 2. Transcribe
        history_manager.update_request(req_id, 'Transcribing', title=title)
        transcription = await run_in_threadpool(transcribe_audio, audio_path)
        
        if req_id in history_manager.cancelled_tasks:
            history_manager.cancelled_tasks.remove(req_id)
            print(f'Task {req_id} cancelled during /transcribe.')
            return JSONResponse(content={'status': 'cancelled'}, status_code=200)

        history_manager.update_request(req_id, 'Transcribed', title=title, transcription=transcription)
        
        return {
            'status': 'completed', 
            'url': url,
            'title': title,
            'transcription': transcription,
            'database_id': database_id
        }
    except Exception as e:
        error_msg = f'{str(e)}'
        print(f'Error: {error_msg}')
        traceback.print_exc()
        history_manager.update_request(req_id, 'Failed', error=error_msg)
        return JSONResponse(content={'error': error_msg}, status_code=500)
async def process_local_file_bg(file_path: str, req_id: str, delete_after: bool):
    try:
        title = os.path.basename(file_path)
        history_manager.update_request(req_id, 'Transcribing', title=title)
        
        # Run Whisper transcription
        transcription = await run_in_threadpool(transcribe_audio, file_path, delete_after)
        
        if req_id in history_manager.cancelled_tasks:
            history_manager.cancelled_tasks.remove(req_id)
            print(f'Local task {req_id} cancelled.')
            return

        history_manager.update_request(req_id, 'Transcribed', title=title, transcription=transcription)

        # Clean up source file from storage directory after successful transcription
        try:
            storage_dir = config_manager.get_storage_dir()
            resolved = os.path.abspath(os.path.realpath(file_path))
            if resolved.startswith(os.path.join(storage_dir, "")) and os.path.exists(resolved):
                os.remove(resolved)
                print(f'Cleaned up source file from storage: {resolved}')
        except Exception as cleanup_err:
            print(f'Warning: Could not clean up source file {file_path}: {cleanup_err}')

    except Exception as e:
        error_msg = str(e)
        print(f'Local Transcription Error: {error_msg}')
        history_manager.update_request(req_id, 'Failed', error=error_msg)

@app.post('/api/transcribe-local')
async def transcribe_local(
    background_tasks: BackgroundTasks,
    request: Request,
    file_path: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    # Check Server API Token if configured
    server_token = config_manager.get('server_api_token')
    if server_token:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer ') or auth_header.split(' ')[1] != server_token:
             return JSONResponse(content={'error': 'Unauthorized'}, status_code=401)

    ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.webm', '.mp4', '.avi', '.mkv', '.mov', '.flac', '.ogg'}

    file_path_str = file_path.strip() if file_path else None

    # Check if a file was actually uploaded (FastAPI might pass an empty UploadFile with size 0 or empty filename)
    has_uploaded_file = file and file.filename

    if not file_path_str and not has_uploaded_file:
        return JSONResponse(content={'error': 'Either Local File Path or File Upload must be provided.'}, status_code=400)

    if file_path_str:
        # Validate file path
        storage_dir = config_manager.get_storage_dir()
        allowed_sandboxes = ["/home/admin", "/app", storage_dir]
        if os.path.exists("/mnt/nas_drive2/SocialTranscription_Storage"):
            allowed_sandboxes.append("/mnt/nas_drive2/SocialTranscription_Storage")
        if os.path.exists("/mnt/nas_pool/SocialTranscription_Storage"):
            allowed_sandboxes.append("/mnt/nas_pool/SocialTranscription_Storage")
            
        resolved_path = os.path.abspath(os.path.realpath(file_path_str))
        
        access_granted = False
        for sandbox in allowed_sandboxes:
            sandbox_prefix = os.path.join(sandbox, "")
            if resolved_path.startswith(sandbox_prefix):
                access_granted = True
                break

        if not access_granted:
            return JSONResponse(content={'error': 'Access Denied: Path must be within /home/admin, /app, or the storage folder'}, status_code=403)
        
        if not os.path.exists(resolved_path) or not os.path.isfile(resolved_path):
            return JSONResponse(content={'error': 'File not found or is not a file'}, status_code=400)
            
        _, ext = os.path.splitext(resolved_path)
        if ext.lower() not in ALLOWED_EXTENSIONS:
            return JSONResponse(content={'error': f'Unsupported file extension. Allowed extensions: {", ".join(ALLOWED_EXTENSIONS)}'}, status_code=400)

        # Register request in history
        req_id = history_manager.add_request(f"Local Path: {file_path_str}", 'Local Path')
        
        # Start transcription background task
        background_tasks.add_task(process_local_file_bg, resolved_path, req_id, False)
        
        return {'status': 'processing', 'req_id': req_id}

    else:
        # Validate uploaded file extension
        _, ext = os.path.splitext(file.filename)
        if ext.lower() not in ALLOWED_EXTENSIONS:
            return JSONResponse(content={'error': f'Unsupported file extension. Allowed extensions: {", ".join(ALLOWED_EXTENSIONS)}'}, status_code=400)

        storage_dir = config_manager.get_storage_dir()
        # Generate local target path for streaming write
        filename = f"upload_{uuid.uuid4()}{ext.lower()}"
        target_path = os.path.abspath(os.path.join(storage_dir, filename))

        # Check sandbox for safety of target path
        sandbox_prefix = os.path.join(storage_dir, "")
        if not target_path.startswith(sandbox_prefix):
            return JSONResponse(content={'error': 'Invalid target path'}, status_code=400)

        # Stream write
        try:
            with open(target_path, "wb") as buffer:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    buffer.write(chunk)
            try:
                os.chmod(target_path, 0o666)
            except Exception as e:
                print(f"Error setting permissions on uploaded file {target_path}: {e}")
        except Exception as e:
            if os.path.exists(target_path):
                os.remove(target_path)
            return JSONResponse(content={'error': f'File upload failed: {str(e)}'}, status_code=500)

        # Register request in history
        req_id = history_manager.add_request(f"Upload: {file.filename}", 'File Upload')

        # Start transcription background task (will delete target_path on completion)
        background_tasks.add_task(process_local_file_bg, target_path, req_id, True)

        return {'status': 'processing', 'req_id': req_id}


@app.post('/save-notion')
async def save_notion(
    url: str = Form(...),
    transcription: str = Form(...),
    database_id: str = Form(None),
    title: str = Form(None),
    req_id: str = Form(None)
):
    token = config_manager.get('notion_token')
    if not token:
        return JSONResponse(content={'error': 'Notion token not configured'}, status_code=400)

    db_id = database_id or config_manager.get('default_database_id')
    if not db_id:
        return JSONResponse(content={'error': 'Database ID not configured'}, status_code=400)

    try:
        page_url = await create_notion_page(db_id, url, transcription, token, title)
        if page_url:
            if req_id:
                history_manager.update_request(req_id, 'Completed', notion_url=page_url)
            return {'status': 'success', 'url': page_url}
        else:
            return JSONResponse(content={'error': 'Failed to create page'}, status_code=500)
    except Exception as e:
        return JSONResponse(content={'error': str(e)}, status_code=500)


class WebhookData(BaseModel):
    url: str

class SettingsData(BaseModel):
    notion_token: str
    database_id: str
    webhook_token: str

@app.post('/api/settings')
async def update_settings(data: SettingsData):
    updates = {"default_database_id": data.database_id}
    
    # Only update token if it doesn't contain asterisks (meaning user actually changed it)
    if data.notion_token and '*' not in data.notion_token:
        updates["notion_token"] = data.notion_token
        
    if data.webhook_token and '*' not in data.webhook_token:
        updates["webhook_token"] = data.webhook_token
        
    config_manager.save_config(updates)
    return {"status": "success"}


async def process_webhook(url: str, token: str, database_id: str, req_id: str):
    try:
        print(f'Webhook processing {url}...')
        
        # 1. Download
        history_manager.update_request(req_id, 'Downloading')
        audio_path, title = await run_in_threadpool(download_audio, url)
        
        if req_id in history_manager.cancelled_tasks:
            history_manager.cancelled_tasks.remove(req_id)
            print(f'Task {req_id} cancelled.')
            return

        # 2. Transcribe
        history_manager.update_request(req_id, 'Transcribing', title=title)
        transcription = await run_in_threadpool(transcribe_audio, audio_path)
        
        if req_id in history_manager.cancelled_tasks:
            history_manager.cancelled_tasks.remove(req_id)
            print(f'Task {req_id} cancelled.')
            return

        # Explicitly save transcription in case they want to review or manually send it later
        history_manager.update_request(req_id, 'Transcribed', title=title, transcription=transcription)

        # 3. Save to Notion
        history_manager.update_request(req_id, 'Saving to Notion')
        page_url = await create_notion_page(database_id, url, transcription, token, title)
        
        if page_url:
            history_manager.update_request(req_id, 'Completed', title=title, notion_url=page_url)
        else:
            history_manager.update_request(req_id, 'Failed', error='Failed to create Notion page')

    except Exception as e:
        error_msg = str(e)
        print(f'Webhook Error: {error_msg}')
        history_manager.update_request(req_id, 'Failed', error=error_msg)


@app.post('/webhook')
async def webhook_handler(
    data: WebhookData,
    background_tasks: BackgroundTasks,
    x_api_token: str = Header(None)
):
    url = data.url
    # Verify Token
    expected_token = config_manager.get('webhook_token')
    if not expected_token or x_api_token != expected_token:
        raise HTTPException(status_code=401, detail='Invalid or missing API token')

    if not url:
        raise HTTPException(status_code=400, detail='Missing URL')

    token = config_manager.get('notion_token')
    database_id = config_manager.get('default_database_id')

    if not token or not database_id:
        raise HTTPException(status_code=500, detail='Notion configuration missing on server')

    req_id = history_manager.add_request(url, 'Webhook')

    # Send heavy process to background so we don't hang the webhook client
    background_tasks.add_task(process_webhook, url, token, database_id, req_id)
    
    return {'status': 'processing', 'message': 'Transcriber job dispatched to background', 'req_id': req_id}


if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000, reload=True)
