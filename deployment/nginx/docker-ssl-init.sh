#!/bin/bash

# Docker-based SSL Initialization Script for nginx + certbot
# This script works with the docker compose setup to initialize SSL certificates

set -e

# Configuration from environment or defaults
DOMAIN_NAME=${DOMAIN_NAME:-localhost}
LETSENCRYPT_EMAIL=${LETSENCRYPT_EMAIL:-admin@example.com}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.prod.yml}

echo "🔧 Initializing SSL setup for nginx migration"
echo "   Domain: $DOMAIN_NAME"
echo "   Email: $LETSENCRYPT_EMAIL"
echo "   Compose file: $COMPOSE_FILE"

# Check if docker compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ Docker compose file not found: $COMPOSE_FILE"
    exit 1
fi

# Create necessary directories
echo "📁 Creating SSL directories..."
mkdir -p ./deployment/nginx/ssl
mkdir -p ./deployment/certbot/www
mkdir -p ./deployment/certbot/conf

# Generate DH parameters for better SSL security
echo "🔐 Generating DH parameters (this may take a few minutes)..."
if [ ! -f "./deployment/nginx/ssl/dhparam.pem" ]; then
    openssl dhparam -out ./deployment/nginx/ssl/dhparam.pem 2048
    echo "✅ DH parameters generated"
else
    echo "ℹ️  DH parameters already exist"
fi

# Generate temporary self-signed certificate
echo "🔑 Generating temporary self-signed certificate..."
if [ ! -f "./deployment/nginx/ssl/self-signed.crt" ]; then
    openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
        -keyout ./deployment/nginx/ssl/self-signed.key \
        -out ./deployment/nginx/ssl/self-signed.crt \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN_NAME"
    echo "✅ Self-signed certificate generated"
else
    echo "ℹ️  Self-signed certificates already exist"
fi

# Create a temporary nginx config that uses self-signed certs initially
echo "📝 Creating temporary nginx configuration..."
cp ./deployment/nginx/conf.d/default.conf ./deployment/nginx/conf.d/default.conf.backup

# Update nginx config to use self-signed certs initially
sed -i.tmp "s|ssl_certificate /etc/letsencrypt/live/\${DOMAIN_NAME:-localhost}/fullchain.pem;|ssl_certificate /etc/nginx/ssl/self-signed.crt;|g" ./deployment/nginx/conf.d/default.conf
sed -i.tmp "s|ssl_certificate_key /etc/letsencrypt/live/\${DOMAIN_NAME:-localhost}/privkey.pem;|ssl_certificate_key /etc/nginx/ssl/self-signed.key;|g" ./deployment/nginx/conf.d/default.conf

echo "🚀 Starting nginx and certbot services..."

# Start nginx first with self-signed certificates
docker compose -f "$COMPOSE_FILE" up -d nginx

# Wait for nginx to be ready
echo "⏳ Waiting for nginx to start..."
sleep 5

# Check if nginx started successfully
if ! docker compose -f "$COMPOSE_FILE" ps nginx | grep -q "Up"; then
    echo "❌ nginx failed to start"
    docker compose -f "$COMPOSE_FILE" logs nginx
    exit 1
fi

echo "✅ nginx started successfully"

# Only proceed with Let's Encrypt if we have a real domain
if [ "$DOMAIN_NAME" != "localhost" ] && [[ "$DOMAIN_NAME" != *.local ]] && [ -n "$LETSENCRYPT_EMAIL" ]; then
    echo "🌐 Requesting Let's Encrypt certificate for $DOMAIN_NAME..."
    
    # Create the certificate
    docker compose -f "$COMPOSE_FILE" run --rm certbot \
        certonly --webroot --webroot-path=/var/www/certbot \
        --email "$LETSENCRYPT_EMAIL" --agree-tos --no-eff-email \
        --force-renewal -d "$DOMAIN_NAME"
    
    if [ $? -eq 0 ]; then
        echo "✅ Let's Encrypt certificate obtained successfully"
        
        # Restore original nginx config to use Let's Encrypt certs
        echo "🔄 Updating nginx to use Let's Encrypt certificates..."
        mv ./deployment/nginx/conf.d/default.conf.backup ./deployment/nginx/conf.d/default.conf
        
        # Reload nginx with new certificates
        docker compose -f "$COMPOSE_FILE" exec nginx nginx -s reload
        
        echo "✅ nginx updated to use Let's Encrypt certificates"
        
        # Start certbot renewal service
        docker compose -f "$COMPOSE_FILE" up -d certbot
        echo "✅ Certbot renewal service started"
    else
        echo "❌ Failed to obtain Let's Encrypt certificate"
        echo "ℹ️  nginx will continue using self-signed certificates"
    fi
else
    echo "ℹ️  Skipping Let's Encrypt certificate request"
    echo "ℹ️  Reason: localhost domain or missing email configuration"
    echo "ℹ️  Using self-signed certificates for local development"
fi

# Clean up temporary files
rm -f ./deployment/nginx/conf.d/default.conf.tmp

echo ""
echo "🎉 SSL initialization completed!"
echo ""
echo "📋 Service Status:"
docker compose -f "$COMPOSE_FILE" ps nginx certbot
echo ""
echo "📋 Next steps:"
if [ "$DOMAIN_NAME" = "localhost" ]; then
    echo "   • For production use, set DOMAIN_NAME and LETSENCRYPT_EMAIL environment variables"
    echo "   • Update DNS to point to your server"
    echo "   • Re-run this script with production settings"
else
    echo "   • Services are running and SSL is configured"
    echo "   • Certificates will be automatically renewed"
    echo "   • Monitor logs: docker compose -f $COMPOSE_FILE logs -f nginx certbot"
fi