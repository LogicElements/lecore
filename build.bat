@echo off

echo === Delete distribution and log directories
set dist=".\dist\"
set log=".\Log\"
if exist %dist% rmdir /s /q %dist%
if exist %log% rmdir /s /q %log%

echo === Build Python package
py -m build

echo === Upload python package to PIP
py -m twine upload dist/*
