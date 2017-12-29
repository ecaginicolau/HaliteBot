@echo off
SET PYTHONPATH=%cd%
echo [Building]
python setup.py build_ext --inplace
if errorlevel 1 (
   echo [Error building]
   exit /b %errorlevel%
)
rem halite.exe -s 4035208291 -t -d "240 160" "python MyBot.py" "python .\opponents\ClosestTargetBot.py"
rem halite.exe -s 4035208291 -t -d "240 160" "python MyBot.py" "python .\opponents\ClosestTargetBot.py"
halite.exe -d "240 160" "python MyBot.py" "python .\opponents\ClosestTargetBot.py"
rem halite.exe -r -q -d "240 160" "python MyBot.py" "python .\opponents\ClosestTargetBot.py"

