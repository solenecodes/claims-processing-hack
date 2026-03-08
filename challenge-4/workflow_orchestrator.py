#!/usr/bin/env python3
"""
Claims Processing Multi-Agent Workflow
Orchestrates OCR Agent and JSON Structuring Agent using sequential processing
"""
import os
import sys
import json
import logging
import asyncio
from dotenv import load_dotenv

# Azure AI Foundry SDK
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential

# Import the OCR and JSON structuring functions from challenge-2
# Handle both local development and container deployment paths
if os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'challenge-2', 'agents')):
    # Local development: challenge-2 is a sibling directory
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'challenge-2', 'agents'))
else:
    # Container deployment: challenge-2 is in the same directory as the app
    sys.path.append(os.path.join(os.path.dirname(__file__), 'challenge-2', 'agents'))
from ocr_agent import extract_text_with_ocr
from vision_agent import analyze_crash_image, is_crash_photo

# Load environment
load_dotenv(override=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
ENDPOINT = os.environ.get("AI_FOUNDRY_PROJECT_ENDPOINT")
MODEL_DEPLOYMENT_NAME = os.environ.get("MODEL_DEPLOYMENT_NAME")


async def process_claim_workflow(image_path: str) -> dict:
    """
    Multi-agent workflow that orchestrates OCR and JSON structuring.
    
    Args:
        image_path: Path to the claim image file
        
    Returns:
        Structured claim data as dictionary
    """
    logger.info(f"🔄 Starting claims processing workflow for: {image_path}")
    
    # Step 1: OCR Agent - Extract text from image
    logger.info("📸 Step 1: OCR Agent - Extracting text from image...")
    ocr_result_json = extract_text_with_ocr(image_path)
    ocr_result = json.loads(ocr_result_json)
    
    if ocr_result.get("status") == "error":
        logger.error(f"OCR failed: {ocr_result.get('error')}")
        return {
            "error": "OCR processing failed",
            "details": ocr_result.get("error"),
            "image_path": image_path
        }
    
    ocr_text = ocr_result.get("text", "")
    logger.info(f"✅ OCR Agent extracted {len(ocr_text)} characters")
    
    # Step 2: JSON Structuring Agent - Convert OCR text to structured JSON
    logger.info("📊 Step 2: JSON Structuring Agent - Converting to structured JSON...")
    
    # Create AI Project Client
    with AIProjectClient(
        endpoint=ENDPOINT,
        credential=DefaultAzureCredential(),
    ) as project_client:
        
        # Create JSON structuring agent
        agent = project_client.agents.create_version(
            agent_name="WorkflowJSONStructuringAgent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT_NAME,
                instructions="""You are a JSON structuring agent specialized in insurance claims data.

Your task:
1. Receive OCR text from claim documents
2. Structure the text into valid JSON format with these fields:
   - vehicle_info: {make, model, color, year}
   - damage_assessment: {severity, affected_areas[], estimated_cost}
   - incident_info: {date, location, description}
3. Return ONLY valid JSON, no markdown or explanations

Always return properly formatted JSON.""",
                temperature=0.1,
            ),
        )
        
        logger.info(f"Created JSON Structuring Agent: {agent.name}")
        
        # Get OpenAI client for agent responses
        openai_client = project_client.get_openai_client()
        
        # Create user query with OCR text
        user_query = f"""Please structure the following OCR text into the standardized JSON format.

---OCR TEXT START---
{ocr_text}
---OCR TEXT END---

Return only the structured JSON object."""
        
        logger.info("Sending OCR text to structuring agent...")
        
        # Get response from agent
        response = openai_client.responses.create(
            input=user_query,
            extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
        )
        
        # Extract the JSON from response
        response_text = response.output_text.strip()
        
        # Parse JSON from response
        try:
            # Remove markdown code fences if present
            if response_text.startswith("```"):
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end != -1:
                    response_text = response_text[start:end]
            
            structured_data = json.loads(response_text)
            logger.info("✅ Successfully structured OCR text into JSON")
            
            # Add metadata
            structured_data["metadata"] = {
                "source_image": image_path,
                "ocr_characters": len(ocr_text),
                "workflow": "multi-agent"
            }
            
            return structured_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return {
                "error": "JSON parsing failed",
                "details": str(e),
                "raw_response": response_text
            }


