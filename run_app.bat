@echo off
title Chennai Transit AI Web App
color 0b
echo =======================================================
echo   Launching Chennai Intelligent Transit Recommender...
echo =======================================================
cd /d "e:\DSA1606 - Knowledge engineering\Capstone\Route Recommendation"
echo.
echo Starting Streamlit server on http://localhost:8501
echo.
streamlit run ui/app.py
pause
