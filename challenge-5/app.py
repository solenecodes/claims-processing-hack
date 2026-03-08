#!/usr/bin/env python3
"""
Claims Processing UI
Streamlit frontend for the Claims Processing REST API
"""
import os
import json
import base64
import httpx
import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv("/workspaces/claims-processing-hack/.env")

# Page configuration
st.set_page_config(
    page_title="Claims Processing System",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1E3A8A; margin-bottom: 1rem; }
    .status-success { background-color: #D1FAE5; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #10B981; }
    .status-error { background-color: #FEE2E2; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #EF4444; }
</style>
""", unsafe_allow_html=True)

# Default API URL - Use localhost for local development
DEFAULT_API_URL = "http://localhost:8080"


def get_api_url():
    if "api_url" not in st.session_state:
        st.session_state.api_url = os.environ.get("API_URL", DEFAULT_API_URL)
    return st.session_state.api_url


def check_health(api_url: str) -> dict:
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{api_url}/health")
            return response.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}


def process_claim(api_url: str, file_content: bytes, filename: str) -> dict:
    try:
        with httpx.Client(timeout=120.0) as client:
            files = {"file": (filename, file_content, "image/jpeg")}
            response = client.post(f"{api_url}/process-claim/upload", files=files)
            return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def process_multiple_claims(api_url: str, files_data: list) -> dict:
    """Process multiple files and get a single combined result"""
    try:
        with httpx.Client(timeout=180.0) as client:
            files = [("files", (f["name"], f["content"], "image/jpeg")) for f in files_data]
            response = client.post(f"{api_url}/process-claim/upload-multiple", files=files)
            return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def display_results(data: dict):
    if not data:
        return
    
    # Vehicle Information
    if "vehicle_info" in data:
        st.subheader("🚗 Vehicle Information")
        v = data["vehicle_info"]
        cols = st.columns(4)
        cols[0].metric("Make", v.get("make", "N/A"))
        cols[1].metric("Model", v.get("model", "N/A"))
        cols[2].metric("Color", v.get("color", "N/A"))
        cols[3].metric("Year", v.get("year", "N/A"))
    
    # Damage Assessment
    if "damage_assessment" in data:
        st.subheader("💥 Damage Assessment")
        d = data["damage_assessment"]
        
        # Severity with icon
        severity = d.get("severity", "N/A")
        sev_lower = str(severity).lower()
        if "severe" in sev_lower:
            icon = "🔴"
        elif "moderate" in sev_lower:
            icon = "🟡"
        elif "minor" in sev_lower:
            icon = "🟢"
        else:
            icon = "⚪"
        
        cols = st.columns(3)
        cols[0].metric("Severity", f"{icon} {severity}")
        
        # Estimated cost - handle both numeric and text
        cost = d.get("estimated_cost", "N/A")
        if isinstance(cost, (int, float)):
            cols[1].metric("Estimated Cost", f"${cost:,.2f}")
        else:
            cols[1].metric("Estimated Cost", str(cost) if cost else "N/A")
        
        # Affected areas count
        areas = d.get("affected_areas", [])
        cols[2].metric("Affected Areas", len(areas) if isinstance(areas, list) else "N/A")
        
        # Show visual description if present
        if d.get("visual_description"):
            st.info(f"**Visual Description:** {d.get('visual_description')}")
        
        # List affected areas
        if areas and isinstance(areas, list):
            areas_text = ", ".join(str(a) for a in areas)
            st.markdown(f"**Areas:** {areas_text}")
    
    # Incident Information
    if "incident_info" in data:
        st.subheader("📋 Incident Information")
        i = data["incident_info"]
        st.markdown(f"**Date:** {i.get('date', 'N/A')} | **Location:** {i.get('location', 'N/A')}")
        st.markdown(f"**Description:** {i.get('description', 'N/A')}")


def main():
    st.markdown('<p class="main-header">🚗 Insurance Claims Processing</p>', unsafe_allow_html=True)
    st.markdown("Upload claim images to extract structured data using AI")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        api_url = st.text_input("API URL", value=get_api_url())
        st.session_state.api_url = api_url
        
        if st.button("🏥 Check Health", use_container_width=True):
            with st.spinner("Checking..."):
                result = check_health(api_url)
                if result.get("status") == "healthy":
                    st.success(f"✅ API Healthy\n\n{result.get('service', '')}")
                else:
                    st.error(f"❌ {result.get('error', 'Error')}")
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📤 Upload Claim")
        st.info("💡 Upload claim forms (crash*_front/back.jpeg) AND crash photos (crash*.jpg) for complete analysis")
        uploaded_files = st.file_uploader("Choose images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        process_btn = st.button("🚀 Process Claim", type="primary", use_container_width=True, disabled=not uploaded_files)
    
    with col2:
        if uploaded_files:
            for uploaded in uploaded_files:
                st.image(uploaded, caption=uploaded.name, width=150)
    
    # Process
    if process_btn and uploaded_files:
        st.divider()
        st.header("📋 Results")
        
        # Prepare files data
        files_data = [{"name": f.name, "content": f.getvalue()} for f in uploaded_files]
        file_names = ", ".join([f.name for f in uploaded_files])
        
        with st.spinner(f"🔄 Processing {len(uploaded_files)} images combined... (60-90 seconds)"):
            result = process_multiple_claims(st.session_state.api_url, files_data)
        
        st.subheader(f"📄 Combined Result from: {file_names}")
        if result.get("success"):
            st.markdown('<div class="status-success">✅ Claim processed successfully!</div>', unsafe_allow_html=True)
            display_results(result.get("data", {}))
            
            # Show parties involved if present
            data = result.get("data", {})
            if "parties_involved" in data:
                st.subheader("👥 Parties Involved")
                for party in data["parties_involved"]:
                    with st.container():
                        col1, col2 = st.columns([1, 2])
                        with col1:
                            st.markdown(f"### {party.get('name', 'N/A')}")
                            st.markdown(f"**Role:** {party.get('role', 'N/A')}")
                            insurance = party.get('insurance_company', 'N/A')
                            if insurance and insurance != 'None':
                                st.markdown(f"**Insurance:** {insurance}")
                        
                        with col2:
                            contact = party.get('contact')
                            if contact:
                                if isinstance(contact, dict):
                                    # Format contact dict nicely
                                    contact_parts = []
                                    if contact.get('phone'):
                                        st.markdown(f"📞 **Phone:** {contact.get('phone')}")
                                    if contact.get('email'):
                                        st.markdown(f"📧 **Email:** {contact.get('email')}")
                                    if contact.get('address'):
                                        st.markdown(f"📍 **Address:** {contact.get('address')}")
                                elif contact != 'None' and contact != 'N/A':
                                    st.markdown(f"📞 **Contact:** {contact}")
                        st.divider()
            
            # Show photo analysis if present (from Vision Agent)
            if "photo_analysis" in data:
                st.subheader("📷 Crash Photo Analysis")
                pa = data["photo_analysis"]
                
                # Handle damage_observations - can be dict or string
                damage_obs = pa.get("damage_observations")
                if damage_obs:
                    if isinstance(damage_obs, dict):
                        # Multiple vehicles with detailed observations
                        for vehicle_key, vehicle_data in damage_obs.items():
                            vehicle_name = vehicle_key.replace("_", " ").title()
                            st.markdown(f"### 🚗 {vehicle_name}")
                            
                            if isinstance(vehicle_data, dict):
                                cols = st.columns(2)
                                with cols[0]:
                                    if vehicle_data.get("damage_location"):
                                        st.markdown(f"**📍 Location:** {vehicle_data.get('damage_location')}")
                                    if vehicle_data.get("damage_extent"):
                                        st.markdown(f"**📏 Extent:** {vehicle_data.get('damage_extent')}")
                                with cols[1]:
                                    severity = vehicle_data.get("severity", "N/A")
                                    sev_lower = str(severity).lower()
                                    if "severe" in sev_lower:
                                        icon = "🔴"
                                    elif "moderate" in sev_lower:
                                        icon = "🟡"
                                    else:
                                        icon = "🟢"
                                    st.markdown(f"**⚠️ Severity:** {icon} {severity}")
                                    if vehicle_data.get("repair_complexity"):
                                        st.markdown(f"**🔧 Repair:** {vehicle_data.get('repair_complexity')}")
                            else:
                                st.write(vehicle_data)
                    else:
                        # Simple string description
                        st.markdown(f"**Observations:** {damage_obs}")
                
                # Overall severity
                if pa.get("severity_from_photos"):
                    severity = pa.get("severity_from_photos")
                    sev_lower = str(severity).lower()
                    if "severe" in sev_lower:
                        icon = "🔴"
                    elif "moderate" in sev_lower:
                        icon = "🟡"
                    else:
                        icon = "🟢"
                    st.info(f"**Overall Severity:** {icon} {severity}")
                
                # Overall repair complexity
                if pa.get("repair_complexity"):
                    st.warning(f"**🔧 Overall Repair Complexity:** {pa.get('repair_complexity')}")
            
            with st.expander("🔍 Raw JSON"):
                st.json(result)
        else:
            st.markdown(f'<div class="status-error">❌ Error: {result.get("error", "Unknown")}</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
