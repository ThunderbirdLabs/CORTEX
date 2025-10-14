"""
API Key Authentication Middleware
"""
import os
from fastapi import Header, HTTPException


async def verify_api_key(x_api_key: str = Header(...)):
    """
    Verify API key from X-API-Key header

    Args:
        x_api_key: API key from request header

    Returns:
        str: The validated API key

    Raises:
        HTTPException: 401 if API key is invalid
    """
    # For production, use proper secret management (AWS Secrets Manager, HashiCorp Vault, etc.)
    valid_api_key = os.getenv("API_KEY", "cortex_dev_key_12345")

    if x_api_key != valid_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    return x_api_key
