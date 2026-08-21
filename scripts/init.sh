#!/usr/bin/env bash
# ============================================================
# AI-Assisted Development Methodology — One-Click Init
# ============================================================
# Usage:
#   bash init.sh                  # Interactive Tier 1 setup
#   bash init.sh --tier 2         # Non-interactive Tier 2 setup
#   bash init.sh --tier 1 --name "my-project" --stack java
#   bash init.sh --check          # Verify current setup status
#
# What this does:
#   Tier 1 (5 min): CLAUDE.md + OpenSpec + Superpowers + mandatory skills check
#   Tier 2 (15 min): Fitness config + path documents + SDD setup
#   Tier 3 (full):  Frontend engineering + RAMER agent + CI integration
# ============================================================

set -euo pipefail

# ---- Resolve paths ----
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
METHODOLOGY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATES_DIR="$METHODOLOGY_DIR/templates"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"

# ---- Defaults ----
TIER="${TIER:-1}"
PROJECT_NAME="${PROJECT_NAME:-}"
STACK="${STACK:-}"
SOURCE="${SOURCE:-}"
CHECK_ONLY=false
DRY_RUN=false

# ---- Colors ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ---- Args ----
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tier) TIER="$2"; shift 2 ;;
    --name) PROJECT_NAME="$2"; shift 2 ;;
    --stack) STACK="$2"; shift 2 ;;
    --source) SOURCE="$2"; shift 2 ;;
    --check) CHECK_ONLY=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help|-h)
      echo "Usage: bash init.sh [--tier 1|2|3] [--name <project>] [--stack java|node|python] [--source <path|url>] [--check] [--dry-run]"
      exit 0
      ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

# ---- Read version ----
VERSION_FILE="$METHODOLOGY_DIR/VERSION"
if [ -f "$VERSION_FILE" ]; then
  VERSION="$(head -1 "$VERSION_FILE")"
else
  VERSION="unknown"
fi

# ---- Helpers ----
info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
step()  { echo -e "\n${BOLD}━━━ $* ━━━${NC}"; }
check() { [ "$DRY_RUN" = true ] && return 0; "$@"; }
file_exists() { [ -f "$1" ] && echo -e "  ${GREEN}✓${NC} $1" || echo -e "  ${RED}✗${NC} $1"; }
dir_exists()  { [ -d "$1" ] && echo -e "  ${GREEN}✓${NC} $1" || echo -e "  ${RED}✗${NC} $1"; }
cmd_exists()  { command -v "$1" &>/dev/null && echo -e "  ${GREEN}✓${NC} $1" || echo -e "  ${RED}✗${NC} $1"; }

run() {
  if [ "$DRY_RUN" = true ]; then
    echo -e "  ${YELLOW}[dry-run]${NC} $*"
  else
    "$@"
  fi
}

# ---- Status check ----
do_check() {
  step "Status Check"
  echo ""
  echo "Project root: $PROJECT_ROOT"
  echo "Methodology:  $METHODOLOGY_DIR"
  echo ""
  echo "--- Mandatory Skills ---"
  file_exists "$PROJECT_ROOT/openspec/config.yaml"
  dir_exists  "$PROJECT_ROOT/docs/superpowers/plans"
  dir_exists  "$PROJECT_ROOT/docs/superpowers/specs"
  echo -e "  $(grep -r "codegraph" ~/.claude/settings.* 2>/dev/null && echo -e "${GREEN}✓${NC} codegraph MCP" || echo -e "${RED}✗${NC} codegraph MCP")"
  echo ""
  echo "--- Core Files ---"
  file_exists "$PROJECT_ROOT/CLAUDE.md"
  file_exists "$PROJECT_ROOT/docs/methodology/core/mandatory-skills.md"
  echo ""
  echo "--- Templates ---"
  file_exists "$TEMPLATES_DIR/CLAUDE.md.template"
  file_exists "$TEMPLATES_DIR/openspec-config.yaml.template"
  file_exists "$TEMPLATES_DIR/mandatory-skills/SKILLS.md.template"
  file_exists "$TEMPLATES_DIR/fitness/JavaParameterScanner.java.template"
  file_exists "$TEMPLATES_DIR/fitness/test_java_parameter_limit.py.template"
  echo ""
  echo "--- Frontend Engineering ---"
  file_exists "$HOME/.claude/skills/fe-engineering/SKILL.md"
  file_exists "$HOME/.codex/skills/fe-engineering/SKILL.md"
  echo ""
  echo "--- Multi-Agent Parallel ---"
  file_exists "$HOME/.claude/skills/multi-agent/SKILL.md"
  file_exists "$HOME/.codex/skills/multi-agent/SKILL.md"
  echo ""
  echo "--- Token Compaction Preservation ---"
  file_exists "$PROJECT_ROOT/.claude/round-contract.md"
  file_exists "$PROJECT_ROOT/.claude/hooks/save-state.sh"
  file_exists "$PROJECT_ROOT/.codex/round-contract.md"
  file_exists "$PROJECT_ROOT/.codex/hooks/save-state.sh"
  echo ""
  echo "--- Fitness (Tier 2) ---"
  file_exists "$PROJECT_ROOT/docs/fitness/scripts/fitness.py"
  file_exists "$PROJECT_ROOT/docs/fitness/README.md"
  echo ""
  echo "--- Path Documents (Tier 2) ---"
  find "$PROJECT_ROOT" -maxdepth 3 -name "AI.md" -not -path "*/node_modules/*" -not -path "*/.git/*" 2>/dev/null | head -10 | while read f; do
    echo "  ${GREEN}✓${NC} ${f#$PROJECT_ROOT/}"
  done
}

