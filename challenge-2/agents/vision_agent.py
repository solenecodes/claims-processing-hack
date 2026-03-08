#!/usr/bin/env python3
"""
Vision Agent - Specialized agent for analyzing crash/accident images.
Uses GPT-4.1-mini Vision capabilities to describe vehicle damage.

Usage:
    python vision_agent.py [IMAGE_PATH]
"""
import os
import sys
import base64
import json
import logging
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
MODEL_DEPLOYMENT_NAME = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")


def encode_image_to_base64(image_path: str) -> tuple[str, str]:
    """
    Encode an image file to base64 and determine its format.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Tuple of (base64_string, image_format)
    """
    with open(image_path, "rb") as f:
        image_bytes = f.read()
        base64_encoded = base64.b64encode(image_bytes).decode('utf-8')
    
    # Determine image format
    if image_path.lower().endswith(('.jpg', '.jpeg')):
        image_format = "jpeg"
    elif image_path.lower().endswith('.png'):
        image_format = "png"
    else:
        image_format = "jpeg"  # default
    
    return base64_encoded, image_format


def analyze_crash_image(image_path: str) -> str:
    """
    Analyze a crash/accident image using GPT-4.1-mini Vision.
    
    Args:
        image_path: Path to the crash image file
        
    Returns:
        JSON string containing analysis results
    """
    try:
        logger.info(f"Starting vision analysis for: {image_path}")
        
        # Validate file exists
        if not os.path.exists(image_path):
            return json.dumps({
                "status": "error",
                "error": f"File not found: {image_path}",
                "analysis": "",
                "file_path": image_path
            })
        
        # Check configuration
        if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_KEY:
            return json.dumps({
                "status": "error",
                "error": "Missing Azure OpenAI configuration (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY)",
                "analysis": "",
                "file_path": image_path
            })
        
        # Encode image
        logger.info(f"Encoding image to base64: {image_path}")
        base64_image, image_format = encode_image_to_base64(image_path)
        
        # Create OpenAI client
        client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_KEY,
            api_version=AZURE_OPENAI_API_VERSION
        )
        
        # Analyze with GPT-4.1-mini Vision
        logger.info(f"Submitting to GPT-4.1-mini Vision...")
        
        response = client.chat.completions.create(
            model=MODEL_DEPLOYMENT_NAME,
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert insurance claims analyst with advanced image analysis capabilities.
Your task is to provide detailed, professional descriptions of vehicle damage and accident scenes.

Focus on:
- Type of vehicle (make, model, color if visible)
- Location and extent of damage (scratches, dents, broken parts, etc.)
- Severity assessment (minor, moderate, severe)
- Affected areas of the vehicle (front, rear, side, etc.)
- Environmental context (road conditions, weather signs, location type)
- Any visible safety concerns or hazards
- Estimated repair complexity

Provide clear, objective descriptions useful for insurance claim processing."""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this vehicle/accident image. Provide a detailed damage assessment including: vehicle information, damage severity, affected areas, and any relevant observations for insurance processing."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_format};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000,
            temperature=0.3
        )
        
        analysis = response.choices[0].message.content
        logger.info(f"Vision analysis completed: {len(analysis)} characters")
        
        return json.dumps({
            "status": "success",
            "analysis": analysis,
            "file_path": image_path,
            "model_used": MODEL_DEPLOYMENT_NAME,
            "analysis_type": "crash_image_vision"
        })
        
    except Exception as e:
        logger.error(f"Vision analysis error: {str(e)}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "analysis": "",
            "file_path": image_path
        })


def is_crash_photo(filename: str) -> bool:
    """
    Determine if a file is likely a crash photo (not a form/statement).
    
    Crash photos: crash1.jpg, crash2.jpg, etc. (in images folder)
    Statements: crash1_front.jpeg, crash1_back.jpeg (forms with text)
    """
    name_lower = filename.lower()
    # If it has _front or _back, it's a statement form
    if '_front' in name_lower or '_back' in name_lower:
        return False
    # If it's just crashN.jpg, it's a crash photo
    if name_lower.startswith('crash') and name_lower.endswith(('.jpg', '.jpeg', '.png')):
        return True
    return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vision_agent.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    print("=== Vision Agent with GPT-4.1-mini ===\n")
    
    result_json = analyze_crash_image(image_path)
    result = json.loads(result_json)
    
    if result["status"] == "success":
        print("✅ Analysis completed successfully!\n")
        print("=== Damage Analysis ===")
        print(result["analysis"])
    else:
        print(f"❌ Error: {result['error']}")
