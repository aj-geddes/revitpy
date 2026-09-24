#!/usr/bin/env bash
# Build the RevitPy host add-in for one or more Revit versions.
#
#   ./build.sh                 # all supported versions, Release
#   ./build.sh 2025 2026       # selected versions
#   CONFIGURATION=Debug ./build.sh 2025
#
# Requires the .NET 10 SDK (it can target net48, net8.0-windows and
# net10.0-windows; Windows targeting packs are downloaded on non-Windows hosts).
set -euo pipefail

cd "$(dirname "$0")"
CONFIGURATION="${CONFIGURATION:-Release}"
VERSIONS=("$@")
if [ ${#VERSIONS[@]} -eq 0 ]; then
    VERSIONS=(2024 2025 2026 2027)
fi

for version in "${VERSIONS[@]}"; do
    echo "==> Building RevitPy.Addin for Revit ${version} (${CONFIGURATION})"
    # Each Revit version uses a different target framework; clear restore state.
    rm -rf src/RevitPy.Addin/obj
    dotnet build src/RevitPy.Addin/RevitPy.Addin.csproj \
        -c "${CONFIGURATION}" -p:RevitVersion="${version}"
done

echo "Output: src/RevitPy.Addin/bin/${CONFIGURATION}/<version>/"
