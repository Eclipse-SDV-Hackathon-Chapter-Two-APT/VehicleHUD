# syntax=docker/dockerfile:1.2

# Build stage, to create the executable
FROM --platform=$TARGETPLATFORM ghcr.io/eclipse-velocitas/devcontainer-base-images/python:v0.3 as builder
ARG TARGETARCH

# Install dependencies for Python and build tools
RUN apt-get update && apt-get install -y python3-dev

# Copy application files
COPY ./.velocitas.json /workspace/.velocitas.json
COPY ./app /workspace/app

# Handle Arm64-specific installation for staticx
RUN /bin/bash -c 'set -ex && \
    ARCH=`uname -m` && \
    if [ "$ARCH" == "aarch64" ]; then \
    echo "ARM64" && \
    apt-get install -y gcc && \
    pip3 install --no-cache-dir scons; \
    fi'

# Install Python dependencies
RUN pip3 install --no-cache-dir pyinstaller==5.9.0 \
    && pip3 install --no-cache-dir patchelf==0.17.0.0 \
    && pip3 install --no-cache-dir staticx \
    && pip3 install --no-cache-dir -r /workspace/app/requirements.txt \
    && pip3 install --no-cache-dir -r /workspace/app/requirements-links.txt

# Initialize Velocitas
WORKDIR /workspace
RUN velocitas init

# Build the executable
WORKDIR /workspace/app
RUN pyinstaller --clean -F -s src/main.py

# Include additional application files
WORKDIR /workspace/app/dist
COPY ./app/src /app/src  # Copy the app/src directory for runtime access

# Create static executable
RUN staticx main run-exe

# Runner stage, to copy the executable and app/src directory
FROM scratch as runner

# Copy the static executable
COPY --from=builder /workspace/app/dist/run-exe /app/run-exe

# Copy the app/src directory for runtime use
COPY --from=builder /workspace/app/src /app/src

WORKDIR /app

ENV PATH="/:/app:$PATH"

LABEL org.opencontainers.image.source="https://github.com/eclipse-velocitas/vehicle-app-python-template"

CMD ["/app/run-exe"]