if [ "$CHECK_ONLY" = true ]; then
  do_check
  exit 0
fi

# ---- Tier 1: One-Click Setup ----
do_tier1() {
  step "Tier 1: Core Setup (5 min)"

  # 1.1 CLAUDE.md
  info "1.1 Setting up CLAUDE.md..."
  if [ -f "$PROJECT_ROOT/CLAUDE.md" ]; then
    warn "CLAUDE.md already exists, skipping. Delete it first to overwrite."
  else
    if [ -f "$TEMPLATES_DIR/CLAUDE.md.template" ]; then
      run cp "$TEMPLATES_DIR/CLAUDE.md.template" "$PROJECT_ROOT/CLAUDE.md"
      ok "Created CLAUDE.md (edit placeholders marked with {{ }})"
    else
      fail "CLAUDE.md.template not found at $TEMPLATES_DIR"
    fi
  fi

  # 1.2 OpenSpec
  info "1.2 Setting up OpenSpec..."
  if [ -f "$PROJECT_ROOT/openspec/config.yaml" ]; then
    ok "OpenSpec config already exists"
  elif [ -f "$TEMPLATES_DIR/openspec-config.yaml.template" ]; then
    run mkdir -p "$PROJECT_ROOT/openspec"
    run cp "$TEMPLATES_DIR/openspec-config.yaml.template" "$PROJECT_ROOT/openspec/config.yaml"
    ok "Created openspec/config.yaml (edit placeholders)"
  else
    warn "openspec-config.yaml.template not found, skipping"
  fi

  # 1.3 Superpowers
  info "1.3 Setting up Superpowers directory..."
  run mkdir -p "$PROJECT_ROOT/docs/superpowers/plans" "$PROJECT_ROOT/docs/superpowers/specs"
  ok "Created docs/superpowers/ (plans + specs)"

  # 1.4 Mandatory skills doc
  info "1.4 Setting up mandatory-skills.md..."
  if [ -f "$PROJECT_ROOT/docs/methodology/core/mandatory-skills.md" ]; then
    ok "mandatory-skills.md already exists"
  elif [ -f "$TEMPLATES_DIR/mandatory-skills/SKILLS.md.template" ]; then
    run mkdir -p "$PROJECT_ROOT/docs/methodology/core"
    run cp "$TEMPLATES_DIR/mandatory-skills/SKILLS.md.template" "$PROJECT_ROOT/docs/methodology/core/mandatory-skills.md"
    ok "Created docs/methodology/core/mandatory-skills.md"
  fi

  # 1.5 FE-Engineering global skill
  info "1.5 Installing FE-Engineering global skill..."
  if [ -f "$HOME/.claude/skills/fe-engineering/SKILL.md" ]; then
    ok "fe-engineering skill already installed globally"
  elif [ -f "$TEMPLATES_DIR/fe-engineering/SKILL.md" ]; then
    run mkdir -p "$HOME/.claude/skills/fe-engineering"
    run cp "$TEMPLATES_DIR/fe-engineering/SKILL.md" "$HOME/.claude/skills/fe-engineering/SKILL.md"
    ok "Installed fe-engineering to ~/.claude/skills/"
  fi
  if [ -f "$HOME/.codex/skills/fe-engineering/SKILL.md" ]; then
    ok "fe-engineering skill already installed for Codex"
  elif [ -f "$TEMPLATES_DIR/fe-engineering/SKILL.md" ]; then
    run mkdir -p "$HOME/.codex/skills/fe-engineering"
    run cp "$TEMPLATES_DIR/fe-engineering/SKILL.md" "$HOME/.codex/skills/fe-engineering/SKILL.md"
    ok "Installed fe-engineering to ~/.codex/skills/"
  fi

  # 1.6 Multi-Agent global skill
  info "1.6 Installing Multi-Agent global skill..."
  if [ -f "$HOME/.claude/skills/multi-agent/SKILL.md" ]; then
    ok "multi-agent skill already installed globally"
  elif [ -f "$TEMPLATES_DIR/multi-agent/SKILL.md.template" ]; then
    run mkdir -p "$HOME/.claude/skills/multi-agent"
    run cp "$TEMPLATES_DIR/multi-agent/SKILL.md.template" "$HOME/.claude/skills/multi-agent/SKILL.md"
    ok "Installed multi-agent to ~/.claude/skills/"
  fi
  if [ -f "$HOME/.codex/skills/multi-agent/SKILL.md" ]; then
    ok "multi-agent skill already installed for Codex"
  elif [ -f "$TEMPLATES_DIR/multi-agent/SKILL.md.template" ]; then
    run mkdir -p "$HOME/.codex/skills/multi-agent"
    run cp "$TEMPLATES_DIR/multi-agent/SKILL.md.template" "$HOME/.codex/skills/multi-agent/SKILL.md"
    ok "Installed multi-agent to ~/.codex/skills/"
  fi

  # 1.7 Token compaction preservation
  info "1.7 Installing token compaction preservation..."
  if [ -f "$PROJECT_ROOT/.claude/round-contract.md" ]; then
    ok "round-contract.md already exists"
  elif [ -f "$TEMPLATES_DIR/compaction/round-contract.md.template" ]; then
    run mkdir -p "$PROJECT_ROOT/.claude/hooks" "$PROJECT_ROOT/.claude/compaction-state"
    run cp "$TEMPLATES_DIR/compaction/round-contract.md.template" "$PROJECT_ROOT/.claude/round-contract.md"
    ok "Created .claude/round-contract.md"
  fi
  if [ -f "$PROJECT_ROOT/.claude/hooks/save-state.sh" ]; then
    ok "save-state.sh already exists"
  elif [ -f "$TEMPLATES_DIR/compaction/save-state.sh.template" ]; then
    run cp "$TEMPLATES_DIR/compaction/save-state.sh.template" "$PROJECT_ROOT/.claude/hooks/save-state.sh"
    run chmod +x "$PROJECT_ROOT/.claude/hooks/save-state.sh"
    ok "Installed .claude/hooks/save-state.sh"
  fi
  if grep -q '"PreCompact"' "$PROJECT_ROOT/.claude/settings.json" "$PROJECT_ROOT/.claude/settings.local.json" 2>/dev/null; then
    ok "Compaction hooks configured"
  else
    warn "Compaction hooks not in settings. Merge the fragment from:"
    echo "  $TEMPLATES_DIR/compaction/settings-hooks.json.template"
  fi
  if [ -f "$PROJECT_ROOT/.codex/round-contract.md" ]; then
    ok "Codex round-contract.md already exists"
  elif [ -f "$TEMPLATES_DIR/compaction/codex-round-contract.md.template" ]; then
    run mkdir -p "$PROJECT_ROOT/.codex/hooks" "$PROJECT_ROOT/.codex-state"
    run cp "$TEMPLATES_DIR/compaction/codex-round-contract.md.template" "$PROJECT_ROOT/.codex/round-contract.md"
    ok "Created .codex/round-contract.md"
  fi
  if [ -f "$PROJECT_ROOT/.codex/hooks/save-state.sh" ]; then
    ok "Codex save-state.sh already exists"
  elif [ -f "$TEMPLATES_DIR/compaction/codex-save-state.sh.template" ]; then
    run cp "$TEMPLATES_DIR/compaction/codex-save-state.sh.template" "$PROJECT_ROOT/.codex/hooks/save-state.sh"
    run chmod +x "$PROJECT_ROOT/.codex/hooks/save-state.sh"
    ok "Installed .codex/hooks/save-state.sh"
  fi

  # 1.8 Global CLAUDE.md update
  info "1.8 Checking global CLAUDE.md method routing..."
  if grep -q "自动方法论路由" "$HOME/.claude/CLAUDE.md" 2>/dev/null; then
    ok "Global CLAUDE.md has method routing configured"
  elif [ -f "$TEMPLATES_DIR/fe-engineering/claude-md/global.append.md" ]; then
    warn "Global CLAUDE.md missing method routing. Append from:"
    echo "  cat $TEMPLATES_DIR/fe-engineering/claude-md/global.append.md >> ~/.claude/CLAUDE.md"
  fi

  # 1.9 Skill check summary
  step "Mandatory Skills Check"
  echo ""
  ok "OpenSpec:     $( [ -f "$PROJECT_ROOT/openspec/config.yaml" ] && echo 'configured' || echo 'TODO: openspec init' )"
  ok "Superpowers:  $( [ -d "$PROJECT_ROOT/docs/superpowers/plans" ] && echo 'configured' || echo 'TODO: mkdir' )"
  ok "Codegraph:    $(grep -r "codegraph" ~/.claude/settings.* 2>/dev/null >/dev/null && echo 'configured' || echo 'TODO: add MCP config')"

  step "Tier 1 Complete"
  echo ""
  echo -e "${GREEN}${BOLD}Next: let Agent complete the configuration${NC}"
  echo ""
  echo "  Tell the agent:"
  echo -e "    ${BOLD}\"根据项目实际情况，填充 CLAUDE.md 和 openspec/config.yaml\"${NC}"
  echo -e "    ${BOLD}\"中的 {{占位符}}，画出模块依赖图，补充构建命令和约定。\"${NC}"
  echo ""
  echo "  The agent will auto-detect your tech stack and fill all placeholders."
  echo ""
  echo -e "  Then: ${BOLD}git add -A && git commit -m 'init: AI methodology Tier 1'${NC}"
  echo ""
  echo -e "  Ready for Tier 2? Run: ${BOLD}bash $SCRIPT_DIR/init.sh --tier 2${NC}"
  echo ""
}

