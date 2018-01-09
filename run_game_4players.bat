@echo off
rem SET PYTHONPATH=%~dp0
SET RAMPA_LOG_LEVEL=DEBUG
echo [Building]
python setup.py build_ext --inplace
if errorlevel 1 (
   echo [Error building]
   exit /b %errorlevel%
)
halite.exe -d "384 256" "python MyBot.py" "..\HaliteBotV59\run_bot.bat" "..\HaliteBotV59\run_bot.bat" "..\HaliteBotV59\run_bot.bat"

