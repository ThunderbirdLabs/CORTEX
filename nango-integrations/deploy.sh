#!/bin/bash

# Nango Google Drive Action Deployment Script
# Deploys the fetch-document action to Nango

set -e  # Exit on error

echo "🚀 Deploying Google Drive fetch-document action to Nango..."

# Check if Nango CLI is installed
if ! command -v nango &> /dev/null; then
    echo "❌ Nango CLI not found. Installing..."
    npm install -g nango
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please create .env with your NANGO_SECRET_KEY_DEV"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Deploy to dev environment
echo "📦 Deploying to Nango dev environment..."
nango deploy dev

echo "✅ Deployment complete!"
echo ""
echo "📝 Next steps:"
echo "1. Go to your Nango dashboard: https://app.nango.dev"
echo "2. Navigate to Google Drive integration"
echo "3. You should see the 'fetch-document' action available"
echo "4. Test it with: GET /fetch-document?id=<file-id>"
echo ""
echo "🔧 To use in your code:"
echo ""
echo "response = await http_client.get("
echo "    'https://api.nango.dev/fetch-document',"
echo "    params={'id': file_id},"
echo "    headers={"
echo "        'Authorization': f'Bearer {nango_secret}',"
echo "        'Connection-Id': connection_id,"
echo "        'Provider-Config-Key': 'google-drive'"
echo "    }"
echo ")"
echo "file_bytes = base64.b64decode(response.json())"
