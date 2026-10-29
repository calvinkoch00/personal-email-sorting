import os
import sqlite3
import logging
import requests
import msal
from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.responses import PlainTextResponse, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Credentials injected securely via bws run in systemd
TENANT_ID = os.getenv("ENTRA_TENANT_ID")
CLIENT_ID = os.getenv("ENTRA_CLIENT_ID")
CLIENT_SECRET = os.getenv("ENTRA_CLIENT_SECRET")
USER_EMAIL = "mail@calvinkoch.ch"

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]
GRAPH_URL = "https://graph.microsoft.com/v1.0"

def init_db():
    """Create the SQLite database and rules table if they do not exist."""
    conn = sqlite3.connect("rules.db")
    conn.execute('''CREATE TABLE IF NOT EXISTS routing_rules (
                        sender_email TEXT PRIMARY KEY, 
                        target_folder_id TEXT, 
                        category TEXT, 
                        mark_read BOOLEAN
                    )''')
    conn.commit()
    conn.close()

init_db()

def get_graph_token():
    app = msal.ConfidentialClientApplication(
        CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_silent(SCOPES, account=None) or app.acquire_token_for_client(scopes=SCOPES)
    if "access_token" in result:
        return result["access_token"]
    logger.error(f"Auth failed: {result.get('error_description')}")
    raise Exception("Failed to acquire Graph API token")

def process_email(message_id: str):
    """Fetch the email details and apply routing rules."""
    token = get_graph_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # 1. Get email details to find the sender
    msg_url = f"{GRAPH_URL}/users/{USER_EMAIL}/messages/{message_id}?$select=id,sender"
    response = requests.get(msg_url, headers=headers)
    
    if response.status_code != 200:
        logger.error(f"Failed to fetch message {message_id}: {response.text}")
        return

    msg_data = response.json()
    sender_email = msg_data.get("sender", {}).get("emailAddress", {}).get("address", "").lower()
    
    if not sender_email:
        return

    # 2. Check local SQLite DB for a matching rule
    conn = sqlite3.connect("rules.db")
    cursor = conn.cursor()
    cursor.execute("SELECT target_folder_id, category, mark_read FROM routing_rules WHERE sender_email = ?", (sender_email,))
    rule = cursor.fetchone()
    conn.close()

    if rule:
        folder_id, category, mark_read = rule
        logger.info(f"Rule match for {sender_email}: Moving to {category}")

        # 3. Apply Category & Read Status
        patch_payload = {"categories": [category]}
        if mark_read:
            patch_payload["isRead"] = True
        requests.patch(f"{GRAPH_URL}/users/{USER_EMAIL}/messages/{message_id}", headers=headers, json=patch_payload)

        # 4. Move the Email
        move_payload = {"destinationId": folder_id}
        requests.post(f"{GRAPH_URL}/users/{USER_EMAIL}/messages/{message_id}/move", headers=headers, json=move_payload)

@app.post("/webhook")
async def graph_webhook(request: Request, validationToken: str = Query(None), background_tasks: BackgroundTasks = BackgroundTasks()):
    # Phase 1: Microsoft Subscription Validation
    if validationToken:
        logger.info("Validated new webhook subscription.")
        return PlainTextResponse(validationToken)
    
    # Phase 2: Process Incoming Emails
    try:
        payload = await request.json()
        for notification in payload.get("value", []):
            resource_id = notification.get("resourceData", {}).get("id")
            if resource_id:
                # Pass to background task so we can return 202 Accepted immediately
                background_tasks.add_task(process_email, resource_id)
                
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        
    return Response(status_code=202)

@app.get("/folders")
def get_folders():
    """Fetch all email folders and their IDs from Microsoft Graph."""
    try:
        token = get_graph_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{GRAPH_URL}/users/{USER_EMAIL}/mailFolders?$top=100"
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return {"error": "Failed to fetch folders", "details": response.json()}
            
        folders = response.json().get("value", [])
        
        # Return a clean dictionary mapping folder names to their IDs
        return {
            folder["displayName"]: folder["id"] for folder in folders
        }
        
    except Exception as e:
        return {"error": str(e)}