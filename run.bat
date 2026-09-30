@echo off
REM Starts the app from source (needs Python 3.10+ from python.org).
python -m pip install --quiet -r requirements.txt
start "" pythonw main.pyw
