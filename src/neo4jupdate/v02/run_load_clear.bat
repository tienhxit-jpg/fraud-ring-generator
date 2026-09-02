@echo off
REM Neo4j Data Loader Script (WITH CLEAR DATABASE OPTION)
REM CANH BAO: Script nay se XOA TOAN BO du lieu trong database truoc khi load

setlocal

REM Cau hinh Neo4j connection
set NEO4J_URI=neo4j://127.0.0.1:7687
set NEO4J_USERNAME=neo4j
set NEO4J_PASSWORD=VoThiSau8a!
set NEO4J_DATABASE=neo4j

REM Duong dan den thu muc chua du lieu CSV
set DATA_DIR=./data/synthetic/v2/raw

echo ========================================
echo CANH BAO: CLEAR DATABASE MODE
echo ========================================
echo Script nay se XOA TOAN BO du lieu trong database!
echo.
set /p CONFIRM="Ban co chac chan muon xoa du lieu? (yes/no): "

if /i not "%CONFIRM%"=="yes" (
    echo.
    echo [CANCELLED] Huy thao tac.
    pause
    exit /b 0
)

echo.
echo [INFO] Bat dau xoa va load du lieu...

REM Chay script Python voi tuy chon --clear
python ./src/neo4jupdate/v02/load_data.py ^
    --uri %NEO4J_URI% ^
    --username %NEO4J_USERNAME% ^
    --password %NEO4J_PASSWORD% ^
    --database %NEO4J_DATABASE% ^
    --data-dir %DATA_DIR% ^
    --clear

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Data loading failed!
    pause
    exit /b %errorlevel%
)

echo.
echo [SUCCESS] Data loaded successfully!
pause
