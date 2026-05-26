from fastapi import FastAPI, Request, Form, BackgroundTasks, Header, HTTPException, Body
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
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

@app.post('/save-notion')
async def save_notion(
    url: str = Form(...),
    transcription: str = Form(...),
    database_id: str = Form(None),
    title: str = Form(None)
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
