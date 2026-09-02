@echo off
REM setup.bat

echo Setting up Fraud Ring Detection Synthetic Data Generator...

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
pip install --upgrade pip

REM Install dependencies
echo Installing dependencies...
pip install -r src/generators/v02/requirements.txt

REM Create output directories
echo Creating output directories...
mkdir data\synthetic\raw
mkdir data\synthetic\processed
mkdir data\synthetic\ground_truth

echo Setup complete!
echo To activate the environment, run: venv\Scripts\activate.bat
echo To generate data, run: python src/generators/v02/main.py