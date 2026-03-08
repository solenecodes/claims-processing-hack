#!/usr/bin/env python3
"""
Claims Processing API Server
FastAPI wrapper for the multi-agent workflow
"""
import os
import json
import logging
import asyncio
import tempfile
import base64
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Import workflow
from workflow_orchestrator import process_claim_workflow

# Load environment
load_dotenv(override=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Claims Processing API",
    description="Multi-agent workflow for processing insurance claim images",
    version="1.0.0"
)

# Add CORS middleware to allow requests from Streamlit UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ClaimProcessRequest(BaseModel):
    image_base64: str
    filename: Optional[str] = "claim_image.jpg"


class ClaimProcessResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - health check"""
    return {
        "status": "healthy",
        "service": "Claims Processing API",
        "version": "1.0.0"
    }


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Claims Processing API",
        "version": "1.0.0"
    }


@app.post("/process-claim/upload", response_model=ClaimProcessResponse)
async def process_claim_upload(file: UploadFile = File(...)):
    """
    Process a claim image using file upload
    
    Args:
        file: Image file (JPEG, PNG, etc.)
        
    Returns:
        Structured claim data
    """
    logger.info(f"📸 Received claim image upload: {file.filename}")
    
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        logger.info(f"💾 Saved to temporary file: {tmp_path}")
        
        # Process with workflow
        result = await process_claim_workflow(tmp_path)
        
        # Clean up temporary file
        os.unlink(tmp_path)
        
        # Check for errors
        if "error" in result:
            logger.error(f"❌ Workflow error: {result.get('error')}")
            return ClaimProcessResponse(
                success=False,
                error=result.get("error"),
                data=result
            )
        
        logger.info("✅ Successfully processed claim")
        return ClaimProcessResponse(
            success=True,
            data=result
        )
        
    except Exception as e:
        logger.error(f"❌ Error processing claim: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process-claim/upload-multiple", response_model=ClaimProcessResponse)
async def process_claim_upload_multiple(files: list[UploadFile] = File(...)):
    """
    Process multiple claim images (e.g., front + back) and return combined result
    
    Args:
        files: List of image files (JPEG, PNG, etc.)
        
    Returns:
        Combined structured claim data
    """
    from workflow_orchestrator import process_multiple_claims_workflow
    
    filenames = [f.filename for f in files]
    logger.info(f"📸 Received {len(files)} claim images: {filenames}")
    
    try:
        # Save all uploaded files to temporary locations with original names mapping
        file_data = []  # List of (tmp_path, original_filename)
        for file in files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
                content = await file.read()
                tmp_file.write(content)
                file_data.append((tmp_file.name, file.filename))
        
        logger.info(f"💾 Saved {len(file_data)} files to temporary locations")
        
        # Process with combined workflow - pass original filenames
        result = await process_multiple_claims_workflow(file_data)
        
        # Clean up temporary files
        for tmp_path, _ in file_data:
            os.unlink(tmp_path)
        
        # Check for errors
        if "error" in result:
            logger.error(f"❌ Workflow error: {result.get('error')}")
            return ClaimProcessResponse(
                success=False,
                error=result.get("error"),
                data=result
            )
        
        logger.info("✅ Successfully processed combined claim")
        return ClaimProcessResponse(
            success=True,
            data=result
        )
        
    except Exception as e:
        logger.error(f"❌ Error processing claims: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process-claim/base64", response_model=ClaimProcessResponse)
async def process_claim_base64(request: ClaimProcessRequest):
    """
    Process a claim image using base64 encoded data
    
    Args:
        request: JSON with image_base64 and filename
        
    Returns:
        Structured claim data
    """
    logger.info(f"📸 Received base64 claim image: {request.filename}")
    
    try:
        # Decode base64 image
        image_data = base64.b64decode(request.image_base64)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(request.filename).suffix) as tmp_file:
            tmp_file.write(image_data)
            tmp_path = tmp_file.name
        
        logger.info(f"💾 Saved to temporary file: {tmp_path}")
        
        # Process with workflow
        result = await process_claim_workflow(tmp_path)
        
        # Clean up temporary file
        os.unlink(tmp_path)
        
        # Check for errors
        if "error" in result:
            logger.error(f"❌ Workflow error: {result.get('error')}")
            return ClaimProcessResponse(
                success=False,
                error=result.get("error"),
                data=result
            )
        
        logger.info("✅ Successfully processed claim")
        return ClaimProcessResponse(
            success=True,
            data=result
        )
        
    except Exception as e:
        logger.error(f"❌ Error processing claim: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🚀 Starting Claims Processing API on port {port}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
