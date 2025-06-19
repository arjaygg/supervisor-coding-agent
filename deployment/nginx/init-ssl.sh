#!/bin/bash

# SSL Initialization Script for nginx + certbot migration
# This script handles the initial SSL certificate setup

set -e

# Configuration
DOMAIN_NAME=${DOMAIN_NAME:-localhost}
LETSENCRYPT_EMAIL=${LETSENCRYPT_EMAIL:-admin@example.com}
SSL_DIR="/etc/nginx/ssl"
CERTBOT_WWW="/var/www/certbot"
CERTBOT_CONF="/etc/letsencrypt"

echo "🔧 Starting SSL initialization for domain: $DOMAIN_NAME"

# Create necessary directories
echo "📁 Creating SSL directories..."
mkdir -p "$SSL_DIR"
mkdir -p "$CERTBOT_WWW"
mkdir -p "$CERTBOT_CONF"

# Generate self-signed certificate for initial nginx startup
echo "🔑 Generating temporary self-signed certificate..."
if [ ! -f "$SSL_DIR/self-signed.crt" ] || [ ! -f "$SSL_DIR/self-signed.key" ]; then
    openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
        -keyout "$SSL_DIR/self-signed.key" \
        -out "$SSL_DIR/self-signed.crt" \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN_NAME"
    echo "✅ Self-signed certificate generated"
else
    echo "ℹ️  Self-signed certificates already exist"
fi

# Create temporary nginx config for Let's Encrypt challenge
echo "📝 Creating temporary nginx configuration..."
cat > /tmp/nginx-init.conf << EOF
server {
    listen 80;
    server_name $DOMAIN_NAME;
    
    location /.well-known/acme-challenge/ {
        root $CERTBOT_WWW;
    }
    
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN_NAME;
    
    ssl_certificate $SSL_DIR/self-signed.crt;
    ssl_certificate_key $SSL_DIR/self-signed.key;
    
    location / {
        return 503 "SSL setup in progress";
    }
}
EOF

echo "🚀 Starting nginx with temporary configuration..."

# Start nginx with temporary config (if not already running)
if ! pgrep nginx > /dev/null; then
    nginx -c /tmp/nginx-init.conf
    echo "✅ nginx started with temporary configuration"
fi

# Wait a moment for nginx to fully start
sleep 2

# Request Let's Encrypt certificate
echo "🌐 Requesting Let's Encrypt certificate for $DOMAIN_NAME..."
if [ "$DOMAIN_NAME" != "localhost" ] && [ -n "$LETSENCRYPT_EMAIL" ]; then
    docker run --rm \
        -v "$CERTBOT_WWW:$CERTBOT_WWW" \
        -v "$CERTBOT_CONF:$CERTBOT_CONF" \
        certbot/certbot certonly \
        --webroot \
        --webroot-path="$CERTBOT_WWW" \
        --email "$LETSENCRYPT_EMAIL" \
        --agree-tos \
        --no-eff-email \
        --force-renewal \
        -d "$DOMAIN_NAME"
    
    if [ $? -eq 0 ]; then
        echo "✅ Let's Encrypt certificate obtained successfully"
        
        # Update nginx to use Let's Encrypt certificates
        echo "🔄 Updating nginx configuration to use Let's Encrypt certificates..."
        nginx -s reload
        echo "✅ nginx reloaded with Let's Encrypt certificates"
    else
        echo "❌ Failed to obtain Let's Encrypt certificate"
        echo "ℹ️  nginx will continue using self-signed certificates"
    fi
else
    echo "ℹ️  Skipping Let's Encrypt certificate request (localhost or missing email)"
    echo "ℹ️  Using self-signed certificates for local development"
fi

echo "🎉 SSL initialization completed!"
echo ""
echo "📋 Next steps:"
echo "   1. Update DOMAIN_NAME environment variable with your actual domain"
echo "   2. Update LETSENCRYPT_EMAIL environment variable with your email"
echo "   3. Run 'docker-compose up -d nginx certbot' to start the services"
echo "   4. Certificates will be automatically renewed every 12 hours"