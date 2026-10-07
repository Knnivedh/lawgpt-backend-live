@echo off
echo ================================================================================
echo STARTING COMPREHENSIVE TEST SERVER
echo ================================================================================
echo.
cd /d %~dp0
python comprehensive_accuracy_test_server.py
pause

