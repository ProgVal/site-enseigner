all:

run:
	python -m enseigner

debugrun:
	ENSEIGNER_CONFIG=example_config.json python -m enseigner

tests:
	ENSEIGNER_CONFIG=example_config.json ./run_tests.py

coverage:
	python-coverage run --source=enseigner run_tests.py
	python-coverage html
	xdg-open htmlcov/index.html

db:
	./make_db.py

deps:
	pip3 install flask werkzeug --user

.PHONY: run tests
