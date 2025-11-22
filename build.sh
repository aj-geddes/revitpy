#!/bin/bash

# RevitPy Build Script for Linux/macOS
set -e

# Default values
CONFIGURATION="Debug"
PLATFORM="x64"
RUN_TESTS=false
CLEAN=false
RESTORE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--configuration)
            CONFIGURATION="$2"
            shift 2
            ;;
        -p|--platform)
            PLATFORM="$2"
            shift 2
            ;;
        -t|--test)
            RUN_TESTS=true
            shift
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        --restore)
            RESTORE=true
            shift
            ;;
        -h|--help)
            echo "RevitPy Build Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -c, --configuration  Build configuration (Debug|Release) [default: Debug]"
            echo "  -p, --platform       Target platform (x64|AnyCPU) [default: x64]"
            echo "  -t, --test          Run tests after build"
            echo "  --clean             Clean before build"
            echo "  --restore           Restore packages before build"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}RevitPy Build Script${NC}"
echo -e "${GREEN}===================${NC}"
echo -e "${YELLOW}Configuration: $CONFIGURATION${NC}"
echo -e "${YELLOW}Platform: $PLATFORM${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
SOLUTION_FILE="$SCRIPT_DIR/RevitPy.sln"

# Clean if requested
if [ "$CLEAN" = true ]; then
    echo -e "${YELLOW}Cleaning solution...${NC}"
    dotnet clean "$SOLUTION_FILE" --configuration "$CONFIGURATION" --verbosity minimal
    echo -e "${GREEN}Clean completed successfully${NC}"
fi

# Restore packages if requested or if this is a clean build
if [ "$RESTORE" = true ] || [ "$CLEAN" = true ]; then
    echo -e "${YELLOW}Restoring NuGet packages...${NC}"
    dotnet restore "$SOLUTION_FILE" --verbosity minimal
    echo -e "${GREEN}Restore completed successfully${NC}"
fi

# Build the solution
echo -e "${YELLOW}Building solution...${NC}"
BUILD_ARGS=(
    "build" "$SOLUTION_FILE"
    "--configuration" "$CONFIGURATION"
    "--no-restore"
    "--verbosity" "minimal"
)

if [ "$PLATFORM" = "x64" ]; then
    BUILD_ARGS+=("--arch" "x64")
fi

dotnet "${BUILD_ARGS[@]}"

echo -e "${GREEN}Build completed successfully${NC}"

# Run tests if requested
if [ "$RUN_TESTS" = true ]; then
    echo -e "${YELLOW}Running tests...${NC}"

    TEST_ARGS=(
        "test" "$SOLUTION_FILE"
        "--configuration" "$CONFIGURATION"
        "--no-build"
        "--verbosity" "normal"
        "--logger" "console;verbosity=detailed"
    )

    dotnet "${TEST_ARGS[@]}"

    echo -e "${GREEN}All tests passed${NC}"
fi

echo ""
echo -e "${GREEN}Build completed successfully!${NC}"
echo -e "${YELLOW}Output directory: ./src/{ProjectName}/bin/$CONFIGURATION/net6.0${NC}"
