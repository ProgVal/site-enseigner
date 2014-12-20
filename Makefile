all:

run:
	python -m enseigner

tests:
	./run_tests.py

coverage:
	python-coverage run --source=enseigner run_tests.py
	python-coverage html
	xdg-open htmlcov/index.html

deps:
	pip3 install flask werkzeug --user

.PHONY: run tests
