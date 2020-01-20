build-dist:
	python3 setup.py sdist bdist_wheel

upload-dist:
	python3 -m twine upload dist/*

clean:
	rm -rf build dist .pytest_cache *.egg-info

build-docs:
	sphinx-apidoc -o docs/ . setup.py "*conftest*"
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	$(MAKE) -C docs doctest

docs: build-docs
	open docs/_build/html/index.html
