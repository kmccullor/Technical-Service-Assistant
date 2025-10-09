#!/bin/bash
# Technical Service Assistant - Package Builder
# ===========================================
# Creates a distributable package for installation on other servers

set -euo pipefail

# Configuration
PACKAGE_NAME="technical-service-assistant"
VERSION="1.0.0"
BUILD_DIR="build"
PACKAGE_DIR="$BUILD_DIR/$PACKAGE_NAME-$VERSION"
ARCHIVE_NAME="$PACKAGE_NAME-$VERSION.tar.gz"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${PURPLE}[STEP]${NC} $1"
    echo "----------------------------------------"
}

# Banner
print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        Technical Service Assistant - Package Builder        ║
║                                                              ║
║   Creating distributable installation package...            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# Clean build directory
clean_build() {
    log_step "Cleaning Build Directory"
    rm -rf "$BUILD_DIR"
    mkdir -p "$PACKAGE_DIR"
    log_success "Build directory cleaned"
}

# Copy core application files
copy_application_files() {
    log_step "Copying Application Files"
    
    # Core directories
    [ -d "reranker" ] && cp -r reranker/ "$PACKAGE_DIR/"
    [ -d "pdf_processor" ] && cp -r pdf_processor/ "$PACKAGE_DIR/"
    [ -d "next-rag-app" ] && cp -r next-rag-app/ "$PACKAGE_DIR/frontend"
    [ -d "utils" ] && cp -r utils/ "$PACKAGE_DIR/"
    [ -d "monitoring" ] && cp -r monitoring/ "$PACKAGE_DIR/"
    [ -d "scripts" ] && cp -r scripts/ "$PACKAGE_DIR/"
    [ -d "migrations" ] && cp -r migrations/ "$PACKAGE_DIR/"
    [ -d "docs" ] && cp -r docs/ "$PACKAGE_DIR/"
    [ -d "deployment" ] && cp -r deployment/ "$PACKAGE_DIR/"
    
    # Configuration files
    cp docker-compose.production.yml "$PACKAGE_DIR/docker-compose.yml"
    cp .env.production "$PACKAGE_DIR/.env.example"
    cp init.sql "$PACKAGE_DIR/"
    cp config.py "$PACKAGE_DIR/"
    
    # Requirements and setup
    cp requirements.txt "$PACKAGE_DIR/"
    cp requirements-dev.txt "$PACKAGE_DIR/"
    cp setup.py "$PACKAGE_DIR/"
    cp pyproject.toml "$PACKAGE_DIR/"
    
    # Documentation
    cp README.md "$PACKAGE_DIR/"
    cp ARCHITECTURE.md "$PACKAGE_DIR/"
    cp TROUBLESHOOTING.md "$PACKAGE_DIR/"
    cp CONTRIBUTING.md "$PACKAGE_DIR/"
    cp DEVELOPMENT.md "$PACKAGE_DIR/"
    cp CODE_QUALITY.md "$PACKAGE_DIR/"
    cp CHANGELOG.md "$PACKAGE_DIR/"
    
    # Installation scripts
    cp install.sh "$PACKAGE_DIR/"
    chmod +x "$PACKAGE_DIR/install.sh"
    
    log_success "Application files copied"
}

# Copy configuration templates
copy_configuration_templates() {
    log_step "Copying Configuration Templates"
    
    # Create config templates directory
    mkdir -p "$PACKAGE_DIR/config-templates"
    
    # Copy SearXNG config if exists
    if [ -d "searxng" ]; then
        cp -r searxng/ "$PACKAGE_DIR/"
    fi
    
    # Copy Ollama config if exists
    if [ -d "ollama_config" ]; then
        cp -r ollama_config/ "$PACKAGE_DIR/"
    fi
    
    # Copy monitoring config
    if [ -d "monitoring/prometheus" ]; then
        cp -r monitoring/prometheus/ "$PACKAGE_DIR/monitoring/"
    fi
    
    if [ -d "monitoring/grafana" ]; then
        cp -r monitoring/grafana/ "$PACKAGE_DIR/monitoring/"
    fi
    
    log_success "Configuration templates copied"
}

