"""
Root entry point for Streamlit Community Cloud deployment.
Directly invokes ui/app.py
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ui.app import main

if __name__ == "__main__":
    main()
