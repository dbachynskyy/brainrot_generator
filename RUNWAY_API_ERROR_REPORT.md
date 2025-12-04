# Runway API Integration Error Report

## ✅ RESOLVED

**Solution Found**: The correct API format has been identified and implemented.

### Key Fixes Applied:
1. **X-Runway-Version**: Changed to exactly `"2024-11-06"` (not "v1", "1", etc.)
2. **Endpoint**: Changed from `/v1/generate` to `/v1/image_to_video`
3. **Payload Structure**: Updated to use `promptImage` (required) and `promptText` (optional)
4. **Ratio Format**: Changed from `"9:16"` to `"720:1280"` (exact format required)
5. **Polling Endpoint**: Changed from `/v1/generate/{id}` to `/v1/tasks/{id}`
6. **Status Values**: Updated to check for `"SUCCEEDED"`, `"FAILED"`, `"RUNNING"`, etc.

---

## Problem Summary (Original Issue)
Attempting to integrate with Runway Gen-3 Alpha API for video generation, but receiving a 400 Bad Request error indicating the `X-Runway-Version` header format is invalid.

## Error Details

### Error Message
```
HTTP 400 Bad Request
{
  "error": "The API version that was provided in the X-Runway-Version header is not valid.",
  "docUrl": "https://docs.dev.runwayml.com/api"
}
```

### API Endpoint
- **Base URL**: `https://api.dev.runwayml.com`
- **Generation Endpoint**: `POST https://api.dev.runwayml.com/v1/generate`
- **Polling Endpoint**: `GET https://api.dev.runwayml.com/v1/generate/{generation_id}`

### Request Headers
```python
headers = {
    "Authorization": f"Bearer {RUNWAY_API_KEY}",
    "Content-Type": "application/json",
    "X-Runway-Version": "v1"  # This is the problematic header
}
```

### Request Payload
```python
payload = {
    "model": "gen3a_turbo",
    "prompt": "The visual style should be vibrant and fun...",
    "ratio": "9:16",  # Vertical for Shorts
    "duration": 5,
    "watermark": False
}
```

## What We've Tried

We've attempted the following values for `X-Runway-Version` header, all resulting in the same error:

1. `"v1"` - Error: "The API version that was provided in the X-Runway-Version header is not valid."
2. `"1"` - Error: "The API version that was provided in the X-Runway-Version header is not valid."
3. `"2024-11-20"` (date format) - Error: "The API version that was provided in the X-Runway-Version header is not valid."
4. `"1.0"` - Error: "The API version that was provided in the X-Runway-Version header is not valid."

## Initial Error (Before Fixing Endpoint)
Initially, we were using `https://api.runwayml.com/v1/generate` and received:
```
HTTP 401 Unauthorized
{
  "error": "Incorrect hostname for API key",
  "details": "You passed an API key to api.runwayml.com, which is not correct. The Runway public API is available at api.dev.runwayml.com instead.",
  "docUrl": "https://docs.dev.runwayml.com/api"
}
```

This was fixed by switching to `api.dev.runwayml.com`.

## Current Status
- ✅ API endpoint corrected to `api.dev.runwayml.com`
- ✅ Authentication header format appears correct (Bearer token)
- ✅ Request payload structure seems reasonable
- ❌ `X-Runway-Version` header format is unknown/invalid

## Questions
1. What is the correct format for the `X-Runway-Version` header?
2. Is there a specific API version string we should use?
3. Are there any other required headers we're missing?
4. Is the request payload structure correct for the Runway Gen-3 Alpha API?

## Additional Context
- **Project**: Video generation pipeline for YouTube Shorts
- **Language**: Python 3.x
- **HTTP Client**: httpx (async)
- **API Documentation URL**: https://docs.dev.runwayml.com/api (requires authentication to view)

## Code Snippet
```python
async def _generate_with_runway(self, request: ProductionRequest) -> Path:
    """Generate video using Runway Gen-3 Alpha API."""
    async with httpx.AsyncClient(timeout=300.0) as client:
        headers = {
            "Authorization": f"Bearer {settings.runway_api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": "v1"  # NEED CORRECT FORMAT
        }
        
        payload = {
            "model": "gen3a_turbo",
            "prompt": prompt,
            "ratio": "9:16",
            "duration": min(int(request.script.estimated_duration or 5), 10),
            "watermark": False
        }
        
        response = await client.post(
            "https://api.dev.runwayml.com/v1/generate",
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            logger.error(f"Runway API error: {response.status_code} - {response.text}")
            # Error: {"error":"The API version that was provided in the X-Runway-Version header is not valid."}
```

## Environment
- **OS**: Windows 10/11
- **Python**: 3.x
- **API Key**: Valid (no authentication errors, only version header error)

## Next Steps Needed
1. Determine the correct `X-Runway-Version` header format
2. Verify the request payload structure matches Runway's API specification
3. Check if any additional headers are required

---

**Note**: The Runway API documentation at https://docs.dev.runwayml.com/api requires authentication/login to access, so we cannot view the exact specification without an account.