async def process_multiple_claims_workflow(file_data: list) -> dict:
    """
    Multi-agent workflow that orchestrates OCR and Vision analysis on multiple images.
    
    - Statement forms (crash*_front/back.jpeg) → OCR Agent (Mistral)
    - Crash photos (crash*.jpg) → Vision Agent (GPT-4.1-mini)
    
    Args:
        file_data: List of tuples (tmp_path, original_filename)
        
    Returns:
        Combined structured claim data as dictionary
    """
    # Handle both old format (list of paths) and new format (list of tuples)
    if file_data and isinstance(file_data[0], str):
        # Old format: just paths
        file_data = [(p, os.path.basename(p)) for p in file_data]
    
    logger.info(f"🔄 Starting multi-image claims processing workflow for {len(file_data)} images")
    
    # Categorize images using ORIGINAL filenames
    statement_files = []  # (tmp_path, original_name)
    crash_photo_files = []  # (tmp_path, original_name)
    
    for tmp_path, original_filename in file_data:
        if is_crash_photo(original_filename):
            crash_photo_files.append((tmp_path, original_filename))
            logger.info(f"   📷 Crash photo detected: {original_filename}")
        else:
            statement_files.append((tmp_path, original_filename))
            logger.info(f"   📋 Statement form detected: {original_filename}")
    
    logger.info(f"📋 Statement forms: {len(statement_files)}, 📷 Crash photos: {len(crash_photo_files)}")
    
    combined_ocr_text = ""
    combined_vision_analysis = ""
    total_ocr_chars = 0
    total_vision_chars = 0
    
    # Step 1: OCR Agent - Extract text from statement forms
    if statement_files:
        logger.info("📸 Step 1a: OCR Agent - Extracting text from statement forms...")
        for idx, (tmp_path, original_name) in enumerate(statement_files):
            logger.info(f"   OCR processing {idx+1}/{len(statement_files)}: {original_name}")
            ocr_result_json = extract_text_with_ocr(tmp_path)
            ocr_result = json.loads(ocr_result_json)
            
            if ocr_result.get("status") == "error":
                logger.warning(f"OCR failed for {original_name}: {ocr_result.get('error')}")
                continue
            
            ocr_text = ocr_result.get("text", "")
            if ocr_text:
                combined_ocr_text += f"\n\n=== Statement Form {idx+1} ({original_name}) ===\n{ocr_text}"
                total_ocr_chars += len(ocr_text)
        
        logger.info(f"✅ OCR Agent extracted {total_ocr_chars} characters from {len(statement_files)} statement forms")
    
    # Step 1b: Vision Agent - Analyze crash photos
    if crash_photo_files:
        logger.info("🔍 Step 1b: Vision Agent - Analyzing crash photos...")
        for idx, (tmp_path, original_name) in enumerate(crash_photo_files):
            logger.info(f"   Vision analyzing {idx+1}/{len(crash_photo_files)}: {original_name}")
            vision_result_json = analyze_crash_image(tmp_path)
            vision_result = json.loads(vision_result_json)
            
            if vision_result.get("status") == "error":
                logger.warning(f"Vision analysis failed for {original_name}: {vision_result.get('error')}")
                continue
            
            analysis = vision_result.get("analysis", "")
            if analysis:
                combined_vision_analysis += f"\n\n=== Crash Photo Analysis {idx+1} ({original_name}) ===\n{analysis}"
                total_vision_chars += len(analysis)
        
        logger.info(f"✅ Vision Agent analyzed {len(crash_photo_files)} crash photos ({total_vision_chars} chars)")
    
    # Check if we have any content
    if not combined_ocr_text.strip() and not combined_vision_analysis.strip():
        return {
            "error": "No content extracted from any images",
            "image_paths": image_paths
        }
    
    # Step 2: JSON Structuring Agent - Combine all information
    logger.info("📊 Step 2: JSON Structuring Agent - Converting to structured JSON...")
    
    # Create AI Project Client
    with AIProjectClient(
        endpoint=ENDPOINT,
        credential=DefaultAzureCredential(),
    ) as project_client:
        
        # Create JSON structuring agent with enhanced instructions
        agent = project_client.agents.create_version(
            agent_name="WorkflowJSONStructuringAgent",
            definition=PromptAgentDefinition(
                model=MODEL_DEPLOYMENT_NAME,
                instructions="""You are a JSON structuring agent specialized in insurance claims data.

Your task:
1. Receive OCR text from claim forms AND visual damage analysis from crash photos
2. Combine and structure ALL information into a comprehensive claim record
3. Structure into valid JSON with these fields:
   - vehicle_info: {make, model, color, year, license_plate}
   - damage_assessment: {severity, affected_areas[], estimated_cost, visual_description}
   - incident_info: {date, location, description}
   - parties_involved: [{name, role, contact, insurance_company}]
   - photo_analysis: {damage_observations, severity_from_photos, repair_complexity}
4. Return ONLY valid JSON, no markdown or explanations

Merge form data with visual analysis. The photo analysis provides real damage evidence.""",
                temperature=0.1,
            ),
        )
        
        logger.info(f"Created JSON Structuring Agent: {agent.name}")
        
        # Get OpenAI client for agent responses
        openai_client = project_client.get_openai_client()
        
        # Build combined query
        combined_content = ""
        if combined_ocr_text:
            combined_content += f"\n\n--- CLAIM FORM DATA (OCR) ---{combined_ocr_text}"
        if combined_vision_analysis:
            combined_content += f"\n\n--- CRASH PHOTO ANALYSIS (Vision) ---{combined_vision_analysis}"
        
        user_query = f"""Structure the following claim information into a unified JSON format.
Combine data from claim forms with visual damage analysis from crash photos.

{combined_content}

Return only the structured JSON object."""
        
        logger.info("Sending combined data to structuring agent...")
        
        # Get response from agent
        response = openai_client.responses.create(
            input=user_query,
            extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
        )
        
        # Extract the JSON from response
        response_text = response.output_text.strip()
        
        # Parse JSON from response
        try:
            # Remove markdown code fences if present
            if response_text.startswith("```"):
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end != -1:
                    response_text = response_text[start:end]
            
            structured_data = json.loads(response_text)
            logger.info("✅ Successfully structured combined data into JSON")
            
            # Add metadata with original filenames
            structured_data["metadata"] = {
                "source_images": [name for _, name in file_data],
                "statement_forms": [name for _, name in statement_files],
                "crash_photos": [name for _, name in crash_photo_files],
                "ocr_characters": total_ocr_chars,
                "vision_characters": total_vision_chars,
                "num_documents": len(file_data),
                "workflow": "multi-agent-ocr-vision-combined"
            }
            
            return structured_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return {
                "error": "JSON parsing failed",
                "details": str(e),
                "raw_response": response_text
            }


async def main():
    """Test the workflow with a sample image"""
    if len(sys.argv) < 2:
        print("Usage: python workflow_orchestrator.py <image_path> [image_path2 ...]")
        sys.exit(1)
    
    image_paths = sys.argv[1:]
    
    for image_path in image_paths:
        if not os.path.exists(image_path):
            print(f"❌ Error: Image not found: {image_path}")
            sys.exit(1)
    
    # Run workflow - use multi if more than one image
    if len(image_paths) > 1:
        result = await process_multiple_claims_workflow(image_paths)
    else:
        result = await process_claim_workflow(image_paths[0])
    
    print("\n" + "="*60)
    print("📊 WORKFLOW OUTPUT")
    print("="*60)
    print(json.dumps(result, indent=2))
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
