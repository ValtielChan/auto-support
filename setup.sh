#!/usr/bin/env bash
#
# One-time setup helper: creates .env from the template and generates a random
# SECRET_KEY for you. After running it, just set ADMIN_PASSWORD in .env.
#
#   ./setup.sh && nano .env && docker compose up -d --build
#
set -euo pipefail
cd "$(dirname "$0")"

if [ -f .env ]; then
  echo "✓ .env already exists — leaving it untouched."
  exit 0
fi

cp .env.example .env

# Generate a 32-byte hex SECRET_KEY (openssl if available, else /dev/urandom).
if command -v openssl >/dev/null 2>&1; then
  KEY="$(openssl rand -hex 32)"
else
  KEY="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi

# In-place edit that works with both GNU and BSD sed.
sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=${KEY}|" .env && rm -f .env.bak

echo "✓ Created .env with a generated SECRET_KEY."
echo ""
echo "Next steps:"
echo "  1. Set ADMIN_PASSWORD in .env   (and optionally OPENAI_API_KEY)"
echo "  2. Start the app:               docker compose up -d --build"
echo "  3. Open:                        http://localhost:8000"
