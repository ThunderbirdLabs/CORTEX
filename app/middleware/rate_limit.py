"""
Rate Limiting Middleware
Prevents API abuse and controls costs for OpenAI-powered endpoints
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Create limiter instance
# Uses client IP address as key for rate limiting
limiter = Limiter(key_func=get_remote_address)