# ---- Tier 2: Quality Gate + Path Docs ----
do_tier2() {
  step "Tier 2: Quality Gate + Path Documents (15 min)"

  # Ensure Tier 1 is done first
  do_tier1

  # 2.1 Fitness scripts
  info "2.1 Setting up Fitness framework..."
  run mkdir -p "$PROJECT_ROOT/docs/fitness/scripts"
  if [ -f "$PROJECT_ROOT/docs/fitness/scripts/fitness.py" ]; then
    ok "Fitness runner already exists"
  elif [ -f "$TEMPLATES_DIR/fitness/fitness.py.template" ]; then
    run cp "$TEMPLATES_DIR/fitness/fitness.py.template" "$PROJECT_ROOT/docs/fitness/scripts/fitness.py"
    run chmod +x "$PROJECT_ROOT/docs/fitness/scripts/fitness.py"
    ok "Created docs/fitness/scripts/fitness.py (edit placeholders)"
  else
    warn "Fitness templates not found, skipping"
  fi

  # Add new templates without overwriting project adaptations.
  if ls "$TEMPLATES_DIR/fitness/check_"*.py.template &>/dev/null 2>&1; then
    for f in "$TEMPLATES_DIR/fitness/check_"*.py.template; do
      local_name="$(basename "$f" .template)"
      [ -f "$PROJECT_ROOT/docs/fitness/scripts/$local_name" ] && continue
      run cp "$f" "$PROJECT_ROOT/docs/fitness/scripts/$local_name"
    done
    ok "Filled missing fitness check scripts"
  fi
  if ls "$TEMPLATES_DIR/fitness/test_"*.py.template &>/dev/null 2>&1; then
    for f in "$TEMPLATES_DIR/fitness/test_"*.py.template; do
      local_name="$(basename "$f" .template)"
      [ -f "$PROJECT_ROOT/docs/fitness/scripts/$local_name" ] && continue
      run cp "$f" "$PROJECT_ROOT/docs/fitness/scripts/$local_name"
    done
    ok "Filled missing fitness self-tests"
  fi
  if [ -f "$TEMPLATES_DIR/fitness/JavaParameterScanner.java.template" ] \
      && [ ! -f "$PROJECT_ROOT/docs/fitness/scripts/JavaParameterScanner.java" ]; then
    run cp "$TEMPLATES_DIR/fitness/JavaParameterScanner.java.template" "$PROJECT_ROOT/docs/fitness/scripts/JavaParameterScanner.java"
    ok "Copied Java parameter scanner"
  fi
  if [ -f "$TEMPLATES_DIR/fitness/README.md" ] && [ ! -f "$PROJECT_ROOT/docs/fitness/README.md" ]; then
    run cp "$TEMPLATES_DIR/fitness/README.md" "$PROJECT_ROOT/docs/fitness/README.md"
    ok "Copied Fitness setup guide"
  fi

  # 2.2 Fitness rules
  info "2.2 Setting up Fitness rules..."
  if ls "$TEMPLATES_DIR/fitness/rules/"*.md.template &>/dev/null 2>&1; then
    for f in "$TEMPLATES_DIR/fitness/rules/"*.md.template; do
      local_name="$(basename "$f" .template)"
      [ -f "$PROJECT_ROOT/docs/fitness/$local_name" ] && continue
      run cp "$f" "$PROJECT_ROOT/docs/fitness/$local_name"
    done
    ok "Copied fitness rules"
  fi

  # 2.3 SDD docs
  info "2.3 Setting up SDD documentation..."
  if [ ! -f "$PROJECT_ROOT/docs/sdd/README.md" ] && [ -f "$TEMPLATES_DIR/sdd-readme.md.template" ]; then
    run mkdir -p "$PROJECT_ROOT/docs/sdd"
    run cp "$TEMPLATES_DIR/sdd-readme.md.template" "$PROJECT_ROOT/docs/sdd/README.md"
    ok "Created docs/sdd/README.md"
  fi

  # 2.4 Root path document
  info "2.4 Creating root path document..."
  if [ ! -f "$PROJECT_ROOT/AI.md" ] && [ -f "$TEMPLATES_DIR/path-document.md.template" ]; then
    run cp "$TEMPLATES_DIR/path-document.md.template" "$PROJECT_ROOT/AI.md"
    ok "Created root AI.md (edit for your project)"
  fi

  step "Tier 2 Complete"
  echo ""
  echo -e "${GREEN}${BOLD}Next: let Agent complete the configuration${NC}"
  echo ""
  echo "  Tell the agent:"
  echo -e "    ${BOLD}\"填充 fitness 脚本和规则中的占位符，为核心模块创建 AI.md\"${NC}"
  echo -e "    ${BOLD}\"路径文档，补充项目特有的编码约定。\"${NC}"
  echo ""
  echo "  Verify: python3 docs/fitness/scripts/fitness.py --tier fast --dry-run"
  echo "  Run:    python3 docs/fitness/scripts/fitness.py --tier fast"
  echo ""
}

