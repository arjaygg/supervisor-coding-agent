# Traefik to nginx Migration Guide

## Overview

This document describes the migration from Traefik to nginx as the reverse proxy for the dev-assist system. This migration addresses external access issues while providing explicit SSL certificate management.

## What Changed

### Services Updated
- **Removed**: Traefik service and related volumes
- **Added**: nginx service with Alpine Linux base image
- **Added**: certbot service for Let's Encrypt certificate management
- **Updated**: Removed Traefik-specific labels from API and frontend services

### Configuration Changes
- **SSL Management**: Switched from Traefik's automatic Let's Encrypt to explicit certbot management
- **Routing**: Maintains same routing patterns (`/api` → backend:8000, `/` → frontend:3000)
- **Resource Usage**: Similar memory footprint (~64MB vs 48MB for Traefik)

## Migration Benefits

1. **Explicit Control**: Direct management of SSL certificates and nginx configuration
2. **Troubleshooting**: Easier debugging with static configuration files
3. **Performance**: nginx's proven performance for static content and reverse proxying
4. **Flexibility**: Easier to customize routing rules and security headers

## Quick Start

### For Local Development (localhost)
```bash
# Initialize SSL with self-signed certificates
./deployment/nginx/docker-ssl-init.sh

# Start services
docker compose -f docker-compose.prod.yml up -d
```

### For Production (with domain)
```bash
# Set environment variables
export DOMAIN_NAME=your-domain.com
export LETSENCRYPT_EMAIL=admin@your-domain.com

# Initialize SSL with Let's Encrypt
./deployment/nginx/docker-ssl-init.sh

# Services will start automatically with valid SSL certificates
```

## SSL Certificate Management

### Initial Setup
The `docker-ssl-init.sh` script handles:
1. Creating necessary directories and DH parameters
2. Generating temporary self-signed certificates
3. Starting nginx with temporary certificates
4. Requesting Let's Encrypt certificates (for non-localhost domains)
5. Updating nginx to use Let's Encrypt certificates
6. Starting the certbot renewal service

### Certificate Renewal
- Automatic renewal every 12 hours via certbot service
- Certificates are shared between nginx and certbot via Docker volumes
- nginx automatically reloads when certificates are renewed

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DOMAIN_NAME` | `localhost` | Domain name for SSL certificates |
| `LETSENCRYPT_EMAIL` | `admin@example.com` | Email for Let's Encrypt registration |

## Service Architecture

```
Internet → nginx:80/443 → {
  /api/* → api:8000
  /ws    → api:8000 (WebSocket)
  /*     → frontend:3000
}
```

## Resource Allocation

| Service | Memory Limit | CPU Limit | Memory Reserved | CPU Reserved |
|---------|--------------|-----------|-----------------|--------------|
| nginx   | 64M          | 0.15      | 32M             | 0.05         |
| certbot | 64M          | 0.1       | 32M             | 0.05         |

## Troubleshooting

### Check Service Status
```bash
docker compose -f docker-compose.prod.yml ps nginx certbot
```

### View Logs
```bash
# nginx logs
docker compose -f docker-compose.prod.yml logs -f nginx

# certbot logs
docker compose -f docker-compose.prod.yml logs -f certbot
```

### Test nginx Configuration
```bash
docker compose -f docker-compose.prod.yml exec nginx nginx -t
```

### Manual Certificate Request
```bash
docker compose -f docker-compose.prod.yml run --rm certbot \
  certonly --webroot --webroot-path=/var/www/certbot \
  --email your-email@domain.com --agree-tos --no-eff-email \
  -d your-domain.com
```

### SSL Certificate Status
```bash
# Check certificate expiry
docker compose -f docker-compose.prod.yml exec nginx \
  openssl x509 -in /etc/letsencrypt/live/your-domain.com/fullchain.pem -text -noout
```

## Rollback Plan

If you need to rollback to Traefik:

1. Checkout the previous commit:
   ```bash
   git checkout HEAD~1 -- docker-compose.prod.yml deployment/
   ```

2. Restore Traefik volumes:
   ```bash
   docker volume create dev-assist_traefik_data
   ```

3. Restart services:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

## Security Features

### nginx Security Headers
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`  
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security` (HTTPS only)
- `Referrer-Policy: no-referrer-when-downgrade`

### Rate Limiting
- API endpoints: 10 requests/second with burst of 20
- Login endpoints: 1 request/second (configured but not used)

### SSL Security
- TLS 1.2 and 1.3 only
- Strong cipher suites
- OCSP stapling enabled
- Perfect Forward Secrecy with DH parameters

## Files Modified

- `docker-compose.prod.yml`: Service definitions
- `deployment/nginx/conf.d/default.conf`: SSL certificate paths
- `deployment/nginx/docker-ssl-init.sh`: SSL initialization script
- `deployment/nginx/init-ssl.sh`: Standalone SSL script

## Next Steps

1. Test the migration in a staging environment
2. Update monitoring to check nginx instead of Traefik
3. Update documentation references from Traefik to nginx
4. Consider adding nginx-prometheus-exporter for metrics