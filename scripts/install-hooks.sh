#!/usr/bin/env bash
# Installs a pre-commit hook that blocks commits containing secrets (requires gitleaks).
set -euo pipefail
hook="$(git rev-parse --git-dir)/hooks/pre-commit"
cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
command -v gitleaks >/dev/null || { echo "gitleaks not installed: brew install gitleaks"; exit 1; }
gitleaks git --pre-commit --staged --redact --verbose
HOOK
chmod +x "$hook"
echo "pre-commit secret scan installed"
