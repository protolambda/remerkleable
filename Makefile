build-dist:
	python3 setup.py sdist bdist_wheel

upload-dist:
	python3 -m twine upload dist/*

clean:
	rm -rf build dist .pytest_cache *.egg-info