# ---- Tier 3: Full Deployment ----
do_tier3() {
  step "Tier 3: Full Deployment (30 min)"

  do_tier2

  # 3.1 RAMER Agent templates
  info "3.1 Setting up RAMER Agent..."
  if [ -d "$PROJECT_ROOT/.claude/skills/ramer" ]; then
    ok "RAMER skill already configured"
  elif [ -f "$TEMPLATES_DIR/ramer/SKILL.md.template" ]; then
    warn "RAMER skill template available at $TEMPLATES_DIR/ramer/"
    echo "  Reference docs/methodology/core/ramer-agent.md for setup instructions"
  fi

  # 3.2 CI hints
  info "3.2 CI integration reminders..."
  echo "  Add to CI pipeline:"
  echo "    - python3 docs/fitness/scripts/fitness.py --tier fast"
  echo "    - <your frontend typecheck + build command>"
  echo "    - <your backend compile command>"

  step "Tier 3 Complete"
  echo ""
  echo -e "${GREEN}${BOLD}Final steps:${NC}"
  echo "  1. Set up pre-commit hook running fitness gate"
  echo "  2. Configure CI pipeline with fitness + typecheck + build"
  echo "  3. Expand path documents to 10+ directories"
  echo "  4. Train team on SDD + RAMER + FE-Engineering workflows"
  echo ""
}

# ---- Main ----
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  AI Methodology — One-Click Init v${VERSION}"
echo -e "${NC}"
echo ""
if [ -n "$SOURCE" ]; then
  info "Using external source: $SOURCE"
  TEMPLATES_DIR="$SOURCE/templates"
  METHODOLOGY_DIR="$SOURCE"
fi

echo "Project root:  $PROJECT_ROOT"
echo "Templates:     $TEMPLATES_DIR"
echo "Tier:          $TIER"
echo "Version:       $VERSION"
echo ""

case "$TIER" in
  1) do_tier1 ;;
  2) do_tier2 ;;
  3) do_tier3 ;;
  *) fail "Unknown tier: $TIER. Use 1, 2, or 3."; exit 1 ;;
esac

echo ""
echo -e "${GREEN}${BOLD}Done!${NC} See docs/methodology/TRANSPLANT.md for detailed instructions."
echo ""
