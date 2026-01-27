#!/bin/bash
# Install Elasticsearch IK Analyzer Plugin
# Used for Chinese text segmentation (ik_max_word, ik_smart)
#
# Usage:
#   1. Make sure Elasticsearch container is running
#   2. Run this script: ./scripts/install_elasticsearch_ik.sh

# Don't use set -e here, we need to handle errors manually for URL fallback

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Elasticsearch version (must match docker-compose.yml)
ES_VERSION="8.11.0"
# IK Analyzer version (must match Elasticsearch version)
# Note: For ES 8.11.0, try version 8.11.0 or latest 8.x version
# If 8.11.0 doesn't exist, try 8.10.0 or 8.12.0
IK_VERSION="8.11.0"
# Fallback version if 8.11.0 doesn't exist
IK_VERSION_FALLBACK="8.10.0"
# IK Analyzer download URL (try multiple sources)
IK_URL_1="https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v${IK_VERSION}/elasticsearch-analysis-ik-${IK_VERSION}.zip"
IK_URL_2="https://github.com/infinilabs/analysis-ik/releases/download/v${IK_VERSION}/elasticsearch-analysis-ik-${IK_VERSION}.zip"

CONTAINER_NAME="finnet-elasticsearch"

echo -e "${GREEN}Starting installation of Elasticsearch IK Analyzer plugin...${NC}"

# Check if container is running
if ! docker ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}Error: Elasticsearch container '$CONTAINER_NAME' is not running${NC}"
    echo -e "${YELLOW}Please start Elasticsearch first: docker-compose up -d elasticsearch${NC}"
    exit 1
fi

echo -e "${GREEN}Elasticsearch container is running${NC}"

# Install IK Analyzer plugin
echo -e "${GREEN}Installing IK Analyzer plugin (v${IK_VERSION})...${NC}"

# Try first URL
echo -e "${YELLOW}Trying URL 1: ${IK_URL_1}${NC}"
if docker exec "$CONTAINER_NAME" \
    bin/elasticsearch-plugin install --batch "${IK_URL_1}"; then
    echo -e "${GREEN}Successfully installed from URL 1${NC}"
else
    echo -e "${YELLOW}URL 1 failed, trying URL 2: ${IK_URL_2}${NC}"
    if docker exec "$CONTAINER_NAME" \
        bin/elasticsearch-plugin install --batch "${IK_URL_2}"; then
        echo -e "${GREEN}Successfully installed from URL 2${NC}"
    else
        echo -e "${YELLOW}Both URLs failed for version ${IK_VERSION}, trying fallback version ${IK_VERSION_FALLBACK}...${NC}"
        IK_URL_FALLBACK="https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v${IK_VERSION_FALLBACK}/elasticsearch-analysis-ik-${IK_VERSION_FALLBACK}.zip"
        if docker exec "$CONTAINER_NAME" \
            bin/elasticsearch-plugin install --batch "${IK_URL_FALLBACK}"; then
            echo -e "${GREEN}Successfully installed fallback version ${IK_VERSION_FALLBACK}${NC}"
            echo -e "${YELLOW}Note: Using IK version ${IK_VERSION_FALLBACK} with ES ${ES_VERSION} (may have minor compatibility issues)${NC}"
        else
            echo -e "${RED}All installation attempts failed. Please check:${NC}"
            echo -e "${YELLOW}1. IK Analyzer versions may not exist for ES ${ES_VERSION}${NC}"
            echo -e "${YELLOW}2. Check available versions at: https://github.com/medcl/elasticsearch-analysis-ik/releases${NC}"
            echo -e "${YELLOW}3. Or try manual installation:${NC}"
            echo -e "   docker exec -it $CONTAINER_NAME bin/elasticsearch-plugin install --batch <URL>"
            exit 1
        fi
    fi
fi

# Restart container to activate plugin
echo -e "${GREEN}Restarting Elasticsearch container to activate plugin...${NC}"
docker restart "$CONTAINER_NAME"

# Wait for Elasticsearch to start
echo -e "${YELLOW}Waiting for Elasticsearch to start...${NC}"
sleep 15

# Check if Elasticsearch is ready
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s -f http://localhost:9200/_cluster/health > /dev/null 2>&1; then
        echo -e "${GREEN}Elasticsearch is ready${NC}"
        break
    fi
    attempt=$((attempt + 1))
    echo -e "${YELLOW}Waiting for Elasticsearch... (${attempt}/${max_attempts})${NC}"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}Elasticsearch failed to start within timeout${NC}"
    exit 1
fi

# Verify plugin installation
echo -e "${GREEN}Verifying plugin installation...${NC}"
if docker exec "$CONTAINER_NAME" bin/elasticsearch-plugin list | grep -q "analysis-ik"; then
    echo -e "${GREEN}✓ IK Analyzer plugin installed successfully!${NC}"
    echo -e "${GREEN}You can verify with:${NC}"
    echo -e "  curl -X GET 'http://localhost:9200/_cat/plugins'"
else
    echo -e "${RED}✗ IK Analyzer plugin installation failed${NC}"
    exit 1
fi

echo -e "${GREEN}Installation completed!${NC}"
