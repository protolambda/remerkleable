build-dist:
	python3 setup.py sdist bdist_wheel

check-dist:
	python3 -m twine check dist/*

upload-dist:
	python3 -m twine upload dist/*

install:
	python3 -m venv venv && . venv/bin/activate; pip3 install .

lint:
	cd remerkleable && flake8 . --count --exit-zero --max-complexity=15 --max-line-length=127 --statistics

clean:
	rm -rf build dist .pytest_cache *.egg-info

build-docs:
	sphinx-apidoc -o docs/ . setup.py "*conftest*"
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	$(MAKE) -C docs doctest

docs: build-docs
	open docs/_build/html/index.html
