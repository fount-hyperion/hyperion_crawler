#!/bin/bash

# Test Artifact Registry access
echo "Testing Artifact Registry access..."

# Get token
TOKEN=$(gcloud auth print-access-token 2>/dev/null)
if [ -z "$TOKEN" ]; then
    echo "Failed to get access token. Please run: gcloud auth login"
    exit 1
fi

echo "Token obtained successfully"

# Test repositories
REPOS=(
    "hyperion-python-packages"
    "hyperion-virtual"
)

for REPO in "${REPOS[@]}"; do
    echo ""
    echo "Testing repository: $REPO"
    URL="https://asia-northeast3-python.pkg.dev/shared-hyperion/$REPO/simple/"
    
    # Test access
    RESPONSE=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $TOKEN" "$URL")
    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    CONTENT=$(echo "$RESPONSE" | head -n -1)
    
    echo "HTTP Status: $HTTP_CODE"
    
    if [ "$HTTP_CODE" = "200" ]; then
        # Check for kardia
        if echo "$CONTENT" | grep -qi "kardia"; then
            echo "✓ Found kardia in repository!"
            echo "$CONTENT" | grep -i "kardia" | head -5
        else
            echo "✗ kardia not found in repository"
            # Show first few packages
            echo "Available packages:"
            echo "$CONTENT" | grep -o '<a href="[^"]*">' | head -5
        fi
    else
        echo "✗ Failed to access repository"
    fi
done

# Test with pip directly
echo ""
echo "Testing pip install with verbose output..."
pip index versions kardia \
    --extra-index-url https://oauth2accesstoken:${TOKEN}@asia-northeast3-python.pkg.dev/shared-hyperion/hyperion-python-packages/simple/ \
    2>&1 | head -20