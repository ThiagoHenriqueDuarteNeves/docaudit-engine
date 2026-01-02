@echo off
REM Calls the PowerShell script to start zrok tunnels in headless mode
powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File ".\zrok-headless.ps1"
