#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
#   OMI — Automated Linux Installer
#   Usage: bash install_linux.sh [GEMINI_API_KEY]
#   Or:    GEMINI_API_KEY=AIza... bash install_linux.sh
# ═══════════════════════════════════════════════════════

set -e

# ── Colors ──────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

step()  { echo -e "\n${CYAN}${BOLD}──────────────────────────────────────────────────${NC}"; echo -e "  ${BOLD}$1${NC}"; echo -e "${CYAN}──────────────────────────────────────────────────${NC}"; }
ok()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC}  $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; exit 1; }

echo -e "\n${BOLD}═══════════════════════════════════════════════════${NC}"
echo -e "   ${BOLD}OMI ASSISTANT — AUTOMATED LINUX INSTALLER${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════${NC}\n"

# ── Resolve project root (directory of this script) ────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_SCRIPT="$SCRIPT_DIR/main.py"
VENV_DIR="$SCRIPT_DIR/.venv"
ENV_FILE="$SCRIPT_DIR/.env"

# ── Step 0: Gemini API key ──────────────────────────────
step "🔑 Gemini API Key"

API_KEY="${1:-${GEMINI_API_KEY:-}}"

if [ -z "$API_KEY" ]; then
    echo -e "  No API key provided. Get one free at:"
    echo -e "  ${CYAN}https://aistudio.google.com/apikey${NC}\n"
    read -rp "  Paste your API key here (starts with AIza...): " API_KEY
fi

if [[ "$API_KEY" != AIza* ]]; then
    warn "Key doesn't look like a standard Gemini key (AIza...) — continuing anyway."
fi

echo "GEMINI_API_KEY=$API_KEY" > "$ENV_FILE"
ok "API key saved to .env"

# ── Step 1: System dependencies ─────────────────────────
step "🔧 Checking system dependencies"

# Helper to run ldconfig on various paths
run_ldconfig() {
    if command -v ldconfig &>/dev/null; then
        ldconfig -p
    elif [ -x /sbin/ldconfig ]; then
        /sbin/ldconfig -p
    elif [ -x /usr/sbin/ldconfig ]; then
        /usr/sbin/ldconfig -p
    fi
}

# Detect package manager
if command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt"
elif command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
elif command -v yum &>/dev/null; then
    PKG_MANAGER="yum"
elif command -v zypper &>/dev/null; then
    PKG_MANAGER="zypper"
else
    PKG_MANAGER="unknown"
fi

MISSING_DEPS=()

# Check for commands
command -v python3 &>/dev/null || MISSING_DEPS+=("python3")
command -v pip3   &>/dev/null || MISSING_DEPS+=("pip")
python3 -c "import venv" 2>/dev/null || MISSING_DEPS+=("venv")
command -v git    &>/dev/null || MISSING_DEPS+=("git")

# Check for libraries
LD_LIBS=$(run_ldconfig)
if ! echo "$LD_LIBS" | grep -q libportaudio; then
    MISSING_DEPS+=("portaudio")
fi
if ! echo "$LD_LIBS" | grep -q libX11; then
    MISSING_DEPS+=("x11")
fi
if ! echo "$LD_LIBS" | grep -q libXrandr; then
    MISSING_DEPS+=("xrandr")
fi
if ! echo "$LD_LIBS" | grep -q -E 'libGL\.so|libGLvnd'; then
    MISSING_DEPS+=("gl")
fi

PKGS_TO_INSTALL=()

for dep in "${MISSING_DEPS[@]}"; do
    case "$PKG_MANAGER" in
        apt)
            case "$dep" in
                python3)   PKGS_TO_INSTALL+=("python3") ;;
                pip)       PKGS_TO_INSTALL+=("python3-pip") ;;
                venv)      PKGS_TO_INSTALL+=("python3-venv") ;;
                git)       PKGS_TO_INSTALL+=("git") ;;
                portaudio) PKGS_TO_INSTALL+=("libportaudio2") ;;
                x11)       PKGS_TO_INSTALL+=("libx11-dev") ;;
                xrandr)    PKGS_TO_INSTALL+=("libxrandr-dev") ;;
                gl)        PKGS_TO_INSTALL+=("libgl1") ;;
            esac
            ;;
        pacman)
            case "$dep" in
                python3)   PKGS_TO_INSTALL+=("python") ;;
                pip)       PKGS_TO_INSTALL+=("python-pip") ;;
                venv)      ;; # included in python on Arch
                git)       PKGS_TO_INSTALL+=("git") ;;
                portaudio) PKGS_TO_INSTALL+=("portaudio") ;;
                x11)       PKGS_TO_INSTALL+=("libx11") ;;
                xrandr)    PKGS_TO_INSTALL+=("libxrandr") ;;
                gl)        PKGS_TO_INSTALL+=("libglvnd") ;;
            esac
            ;;
        dnf|yum)
            case "$dep" in
                python3)   PKGS_TO_INSTALL+=("python3") ;;
                pip)       PKGS_TO_INSTALL+=("python3-pip") ;;
                venv)      PKGS_TO_INSTALL+=("python3-venv") ;;
                git)       PKGS_TO_INSTALL+=("git") ;;
                portaudio) PKGS_TO_INSTALL+=("portaudio") ;;
                x11)       PKGS_TO_INSTALL+=("libX11-devel") ;;
                xrandr)    PKGS_TO_INSTALL+=("libXrandr-devel") ;;
                gl)        PKGS_TO_INSTALL+=("libglvnd") ;;
            esac
            ;;
        zypper)
            case "$dep" in
                python3)   PKGS_TO_INSTALL+=("python3") ;;
                pip)       PKGS_TO_INSTALL+=("python3-pip") ;;
                venv)      PKGS_TO_INSTALL+=("python3-venv") ;;
                git)       PKGS_TO_INSTALL+=("git") ;;
                portaudio) PKGS_TO_INSTALL+=("portaudio") ;;
                x11)       PKGS_TO_INSTALL+=("libX11-devel") ;;
                xrandr)    PKGS_TO_INSTALL+=("libXrandr-devel") ;;
                gl)        PKGS_TO_INSTALL+=("Mesa-libGL1") ;;
            esac
            ;;
    esac
