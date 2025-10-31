#!/bin/bash
# Technical Service Assistant - Quick Install Script
# =================================================
# This script sets up the Technical Service Assistant on a new server
# with all dependencies, Docker containers, and configuration.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
TSA_VERSION="1.0.0"
TSA_USER="tsa"
TSA_HOME="/opt/technical-service-assistant"
# Defaults (can be overridden via interactive prompt or env vars)
DEFAULT_DEPARTMENT_NAME="Technical Service"
DEFAULT_ASSISTANT_NAME="Technical Service Assistant"
DEPARTMENT_NAME="${DEPARTMENT_NAME:-}"
ASSISTANT_NAME="${ASSISTANT_NAME:-}"
DOCKER_COMPOSE_VERSION="2.20.0"
PYTHON_VERSION="3.9"

# Logging functions
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

# Error handling
handle_error() {
    log_error "Installation failed at line $1"
    log_error "Check the logs above for details"
    exit 1
}

trap 'handle_error $LINENO' ERR

# Banner
print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        Technical Service Assistant - Installation            ║
║                                                              ║
║   AI-powered PDF processing and hybrid search system        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# System requirements check
check_system_requirements() {
    log_step "Checking System Requirements"

    # Check OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        log_success "Linux OS detected"
    else
        log_error "This installer requires Linux. Current OS: $OSTYPE"
        exit 1
    fi

    # Check architecture
    ARCH=$(uname -m)
    if [[ "$ARCH" == "x86_64" ]] || [[ "$ARCH" == "amd64" ]]; then
        log_success "x86_64 architecture detected"
    else
        log_warning "Unsupported architecture: $ARCH. Installation may fail."
    fi

    # Check available memory (minimum 4GB recommended)
    MEMORY_GB=$(free -g | awk 'NR==2{printf "%.0f", $7}')
    if [[ $MEMORY_GB -lt 4 ]]; then
        log_warning "Low memory detected: ${MEMORY_GB}GB. Recommended: 4GB+"
    else
        log_success "Memory check passed: ${MEMORY_GB}GB available"
    fi

    # Check disk space (minimum 10GB recommended)
    DISK_GB=$(df -BG / | awk 'NR==2 {print $4}' | sed 's/G//')
    if [[ $DISK_GB -lt 10 ]]; then
        log_error "Insufficient disk space: ${DISK_GB}GB. Required: 10GB+"
        exit 1
    else
        log_success "Disk space check passed: ${DISK_GB}GB available"
    fi
}

# Install system dependencies
install_system_dependencies() {
    log_step "Installing System Dependencies"

    # Detect package manager
    if command -v apt-get &> /dev/null; then
        PKG_MANAGER="apt"
        UPDATE_CMD="apt-get update"
        INSTALL_CMD="apt-get install -y"
    elif command -v yum &> /dev/null; then
        PKG_MANAGER="yum"
        UPDATE_CMD="yum update -y"
        INSTALL_CMD="yum install -y"
    elif command -v dnf &> /dev/null; then
        PKG_MANAGER="dnf"
        UPDATE_CMD="dnf update -y"
        INSTALL_CMD="dnf install -y"
    else
        log_error "Unsupported package manager. Please install dependencies manually."
        exit 1
    fi

    log_info "Using package manager: $PKG_MANAGER"

    # Update package list
    log_info "Updating package list..."
    sudo $UPDATE_CMD

    # Install base dependencies
    log_info "Installing base dependencies..."
    sudo $INSTALL_CMD \
        curl \
        wget \
        git \
        unzip \
        python3 \
        python3-pip \
        python3-venv \
        build-essential \
        postgresql-client \
        nginx \
        supervisor \
        htop \
        jq

    log_success "System dependencies installed"
}

# Install Docker
install_docker() {
    log_step "Installing Docker"

    if command -v docker &> /dev/null; then
        log_info "Docker already installed: $(docker --version)"
        return
    fi

    # Install Docker using official script
    log_info "Installing Docker..."
    curl -fsSL https://get.docker.com | sudo sh

    # Add current user to docker group
    sudo usermod -aG docker $USER

    # Install Docker Compose
    log_info "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose

    # Start Docker service
    sudo systemctl enable docker
    sudo systemctl start docker

    log_success "Docker installed successfully"
    log_warning "Please log out and back in to use Docker without sudo"
}

