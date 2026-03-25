@echo off
echo Starting App Listing Studio...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo Something went wrong. Make sure Python and requirements are installed.
    echo Run: pip install -r requirements.txt
    pause
)
