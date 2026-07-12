#!/bin/bash
# Script to download the official Gradle 8.5 wrapper JAR
# This ensures we have the correct, validated wrapper JAR

GRADLE_VERSION="8.5"
WRAPPER_DIR="android/gradle/wrapper"
JAR_URL="https://raw.githubusercontent.com/gradle/gradle/v${GRADLE_VERSION}/gradle/wrapper/gradle-wrapper.jar"

echo "Downloading official Gradle ${GRADLE_VERSION} wrapper JAR..."
mkdir -p "$WRAPPER_DIR"
wget -q -O "$WRAPPER_DIR/gradle-wrapper.jar" "$JAR_URL"

if [ $? -eq 0 ]; then
    echo "Successfully downloaded gradle-wrapper.jar"
    ls -lh "$WRAPPER_DIR/gradle-wrapper.jar"
else
    echo "Failed to download gradle-wrapper.jar"
    exit 1
fi