# Create TSA user and directories
setup_user_and_directories() {
    log_step "Setting up User and Directories"

    # Create TSA user if not exists
    if ! id "$TSA_USER" &>/dev/null; then
        log_info "Creating TSA user: $TSA_USER"
        sudo useradd -r -s /bin/bash -d "$TSA_HOME" -m "$TSA_USER"
        sudo usermod -aG docker "$TSA_USER"
    else
        log_info "TSA user already exists: $TSA_USER"
    fi

    # Create directories
    log_info "Creating application directories..."
    sudo mkdir -p "$TSA_HOME"/{logs,uploads,data,config,backups}
    sudo chown -R "$TSA_USER:$TSA_USER" "$TSA_HOME"
    sudo chmod 755 "$TSA_HOME"

    log_success "User and directories configured"
}

# Download and extract application
prompt_customization() {
    log_step "Customization"
    if [[ -z "${DEPARTMENT_NAME}" ]]; then
        read -rp "Enter the department name (default: ${DEFAULT_DEPARTMENT_NAME}): " input_dept || true
        if [[ -n "${input_dept}" ]]; then
            DEPARTMENT_NAME="${input_dept}"
        else
            DEPARTMENT_NAME="${DEFAULT_DEPARTMENT_NAME}"
        fi
    else
        log_info "Using provided DEPARTMENT_NAME=${DEPARTMENT_NAME}"
    fi

    if [[ -z "${ASSISTANT_NAME}" ]]; then
        read -rp "Enter a name for the assistant (default: ${DEFAULT_ASSISTANT_NAME}): " input_name || true
        if [[ -n "${input_name}" ]]; then
            ASSISTANT_NAME="${input_name}"
        else
            ASSISTANT_NAME="${DEFAULT_ASSISTANT_NAME}"
        fi
    else
        log_info "Using provided ASSISTANT_NAME=${ASSISTANT_NAME}"
    fi

    log_success "Assistant will be installed as: '${ASSISTANT_NAME}' for department '${DEPARTMENT_NAME}'"
}

download_application() {
    log_step "Downloading Application"

    # For now, assume we're running from the source directory
    # In production, this would download from a release URL
    if [[ -f "docker-compose.yml" ]]; then
        log_info "Running from source directory, copying files..."
        sudo cp -r . "$TSA_HOME/app/"
        sudo chown -R "$TSA_USER:$TSA_USER" "$TSA_HOME/app"
    else
        log_error "Cannot find application files. Please run from the TSA source directory."
        exit 1
    fi

    log_success "Application files copied"
}

# Configure environment
configure_environment() {
    log_step "Configuring Environment"

    # Copy environment template
    sudo -u "$TSA_USER" cp "$TSA_HOME/app/.env.example" "$TSA_HOME/config/.env"

    # Generate random passwords and keys
    DB_PASSWORD=$(openssl rand -base64 32)
    API_KEY=$(openssl rand -base64 32)
    JWT_SECRET=$(openssl rand -base64 64)

    # Update environment file
    sudo -u "$TSA_USER" sed -i "s/DB_PASSWORD=.*/DB_PASSWORD=$DB_PASSWORD/" "$TSA_HOME/config/.env"
    sudo -u "$TSA_USER" sed -i "s/API_KEY=.*/API_KEY=$API_KEY/" "$TSA_HOME/config/.env"
    sudo -u "$TSA_USER" sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$JWT_SECRET/" "$TSA_HOME/config/.env"

    # Append customization variables
    {
        echo "DEPARTMENT_NAME=\"${DEPARTMENT_NAME}\""
        echo "ASSISTANT_NAME=\"${ASSISTANT_NAME}\""
    } | sudo -u "$TSA_USER" tee -a "$TSA_HOME/config/.env" > /dev/null

    # Create symlink for application
    sudo -u "$TSA_USER" ln -sf "$TSA_HOME/config/.env" "$TSA_HOME/app/.env"

    log_success "Environment configured"
    log_info "Database password: $DB_PASSWORD"
    log_info "API key: $API_KEY"
    log_warning "Please save these credentials securely!"
}

