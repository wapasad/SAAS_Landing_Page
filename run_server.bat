@echo off
cd /d "%~dp0"
echo ===================================================
echo   Starting Nexus SaaS Server and Database
echo   Website: http://localhost:5000
echo   Admin Dashboard: http://localhost:5000/admin
echo ===================================================
echo.
..\.venv\Scripts\python.exe app.py
pause
