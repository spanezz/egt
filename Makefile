PYTHON_ENVIRONMENT := PYTHONASYNCDEBUG=1 PYTHONDEBUG=1

check: flake8 mypy

format: pyupgrade autoflake isort black 

pyupgrade:
	pyupgrade --exit-zero-even-if-changed --py311-plus egt $(shell find egtlib test -name "*.py")

black:
	black egt egtlib test

autoflake:
	autoflake --in-place --recursive egtlib test 

isort:
	isort egtlib test

flake8:
	flake8 egtlib test 

mypy:
	mypy egt egtlib test

unittest:
	$(PYTHON_ENVIRONMENT) nose2-3

coverage:
	$(PYTHON_ENVIRONMENT) nose2-3 --coverage egtlib --coverage-report html 

.PHONY: check pyupgrade black mypy unittest coverage
