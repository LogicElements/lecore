# Build [note to myself]

In command line (not venv) run:

Update PIP, build, twine
```
python -m pip install --upgrade build
python -m pip install --upgrade pip
python -m pip install --upgrade twine
```

Run Build
````
py -m build
````


Upload package to pypi.org server

```
py -m twine upload dist/*
```

# venv

Enable activating venv

```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Create and activate venv
```
py -m venv .\venv --clear
.\venv\Scripts\activate
```

Download package and run tests

```
pip install lecore
py .\tests\test_phase_det.py
```

