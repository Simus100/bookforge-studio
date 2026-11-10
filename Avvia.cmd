@echo off
cd /d "%~dp0"
title BookForge Studio
python "%~dp0bootstrap.py"
if errorlevel 1 pause