# Setup systemd services
setup_systemd_services() {
    log_step "Setting up Systemd Services"

    # TSA Docker Compose service
    sudo tee /etc/systemd/system/technical-service-assistant.service > /dev/null << EOF
[Unit]
Description=${ASSISTANT_NAME}
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$TSA_HOME/app
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
User=$TSA_USER
Group=$TSA_USER

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable technical-service-assistant.service

    log_success "Systemd services configured"
}

# Setup nginx reverse proxy
setup_nginx() {
    log_step "Configuring Nginx Reverse Proxy"

    # Create nginx config
    sudo tee /etc/nginx/sites-available/technical-service-assistant > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 100M;

    # Frontend
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API endpoints
    location /api/ {
        proxy_pass http://localhost:8008;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check
    location /health {
        proxy_pass http://localhost:8008/health;
    }

    # Monitoring
    location /metrics {
        proxy_pass http://localhost:9090;
        auth_basic "Monitoring";
        auth_basic_user_file /etc/nginx/.htpasswd;
    }
}
EOF

    # Enable site
    sudo ln -sf /etc/nginx/sites-available/technical-service-assistant /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default

    # Test nginx config
    sudo nginx -t

    # Restart nginx
    sudo systemctl restart nginx
    sudo systemctl enable nginx

    log_success "Nginx configured"
}

# Start services
start_services() {
    log_step "Starting Services"

    # Start TSA services
    log_info "Starting Technical Service Assistant..."
    sudo systemctl start technical-service-assistant.service

    # Wait for services to be ready
    log_info "Waiting for services to start..."
    sleep 30

    # Check service status
    if sudo systemctl is-active --quiet technical-service-assistant.service; then
        log_success "Technical Service Assistant is running"
    else
        log_error "Failed to start Technical Service Assistant"
        sudo systemctl status technical-service-assistant.service
        exit 1
    fi

    log_success "All services started"
}

# Health check
perform_health_check() {
    log_step "Performing Health Check"

    # Check web interface
    if curl -f http://localhost:8080 &>/dev/null; then
        log_success "Web interface is accessible"
    else
        log_warning "Web interface not yet accessible"
    fi

    # Check API
    if curl -f http://localhost:8008/health &>/dev/null; then
        log_success "API is responding"
    else
        log_warning "API not yet responding"
    fi

    # Check database
    if sudo -u "$TSA_USER" docker-compose -f "$TSA_HOME/app/docker-compose.yml" exec -T pgvector pg_isready -U postgres &>/dev/null; then
        log_success "Database is ready"
    else
        log_warning "Database not yet ready"
    fi
}

# Print summary
print_summary() {
    log_step "Installation Summary"

    echo -e "${GREEN}✅ ${ASSISTANT_NAME} installed successfully!${NC}"
    echo ""
    echo "🏢 Department: ${DEPARTMENT_NAME}"
    echo "🤖 Assistant Name: ${ASSISTANT_NAME}"
    echo "🌐 Web Interface: http://$(hostname -I | awk '{print $1}')"
    echo "📡 API Endpoint:  http://$(hostname -I | awk '{print $1}')/api"
    echo "📊 Health Check:  http://$(hostname -I | awk '{print $1}')/health"
    echo ""
    echo "📁 Installation Directory: $TSA_HOME"
    echo "👤 Service User: $TSA_USER"
    echo "🔧 Configuration: $TSA_HOME/config/.env"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. Upload PDF documents to the web interface"
    echo "2. Configure monitoring (optional): systemctl status technical-service-assistant"
    echo "3. Check logs: journalctl -u technical-service-assistant -f"
    echo "4. Backup configuration: $TSA_HOME/config/"
    echo ""
    echo -e "${CYAN}Documentation: $TSA_HOME/app/README.md${NC}"
}

# Main installation function
main() {
    print_banner

    # Check if running as root for system setup
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        echo "Usage: sudo $0"
        exit 1
    fi

    log_info "Starting ${ASSISTANT_NAME:-Technical Service Assistant} installation..."

    check_system_requirements
    prompt_customization
    install_system_dependencies
    install_docker
    setup_user_and_directories
    download_application
    configure_environment
    setup_systemd_services
    setup_nginx
    start_services
    perform_health_check
    print_summary

    log_success "Installation completed successfully!"
}

# Run main function
main "$@"
