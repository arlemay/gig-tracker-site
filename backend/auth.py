# backend/auth.py
import os
from fastapi import Header, HTTPException, status, Depends

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

def require_admin(x_api_key: str = Header(None)):
    if not ADMIN_TOKEN:
        # If not set, allow everything (dev mode)
        return True
    if x_api_key != ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return True
