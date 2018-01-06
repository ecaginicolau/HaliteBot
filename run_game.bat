@echo off
rem SET PYTHONPATH=%~dp0
SET RAMPA_LOG_LEVEL=DEBUG
echo [Building]
python setup.py build_ext --inplace
if errorlevel 1 (
   echo [Error building]
   exit /b %errorlevel%
)
rem halite.exe -s 4035208291 -t -d "240 160" "python MyBot.py" "python .\opponents\ClosestTargetBot.py"
rem halite.exe -s 4035208291 -t -d "240 160" "python MyBot.py" "python .\opponents\ClosestTargetBot.py"
rem halite.exe -d "240 160" "python MyBot.py" "python .\opponents\ClosestTargetBot.py"
rem halite.exe -s 1221653447 -d "240 160" "python MyBot.py" "python .\opponents\ClosestTargetBot.py"
rem halite.exe -s 2910899301 -d "312 206" "python MyBot.py" "..\HaliteBotV43\run_bot.bat"
rem halite.exe -s 2910899301 -d "312 206" "python MyBot.py" "..\HaliteBotV59\run_bot.bat"
rem halite.exe -d "240 160" "python MyBot.py" "python ..\HaliteHerve\MyBot.py"
rem halite.exe -s 3982948433 -d "312 206" "python MyBot.py" "..\HaliteBotV59\run_bot.bat"
halite.exe -s 2293387012 -d "312 206" "python MyBot.py" "..\HaliteBotV59\run_bot.bat"

