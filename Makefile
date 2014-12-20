all:

run:
	python -m enseigner

deps:
	pip3 install flask --user

.PHONY: run
