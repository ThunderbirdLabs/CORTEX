#!/bin/bash
# Check if required dependencies are installed for master setup

echo "🔍 Checking dependencies for CORTEX Master Setup..."
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python version: $PYTHON_VERSION"

# Check bcrypt
if python3 -c "import bcrypt" 2>/dev/null; then
    echo "✅ bcrypt installed"
else
    echo "❌ bcrypt NOT installed"
    echo "   Install with: pip install bcrypt"
    MISSING=1
fi

# Check supabase
if python3 -c "import supabase" 2>/dev/null; then
    echo "✅ supabase-py installed"
else
    echo "❌ supabase-py NOT installed"
    echo "   Install with: pip install supabase"
    MISSING=1
fi

echo ""

if [ "$MISSING" = "1" ]; then
    echo "📦 Install missing dependencies:"
    echo "   pip install bcrypt supabase"
    echo ""
    exit 1
else
    echo "🎉 All dependencies installed! Ready to run setup_master.py"
    exit 0
fi
