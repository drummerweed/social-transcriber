from notion_client import Client
import os
from datetime import datetime

# In a real app, you might manage multiple tokens. For personal use, env var or single file is fine.
# We will use a simple mapping or environment variable for now.

async def get_notion_client(token: str):
    if not token:
        return None
    return Client(auth=token)

async def get_databases(token: str, query: str = None, limit: int = 10):
    """
    Returns a list of databases the integration has access to.
    Supports optional query and limit.
    """
    client = await get_notion_client(token)
    if not client:
        return []
    
    try:
        results = []
        # Search parameters
        params = {
            "filter": {"value": "database", "property": "object"},
            "page_size": limit
        }
        if query:
            params["query"] = query

        response = client.search(**params)
        
        for result in response.get("results", []):
            title = "Untitled"
            if "title" in result and result["title"]:
                title = result["title"][0]["plain_text"]
            results.append({"id": result["id"], "name": title})
        return results
    except Exception as e:
        print(f"Error fetching databases: {e}")
        return []

async def create_notion_page(database_id: str, url: str, transcription: str, token: str, title: str = None):
    """
    Creates a page in the specified Notion database.
    """
    client = await get_notion_client(token)
    if not client:
        raise ValueError("No Notion token provided.")

    if not title:
        title = f"Social Transcription - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    try:
        # Check if URL is a valid http/https link
        is_http_url = url.startswith("http://") or url.startswith("https://")

        # Construct the page properties
        properties = {
            "Subject": {
                "title": [
                    {
                        "text": {
                            "content": title
                        }
                    }
                ]
            }
        }
        
        if is_http_url:
            properties["URL"] = {
                "url": url
            }
        
        # Add URL if possible, otherwise just append to body
        source_rich_text = {
            "type": "text",
            "text": {
                "content": f"Source: {url}"
            }
        }
        
        if is_http_url:
            source_rich_text["text"]["link"] = {"url": url}

        children = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [source_rich_text]
                }
            },
             {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "Transcription"}}]
                }
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": transcription[:2000]} # Chunking needed for very long text
                        }
                    ]
                }
            }
        ]
        
        # If transcription is longer than 2000 chars, add more blocks
        if len(transcription) > 2000:
            remaining = transcription[2000:]
            while remaining:
                chunk = remaining[:2000]
                remaining = remaining[2000:]
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": chunk}}]
                    }
                })

        response = client.pages.create(parent={"database_id": database_id}, properties=properties, children=children)
        return response.get("url")
    except Exception as e:
        print(f"Error creating Notion page: {e}")
        raise
