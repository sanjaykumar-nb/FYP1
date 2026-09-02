import sys
from pathlib import Path

# Add the ai-service root directory to Python path
ai_service_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ai_service_root))