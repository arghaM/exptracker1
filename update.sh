#!/bin/bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

echo ""
echo -e "${BLUE}${BOLD}=== ExpTracker Update ===${NC}"
echo ""

# Must be in a git repo
if [ ! -d ".git" ]; then
    echo -e "${RED}Not a git repository. Cannot update.${NC}"
    echo "If you installed via zip, re-download the latest version instead."
    exit 1
fi

# ---------- Step 1: Backup database before updating ----------
echo -e "${BOLD}[1/4] Backing up database...${NC}"
DB_FILE="${DB_PATH:-expenses.db}"
if [ -f "$DB_FILE" ]; then
    BACKUP_NAME="${DB_FILE}.backup-$(date +%Y%m%d-%H%M%S)"
    cp "$DB_FILE" "$BACKUP_NAME"
    echo -e "  ${GREEN}Saved: $BACKUP_NAME${NC}"
else
    echo -e "  ${YELLOW}No database found (fresh install)${NC}"
fi

# ---------- Step 2: Pull latest code ----------
echo ""
echo -e "${BOLD}[2/4] Pulling latest code...${NC}"

# Stash any local changes (like .env edits that accidentally got tracked)
git stash --include-untracked -q 2>/dev/null || true

BEFORE=$(git rev-parse HEAD)
git pull --ff-only origin main 2>/dev/null || git pull --ff-only origin master 2>/dev/null || {
    echo -e "  ${RED}Pull failed. You may have local changes conflicting with upstream.${NC}"
    echo "  Run: git stash && git pull origin main"
    exit 1
}
AFTER=$(git rev-parse HEAD)

if [ "$BEFORE" = "$AFTER" ]; then
    echo -e "  ${GREEN}Already up to date!${NC}"
else
    # Show what changed
    echo -e "  ${GREEN}Updated!${NC} Changes:"
    git log --oneline "$BEFORE".."$AFTER" | head -10 | while read line; do
        echo "    $line"
    done
fi

# Restore any stashed changes
git stash pop -q 2>/dev/null || true

# ---------- Step 3: Install any new dependencies ----------
echo ""
echo -e "${BOLD}[3/4] Updating dependencies...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
echo -e "  ${GREEN}Done${NC}"

# ---------- Step 4: Summary ----------
echo ""
echo -e "${BOLD}[4/4] Database migrations...${NC}"
echo -e "  ${GREEN}Will auto-apply on next start (init_db)${NC}"

echo ""
echo -e "${GREEN}${BOLD}=== Update Complete ===${NC}"
echo ""
echo -e "  Restart the app:  ${BOLD}./run.sh${NC}"
echo ""
echo -e "  ${YELLOW}Note: If something goes wrong, restore your backup:${NC}"
if [ -n "$BACKUP_NAME" ]; then
    echo -e "    cp $BACKUP_NAME $DB_FILE"
fi
echo ""
