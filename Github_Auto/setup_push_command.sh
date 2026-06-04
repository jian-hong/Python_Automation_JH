#!/bin/bash
REPO_ROOT="$(dirname "$0")/.."
SCRIPT_PATH="$(dirname "$0")/git-push.sh"

# Create a push alias in the repo root
echo '#!/bin/bash' > "$REPO_ROOT/push.sh"
echo "bash \"$SCRIPT_PATH\"" >> "$REPO_ROOT/push.sh"
chmod +x "$REPO_ROOT/push.sh"
chmod +x "$SCRIPT_PATH"

echo ""
echo "Done! From the repo folder, type:"
echo "  ./push.sh"
echo ""
echo "To use just 'push' anywhere, add this to your ~/.bashrc or ~/.zshrc:"
echo "  alias push='bash $REPO_ROOT/push.sh'"