# Create installation package structure
create_package_structure() {
    log_step "Creating Package Structure"
    
    # Create required directories
    mkdir -p "$PACKAGE_DIR"/{logs,uploads,data,backups}
    
    # Create systemd service file
    cat > "$PACKAGE_DIR/technical-service-assistant.service" << 'EOF'
[Unit]
Description=Technical Service Assistant
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/technical-service-assistant
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
User=tsa
Group=tsa

[Install]
WantedBy=multi-user.target
EOF
    
    # Create nginx configuration
    mkdir -p "$PACKAGE_DIR/deployment/nginx"
    cat > "$PACKAGE_DIR/deployment/nginx/nginx.conf" << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream tsa_frontend {
        server frontend:80;
    }
    
    upstream tsa_api {
        server reranker:8008;
    }
    
    server {
        listen 80;
        server_name _;
        client_max_body_size 100M;
        
        location / {
            proxy_pass http://tsa_frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        location /api/ {
            proxy_pass http://tsa_api/api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        location /health {
            proxy_pass http://tsa_api/health;
        }
    }
}
EOF
    
    log_success "Package structure created"
}

# Generate checksums
generate_checksums() {
    log_step "Generating Checksums"
    
    cd "$PACKAGE_DIR"
    find . -type f -exec sha256sum {} \; > SHA256SUMS
    cd - > /dev/null
    
    log_success "Checksums generated"
}

# Create package metadata
create_package_metadata() {
    log_step "Creating Package Metadata"
    
    cat > "$PACKAGE_DIR/PACKAGE_INFO" << EOF
Package: $PACKAGE_NAME
Version: $VERSION
Built: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Built on: $(hostname)
Built by: $(whoami)
Architecture: $(uname -m)
OS: $(uname -s)

Description: Technical Service Assistant - AI-powered PDF processing and hybrid search system

Components:
- Reranker API Service
- PDF Processor
- Frontend Web Interface  
- Performance Monitor
- PostgreSQL + pgvector
- 4x Ollama Instances
- SearXNG Search Engine
- Prometheus + Grafana Monitoring

Requirements:
- Linux x86_64
- Docker & Docker Compose
- 8GB+ RAM (16GB recommended)
- 50GB+ disk space
- Internet connection for model downloads

Installation:
1. Extract package: tar -xzf $ARCHIVE_NAME
2. Run installer: sudo ./install.sh
3. Access web interface at http://server-ip/

Documentation: See README.md and deployment/INSTALLATION_GUIDE.md
EOF
    
    log_success "Package metadata created"
}

# Build Python package
build_python_package() {
    log_step "Building Python Package"
    
    cd "$PACKAGE_DIR"
    
    # Create Python package
    if command -v python3 &> /dev/null; then
        python3 setup.py sdist bdist_wheel > /dev/null 2>&1 || true
        log_success "Python package built"
    else
        log_warning "Python3 not found, skipping Python package build"
    fi
    
    cd - > /dev/null
}

# Create final archive
create_archive() {
    log_step "Creating Distribution Archive"
    
    cd "$BUILD_DIR"
    tar -czf "$ARCHIVE_NAME" "$PACKAGE_NAME-$VERSION/"
    cd - > /dev/null
    
    # Move archive to current directory
    mv "$BUILD_DIR/$ARCHIVE_NAME" ./
    
    # Get archive size
    ARCHIVE_SIZE=$(du -h "$ARCHIVE_NAME" | cut -f1)
    
    log_success "Archive created: $ARCHIVE_NAME ($ARCHIVE_SIZE)"
}

