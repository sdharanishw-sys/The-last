@echo off
title Twin Reference Adaptive BMS Dashboard
echo ============================================================
echo  TWIN REFERENCE ADAPTIVE BATTERY MANAGEMENT SYSTEM
echo  WITH DEVIATION ATTRIBUTION FOR PERSONALIZED EV BATTERY HEALTH
echo ============================================================
echo.
echo  Starting Streamlit dashboard...
echo  Open your browser at: http://localhost:8501
echo.
cd /d "D:\Python Battery Simulation Model\The last"
"C:\Users\dhara\AppData\Local\Python\pythoncore-3.14-64\Scripts\streamlit.exe" run app.py --server.port 8501 --server.headless false --browser.gatherUsageStats false
pause
