#!/bin/bash

# setup-docker.sh - Docker setup and deployment script for AI VTuber
# This script helps build, configure, and run the Docker container
# Usage: ./setup-docker.sh [COMMAND] [OPTIONS]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOCKER_IMAGE_NAME="vtuber-app"
DOCKER_CONTAINER_NAME="vtuber-container"
DOCKER_IMAGE_TAG="latest"
BACKEND_PORT=8001
FRONTEND_PORT=3001

# Functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        echo "Please install Docker from: https://docs.docker.com/engine/install/"
        exit 1
    fi
    print_success "Docker is installed"
}

# Build Docker image
build_image() {
    print_header "Building Docker Image"
    
    if [ -z "$1" ]; then
        TAG="$DOCKER_IMAGE_TAG"
    else
        TAG="$1"
    fi
    
    print_info "Building image: $DOCKER_IMAGE_NAME:$TAG"
    sudo docker build -t "$DOCKER_IMAGE_NAME:$TAG" .
    
    if [ $? -eq 0 ]; then
        print_success "Docker image built successfully"
        echo -e "\nImage details:"
        sudo docker images "$DOCKER_IMAGE_NAME:$TAG"
    else
        print_error "Failed to build Docker image"
        exit 1
    fi
}

# Configure environment variables
configure_env() {
    print_header "Environment Configuration"
    
    if [ ! -f src/.env ]; then
        print_warning "src/.env file not found, creating template"
        cat > src/.env << 'EOF'
# API Keys and Tokens
DEEPSEEK_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here
QWEN_API_KEY=your_key_here
ELEVENLABS_API_KEY=your_key_here

# Twitch Configuration
TWITCH_BOT_TOKEN=your_token_here
TWITCH_CHANNEL=your_channel_here
TWITCH_CLIENT_ID=your_client_id_here
TWITCH_STREAM_KEY=live_your_key_here

# Optional: Remote vLLM Configuration
# REMOTE_VLLM_BASE_URL=https://your_vllm_server/v1/chat/completions
EOF
        print_success "Template created at src/.env"
        echo -e "\n${YELLOW}Please update src/.env with your API keys and secrets${NC}"
        echo "Required keys:"
        echo "  - DEEPSEEK_API_KEY or OPENROUTER_API_KEY (for LLM)"
        echo "  - QWEN_API_KEY (for TTS)"
        echo "  - TWITCH_* keys (for Twitch integration)"
    else
        print_success "src/.env file already exists"
    fi
    
    # Check if required keys are configured
    if grep -q "your_key_here\|^[A-Z_]*=$" src/.env; then
        print_warning "Some environment variables are not configured"
        echo "Please update src/.env with actual values before running the container"
    fi
}

# Run Docker container
run_container() {
    print_header "Running Docker Container"
    
    # Check if container is already running
    if docker ps | grep -q "$DOCKER_CONTAINER_NAME"; then
        print_warning "Container $DOCKER_CONTAINER_NAME is already running"
        return 0
    fi
    
    # Remove old container if exists
    if docker ps -a | grep -q "$DOCKER_CONTAINER_NAME"; then
        print_info "Removing old container..."
        sudo docker rm "$DOCKER_CONTAINER_NAME"
    fi
    
    # Run with port mapping and environment file
    print_info "Starting container: $DOCKER_CONTAINER_NAME"
    sudo docker run -d \
    --name vtuber_container \
    -v /home/redteam/AI-Vtuber:/app \
    vtuber \
    tail -f /dev/null
    
    if [ $? -eq 0 ]; then
        print_success "Container started successfully"
        echo -e "\n${BLUE}Container Details:${NC}"
        sudo docker ps | grep "$DOCKER_CONTAINER_NAME"
        
        echo -e "\n${BLUE}Access Points:${NC}"
        echo "  Backend API: http://localhost:$BACKEND_PORT"
        echo "  API Docs: http://localhost:$BACKEND_PORT/docs"
        echo "  Frontend: http://localhost:$FRONTEND_PORT"
        
        echo -e "\n${BLUE}Useful Commands:${NC}"
        echo "  View logs: docker logs -f $DOCKER_CONTAINER_NAME"
        echo "  Stop container: docker stop $DOCKER_CONTAINER_NAME"
        echo "  Restart container: docker restart $DOCKER_CONTAINER_NAME"
        echo "  Execute command: docker exec -it $DOCKER_CONTAINER_NAME /bin/bash"
    else
        print_error "Failed to start container"
        exit 1
    fi
}