done

if [ ${#PKGS_TO_INSTALL[@]} -gt 0 ]; then
    warn "Missing system dependencies: ${MISSING_DEPS[*]}"
    if [ "$PKG_MANAGER" = "apt" ]; then
        echo -e "  Installing via apt...\n"
        sudo apt-get update -qq
        sudo apt-get install -y "${PKGS_TO_INSTALL[@]}"
        ok "System packages installed"
    elif [ "$PKG_MANAGER" = "pacman" ]; then
        echo -e "  Installing via pacman...\n"
        sudo pacman -Syu --needed --noconfirm "${PKGS_TO_INSTALL[@]}"
        ok "System packages installed"
    elif [ "$PKG_MANAGER" = "dnf" ]; then
        echo -e "  Installing via dnf...\n"
        sudo dnf install -y "${PKGS_TO_INSTALL[@]}"
        ok "System packages installed"
    elif [ "$PKG_MANAGER" = "yum" ]; then
        echo -e "  Installing via yum...\n"
        sudo yum install -y "${PKGS_TO_INSTALL[@]}"
        ok "System packages installed"
    elif [ "$PKG_MANAGER" = "zypper" ]; then
        echo -e "  Installing via zypper...\n"
        sudo zypper install -y "${PKGS_TO_INSTALL[@]}"
        ok "System packages installed"
    else
        warn "Could not automatically install packages for your distribution."
        warn "Please manually install equivalent packages for: ${MISSING_DEPS[*]}"
        read -rp "  Press Enter to continue installation anyway, or Ctrl+C to abort..."
    fi
else
    ok "All system dependencies present"
fi

# ── Step 2: Python virtual environment ──────────────────
step "🐍 Creating Python virtual environment"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    ok "Virtual environment created at .venv"
else
    ok "Virtual environment already exists — skipping"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# ── Step 3: Python packages ─────────────────────────────
step "📦 Installing Python dependencies"

$VENV_PIP install --upgrade pip -q

PACKAGES=(
    "google-genai"
    "mss"
    "Pillow"
    "pystray"
    "sounddevice"
    "numpy"
    "pyautogui"
    "requests"
    "opencv-python"
    "psutil"
    "pyperclip"
    "python-dotenv"
)

for pkg in "${PACKAGES[@]}"; do
    echo -e "  → Installing ${pkg}..."
    $VENV_PIP install "$pkg" -q
done

ok "Core packages installed"

# Optional: Whisper for microphone transcription
echo
read -rp "  Install Whisper for microphone transcription? (y/N): " INSTALL_WHISPER
INSTALL_WHISPER="${INSTALL_WHISPER,,}"
if [ "$INSTALL_WHISPER" = "y" ]; then
    echo -e "  → Installing openai-whisper (this may take a while)..."
    $VENV_PIP install openai-whisper -q
    ok "Whisper installed"
else
    warn "Whisper skipped. Microphone transcription will be disabled."
fi

# ── Step 4: Autostart (XDG .desktop) ────────────────────
step "🚀 Setting up autostart on login"

AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

DESKTOP_FILE="$AUTOSTART_DIR/OmiAssistant.desktop"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Exec="$VENV_PYTHON" "$MAIN_SCRIPT"
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=OmiAssistant
Comment=Personal AI Assistant powered by Gemini
EOF

chmod +x "$DESKTOP_FILE"
ok "Autostart entry created: $DESKTOP_FILE"

# ── Step 5: Launch now ───────────────────────────────────
step "▶  Launch"

echo
read -rp "  Launch OMI now? (y/N): " LAUNCH_NOW
LAUNCH_NOW="${LAUNCH_NOW,,}"
if [ "$LAUNCH_NOW" = "y" ]; then
    echo -e "  Starting OMI in the background..."
    nohup "$VENV_PYTHON" "$MAIN_SCRIPT" > /tmp/omi.log 2>&1 &
    ok "OMI started! Logs: /tmp/omi.log"
else
    echo -e "\n  To start manually:"
    echo -e "  ${CYAN}$VENV_PYTHON $MAIN_SCRIPT${NC}"
fi

# ── Done ─────────────────────────────────────────────────
echo -e "\n${BOLD}═══════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}${BOLD}✅  Installation complete!${NC}"
echo -e "  OMI will start automatically on your next login."
echo -e "${BOLD}═══════════════════════════════════════════════════${NC}\n"
