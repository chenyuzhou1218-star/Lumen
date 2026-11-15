@echo off
rem Code Doctor in any terminal: put this folder on PATH, then run `codedoctor fix "..."` in your project folder.
"%~dp0..\.venv\Scripts\codedoctor.exe" %*