# View container logs
view_logs() {
    print_header "Container Logs"
    sudo docker logs -f "$DOCKER_CONTAINER_NAME"
}

# Stop container
stop_container() {
    print_header "Stopping Container"
    
    if sudo docker ps | grep -q "$DOCKER_CONTAINER_NAME"; then
        sudo docker stop "$DOCKER_CONTAINER_NAME"
        print_success "Container stopped"
    else
        print_warning "Container is not running"
    fi
}

# Restart container
restart_container() {
    print_header "Restarting Container"
    
    if sudo docker ps -a | grep -q "$DOCKER_CONTAINER_NAME"; then
        sudo docker restart "$DOCKER_CONTAINER_NAME"
        print_success "Container restarted"
        
        echo -e "\n${BLUE}Access Points:${NC}"
        echo "  Backend API: http://localhost:$BACKEND_PORT"
        echo "  Frontend: http://localhost:$FRONTEND_PORT"
    else
        print_warning "Container does not exist"
    fi
}

# Clean up (remove container and image)
cleanup() {
    print_header "Cleanup - Remove Container and Image"
    
    print_info "This will remove the container and Docker image"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Stop and remove container
        if sudo docker ps -a | grep -q "$DOCKER_CONTAINER_NAME"; then
            sudo docker stop "$DOCKER_CONTAINER_NAME" || true
            sudo docker rm "$DOCKER_CONTAINER_NAME"
            print_success "Container removed"
        fi
        
        # Remove image
        if sudo docker images | grep -q "$DOCKER_IMAGE_NAME"; then
            sudo docker rmi "$DOCKER_IMAGE_NAME:$DOCKER_IMAGE_TAG"
            print_success "Docker image removed"
        fi
    else
        print_info "Cleanup cancelled"
    fi
}

# Interactive setup wizard
setup_wizard() {
    print_header "Docker Setup Wizard"
    
    echo "This wizard will help you set up the Docker environment."
    echo ""
    
    # Check Docker
    check_docker
    echo ""
    
    # Configure environment
    configure_env
    echo ""
    
    # Build image
    read -p "Build Docker image now? (Y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        build_image
        echo ""
    fi
    
    # Run container
    read -p "Run Docker container now? (Y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        run_container
    fi
    
    print_header "Setup Complete!"
    echo "Your AI VTuber application is now running in Docker!"
}

# Print usage information
print_usage() {
    cat << EOF
${BLUE}AI VTuber Docker Setup Script${NC}

${GREEN}Usage:${NC}
    $0 [COMMAND] [OPTIONS]

${GREEN}Commands:${NC}
    build [TAG]         Build Docker image (default tag: latest)
    run                 Run Docker container
    logs                View container logs
    stop                Stop running container
    restart             Restart container
    cleanup             Remove container and image
    configure           Set up environment variables
    setup               Interactive setup wizard (builds and runs)
    status              Show container status
    help                Show this help message

${GREEN}Examples:${NC}
    $0 setup            # Run interactive wizard
    $0 build v1.0       # Build image with tag v1.0
    $0 run              # Run container with latest image
    $0 logs             # View live logs

${GREEN}Default Ports:${NC}
    Backend API: $BACKEND_PORT
    Frontend: $FRONTEND_PORT

${GREEN}Environment:${NC}
    Configuration file: src/.env

${GREEN}Documentation:${NC}
    See DEPLOYMENT.md for detailed deployment instructions

EOF
}

# Main script
main() {
    case "${1:-setup}" in
        build)
            check_docker
            build_image "${2:-}"
            ;;
        run)
            check_docker
            run_container
            ;;
        logs)
            view_logs
            ;;
        stop)
            stop_container
            ;;
        restart)
            restart_container
            ;;
        cleanup)
            cleanup
            ;;
        configure)
            configure_env
            ;;
        setup)
            setup_wizard
            ;;
        status)
            print_header "Container Status"
            if docker ps | grep -q "$DOCKER_CONTAINER_NAME"; then
                print_success "Container is running"
                docker ps | grep "$DOCKER_CONTAINER_NAME"
            elif docker ps -a | grep -q "$DOCKER_CONTAINER_NAME"; then
                print_warning "Container exists but is not running"
                docker ps -a | grep "$DOCKER_CONTAINER_NAME"
            else
                print_error "Container does not exist"
            fi
            ;;
        help|--help|-h)
            print_usage
            ;;
        *)
            print_error "Unknown command: $1"
            echo ""
            print_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
