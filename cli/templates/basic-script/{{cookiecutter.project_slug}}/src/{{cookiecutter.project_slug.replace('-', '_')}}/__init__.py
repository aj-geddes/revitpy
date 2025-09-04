"""{{ cookiecutter.project_description }}"""

__version__ = "{{ cookiecutter.version }}"
__author__ = "{{ cookiecutter.author_name }}"
__email__ = "{{ cookiecutter.author_email }}"

from .main import run

__all__ = ["run"]