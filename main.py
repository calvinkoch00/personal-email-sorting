from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse, Response
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.post("/webhook")
async def graph_webhook(request: Request, validationToken: str = Query(None)):
    if validationToken:
        logger.info("Received validation challenge from Microsoft Graph.")
        return PlainTextResponse(validationToken)
    
    try:
        payload = await request.json()
        logger.info(f"Received webhook payload: {payload}")
        # Graph API processing logic will go here
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        
    return Response(status_code=202)
