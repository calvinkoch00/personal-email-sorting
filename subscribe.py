import os
import requests
import msal

# Variables are injected strictly via bws run
TENANT_ID = os.getenv("ENTRA_TENANT_ID")
CLIENT_ID = os.getenv("ENTRA_CLIENT_ID")
CLIENT_SECRET = os.getenv("ENTRA_CLIENT_SECRET")

if not TENANT_ID:
    print("Error: Credentials missing in memory. Did you use 'bws run'?")
    exit(1)

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]
GRAPH_URL = "https://graph.microsoft.com/v1.0"

print("Authenticating with Microsoft Entra...")
app = msal.ConfidentialClientApplication(
    CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
)
result = app.acquire_token_silent(SCOPES, account=None) or app.acquire_token_for_client(scopes=SCOPES)

if "access_token" not in result:
    print(f"Authentication Failed: {result.get('error_description')}")
    exit(1)

token = result["access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

print("Creating Webhook Subscription...")
payload = {
    "changeType": "created",
    "notificationUrl": "https://mail.calvinkoch.ch/webhook",
    "resource": "users/mail@calvinkoch.ch/messages",
    "expirationDateTime": "2026-11-01T10:00:00.0000000Z", # Max is ~3 days (4230 minutes), we will automate renewal later
    "clientState": "secretClientValue"
}

response = requests.post(f"{GRAPH_URL}/subscriptions", headers=headers, json=payload)

if response.status_code == 201:
    print("\nSuccess! Webhook subscription created.")
    print(response.json())
else:
    print(f"\nFailed to create subscription: {response.status_code}")
    print(response.text)