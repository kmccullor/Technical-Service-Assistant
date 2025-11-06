#!/bin/sh

# Start Next.js in background
node server.js &

# Start nginx in foreground
nginx -g 'daemon off;'