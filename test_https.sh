#!/bin/bash

# Test HTTPS setup with self-signed certificates
# This script tests the nginx configuration with SSL certificates

echo "Testing HTTPS setup with self-signed certificates..."

# Check if SSL certificates exist
if [ ! -f "ssl/server.crt" ] || [ ! -f "ssl/server.key" ]; then
    echo "ERROR: SSL certificates not found in ssl/ directory"
    echo "Run: openssl req -x509 -newkey rsa:4096 -keyout ssl/server.key -out ssl/server.crt -days 365 -nodes -subj \"/C=US/ST=State/L=City/O=Organization/CN=rni-llm-01.lab.sensus.net\""
    exit 1
fi

echo "✓ SSL certificates found"

# Test nginx configuration syntax
echo "Testing nginx configuration..."
docker run --rm -v $(pwd)/deployment/nginx.conf:/etc/nginx/nginx.conf:ro -v $(pwd)/ssl:/etc/ssl:ro nginx:alpine nginx -t

if [ $? -eq 0 ]; then
    echo "✓ Nginx configuration is valid"
else
    echo "✗ Nginx configuration has errors"
    exit 1
fi

echo ""
echo "To start the production environment with HTTPS:"
echo "1. Make sure all required environment variables are set in .env file"
echo "2. Run: docker-compose -f docker-compose.production.yml up -d"
echo "3. Access the application at: https://rni-llm-01.lab.sensus.net"
echo ""
echo "Note: Since this uses self-signed certificates, browsers will show a security warning."
echo "You can add the certificate to your browser's trusted certificates or accept the warning."
