import packaging.version
from pallets_sphinx_themes import get_version
from pallets_sphinx_themes import ProjectLink

# -- Project information -----------------------------------------------------

project = "remerkleable"
copyright = "2019 protolambda"
author = "protolambda"
release, version = get_version("remerkleable")


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx_issues',
    'pallets_sphinx_themes',
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.doctest',
    'sphinx.ext.coverage',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
}

issues_github_path = "protolambda/remerkleable"

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'flask'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_context = {
    "project_links": [
        ProjectLink("PyPI releases", "https://pypi.org/project/remerkleable/"),
        ProjectLink("Source Code", "https://github.com/protolambda/remerkleable/"),
        ProjectLink("Issue Tracker", "https://github.com/protolambda/remerkleable/issues/"),
        ProjectLink("Contact", "https://twitter.com/protolambda/"),
    ]
}
html_sidebars = {
    "index": ["project.html", "localtoc.html", "searchbox.html"],
    "**": ["localtoc.html", "relations.html", "searchbox.html"],
}
singlehtml_sidebars = {"index": ["project.html", "localtoc.html"]}
html_favicon = "_static/logo.png"
html_logo = "_static/logo.png"
html_title = "Remerkleable Documentation ({})".format(version)
html_show_sourcelink = False


# -- Theme configuration -----------------------------------------------------

html_theme_options = {
    'logo': 'logo.svg',
    'github_user': 'protolambda',
    'github_repo': 'remerkleable',
    'github_banner': True,
    'badge_branch': 'master',
    'show_powered_by': False,
}

# -- Extension configuration -------------------------------------------------