# Verify package
verify_package() {
    log_step "Verifying Package"
    
    # Test archive extraction
    TEST_DIR="$BUILD_DIR/test-extract"
    mkdir -p "$TEST_DIR"
    cd "$TEST_DIR"
    
    tar -xzf "../../$ARCHIVE_NAME" > /dev/null
    
    # Check key files exist
    REQUIRED_FILES=(
        "install.sh"
        "docker-compose.yml"
        ".env.example"
        "README.md"
        "reranker/app.py"
        "pdf_processor/process_pdfs.py"
        "frontend/index.html"
        "deployment/INSTALLATION_GUIDE.md"
        "PACKAGE_INFO"
        "SHA256SUMS"
    )
    
    MISSING_FILES=()
    for file in "${REQUIRED_FILES[@]}"; do
        if [ ! -f "$PACKAGE_NAME-$VERSION/$file" ]; then
            MISSING_FILES+=("$file")
        fi
    done
    
    cd - > /dev/null
    
    if [ ${#MISSING_FILES[@]} -eq 0 ]; then
        log_success "Package verification passed"
    else
        log_error "Package verification failed. Missing files:"
        for file in "${MISSING_FILES[@]}"; do
            echo "  - $file"
        done
        exit 1
    fi
}

# Generate installation instructions
generate_installation_instructions() {
    log_step "Generating Installation Instructions"
    
    cat > "INSTALL_${PACKAGE_NAME}-${VERSION}.txt" << EOF
Technical Service Assistant v${VERSION} - Installation Instructions
================================================================

QUICK START:
-----------
1. Extract the package:
   tar -xzf ${ARCHIVE_NAME}
   
2. Run the installer:
   cd ${PACKAGE_NAME}-${VERSION}
   sudo ./install.sh
   
3. Access the web interface:
   http://your-server-ip/

MANUAL INSTALLATION:
-------------------
If the automated installer fails, you can install manually:

1. Install Docker and Docker Compose
2. Copy files to /opt/technical-service-assistant/
3. Configure environment: cp .env.example .env
4. Edit .env with your settings
5. Start services: docker-compose up -d
6. Run setup: python3 scripts/install.py

SYSTEM REQUIREMENTS:
-------------------
- Linux x86_64 (Ubuntu 20.04+, CentOS 8+)
- 8GB+ RAM (16GB recommended)
- 50GB+ disk space (SSD recommended)
- Docker & Docker Compose
- Internet connection

SUPPORT:
--------
- Documentation: README.md
- Installation Guide: deployment/INSTALLATION_GUIDE.md
- Troubleshooting: TROUBLESHOOTING.md
- Architecture: ARCHITECTURE.md

Package Details:
- Version: ${VERSION}
- Built: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
- Archive: ${ARCHIVE_NAME}
- Size: $(du -h "$ARCHIVE_NAME" | cut -f1)
- Checksum: $(sha256sum "$ARCHIVE_NAME" | cut -d' ' -f1)

For the latest version and updates, visit:
https://github.com/technical-service-assistant/technical-service-assistant
EOF
    
    log_success "Installation instructions generated"
}

# Print summary
print_summary() {
    log_step "Build Summary"
    
    echo -e "${GREEN}✅ Package build completed successfully!${NC}"
    echo ""
    echo "📦 Package: $ARCHIVE_NAME"
    echo "📊 Size: $(du -h "$ARCHIVE_NAME" | cut -f1)"
    echo "🔍 SHA256: $(sha256sum "$ARCHIVE_NAME" | cut -d' ' -f1)"
    echo ""
    echo -e "${YELLOW}Distribution Files:${NC}"
    echo "  • $ARCHIVE_NAME (main package)"
    echo "  • INSTALL_${PACKAGE_NAME}-${VERSION}.txt (instructions)"
    echo ""
    echo -e "${CYAN}Next Steps:${NC}"
    echo "1. Test the package on a clean system"
    echo "2. Upload to distribution server/repository"
    echo "3. Update installation documentation"
    echo ""
    echo -e "${BLUE}Quick Test:${NC}"
    echo "  scp $ARCHIVE_NAME user@test-server:"
    echo "  ssh user@test-server"
    echo "  tar -xzf $ARCHIVE_NAME"
    echo "  cd $PACKAGE_NAME-$VERSION"
    echo "  sudo ./install.sh"
}

# Main build function
main() {
    print_banner
    
    log_info "Building Technical Service Assistant package v$VERSION"
    
    clean_build
    copy_application_files
    copy_configuration_templates
    create_package_structure
    generate_checksums
    create_package_metadata
    build_python_package
    create_archive
    verify_package
    generate_installation_instructions
    print_summary
    
    log_success "Build process completed!"
}

# Run main function
main "$@"