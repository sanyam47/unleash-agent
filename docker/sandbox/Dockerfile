# ========================================================
# Cyber Sandbox Micro-Container (Linux Security Tooling)
# Hardened, Network-Isolated Execution Environment
# ========================================================
FROM python:3.11-slim-bookworm

# Avoid interactive prompts during apt install
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install essential system dependencies, build headers, and network packet libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpcap-dev \
    libssl-dev \
    libffi-dev \
    tcpdump \
    net-tools \
    binutils \
    gdb \
    strace \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install primary cybersecurity & exploitation tooling
# - pwntools: binary exploitation, shellcraft, ROP gadgets, ELF parsing
# - scapy: packet crafting, protocol dissection, network stream simulation
# - cryptography & pycryptodome: ciphers, hashing, asymmetric keys, AES/RSA
# - impacket: Windows network protocol dissection (SMB, MSRPC, NTLM)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    pwntools \
    scapy \
    cryptography \
    pycryptodome \
    impacket \
    requests \
    colorama

# Create an unprivileged sandbox user (UID 1000)
# Running as non-root prevents container breakout vectors
RUN groupadd -g 1000 sandboxgroup && \
    useradd -u 1000 -g sandboxgroup -m -s /bin/bash sandboxuser

# Prepare workspace directory with write permissions for the sandbox user
WORKDIR /workspace
RUN chown -R sandboxuser:sandboxgroup /workspace

USER sandboxuser

# Default command
CMD ["python3"]
