#!/bin/bash
# Test runner script for config module tests

set -e

echo "=================================="
echo "AI Interviewer - Config Module Tests"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${YELLOW}pytest not found. Installing dependencies...${NC}"
    pip3 install -r requirements.txt
    echo ""
fi

echo -e "${BLUE}Running Config Module Tests${NC}"
echo ""

# Run all config tests
echo -e "${GREEN}=== Running All Config Tests ===${NC}"
python3 -m pytest tests/unit/config/ tests/integration/config/ -v

echo ""
echo -e "${GREEN}=== Test Summary ===${NC}"
python3 -m pytest tests/unit/config/ tests/integration/config/ -v --tb=no -q

echo ""
echo -e "${BLUE}=== Running Unit Tests Only ===${NC}"
python3 -m pytest tests/unit/config/ -v --tb=no -q

echo ""
echo -e "${BLUE}=== Running Integration Tests Only ===${NC}"
python3 -m pytest tests/integration/config/ -v --tb=no -q

echo ""
echo -e "${GREEN}✓ Test run complete!${NC}"
