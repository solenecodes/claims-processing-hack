#!/bin/bash
# Deploy Streamlit UI to Azure Container Apps

set -e

# Load environment variables
if [ -f "/workspaces/claims-processing-hack/.env" ]; then
    source /workspaces/claims-processing-hack/.env
fi

# Configuration
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-aihack_solene}"
LOCATION="${LOCATION:-swedencentral}"
ACR_NAME="${ACR_NAME:-msagthackcrzhhhxkpkfydqa}"
CONTAINER_APP_ENV="${CONTAINER_APP_ENVIRONMENT_NAME:-msagthack-caenv-zhhhxkpkfydqa}"
UI_APP_NAME="claims-processing-ui"
IMAGE_NAME="claims-ui"
IMAGE_TAG="latest"

# API URL from Challenge 4 deployment
API_URL="${API_URL:-https://claims-processing-api.orangeforest-dfe25231.swedencentral.azurecontainerapps.io}"

echo "=========================================="
echo "Deploying Streamlit UI to Azure"
echo "=========================================="
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "ACR: $ACR_NAME"
echo "Container App: $UI_APP_NAME"
echo "API URL: $API_URL"
echo "=========================================="

# Check if logged in to Azure
echo "🔐 Checking Azure login..."
az account show > /dev/null 2>&1 || { echo "Please run 'az login' first"; exit 1; }

# Get ACR login server
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer -o tsv)
echo "📦 ACR Login Server: $ACR_LOGIN_SERVER"

# Build and push Docker image
echo ""
echo "🐳 Building Docker image..."
cd /workspaces/claims-processing-hack/challenge-5

az acr build \
    --registry $ACR_NAME \
    --resource-group $RESOURCE_GROUP \
    --image $IMAGE_NAME:$IMAGE_TAG \
    --file Dockerfile \
    .

echo "✅ Docker image built and pushed to ACR"

# Check if Container App already exists
APP_EXISTS=$(az containerapp show --name $UI_APP_NAME --resource-group $RESOURCE_GROUP --query name -o tsv 2>/dev/null || echo "")

if [ -n "$APP_EXISTS" ]; then
    echo ""
    echo "🔄 Updating existing Container App..."
    az containerapp update \
        --name $UI_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --image $ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG \
        --set-env-vars API_URL="$API_URL"
else
    echo ""
    echo "🚀 Creating new Container App..."
    az containerapp create \
        --name $UI_APP_NAME \
        --resource-group $RESOURCE_GROUP \
        --environment $CONTAINER_APP_ENV \
        --image $ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG \
        --registry-server $ACR_LOGIN_SERVER \
        --target-port 8501 \
        --ingress external \
        --cpu 0.5 \
        --memory 1.0Gi \
        --min-replicas 0 \
        --max-replicas 3 \
        --env-vars API_URL="$API_URL"
fi

# Get the application URL
echo ""
echo "🔍 Getting application URL..."
UI_URL=$(az containerapp show --name $UI_APP_NAME --resource-group $RESOURCE_GROUP --query "properties.configuration.ingress.fqdn" -o tsv)

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "🌐 Streamlit UI URL: https://$UI_URL"
echo ""
echo "📋 Test the deployment:"
echo "   1. Open https://$UI_URL in your browser"
echo "   2. Upload a claim image from challenge-0/data/images/"
echo "   3. Click 'Process Claim' to test the full pipeline"
echo ""
echo "🔧 To update the API URL:"
echo "   az containerapp update --name $UI_APP_NAME --resource-group $RESOURCE_GROUP --set-env-vars API_URL=<new-url>"
echo ""
