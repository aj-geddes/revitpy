# {{ cookiecutter.project_name }}

{{ cookiecutter.project_description }}

## Description

This is a RevitPy script that automates tasks in Autodesk Revit using Python.

## Requirements

- Autodesk Revit {% for version, enabled in cookiecutter.revit_versions.items() %}{% if enabled == 'y' %}{{ version }}{% if not loop.last %}, {% endif %}{% endif %}{% endfor %}
- Python {{ cookiecutter.python_version }}+
- RevitPy framework

## Installation

1. Clone this repository:
```bash
git clone https://github.com/{{ cookiecutter.author_name.lower().replace(' ', '') }}/{{ cookiecutter.project_slug }}.git
cd {{ cookiecutter.project_slug }}
```

2. Install dependencies:
```bash
pip install -e .[dev]
```

## Usage

### Running the Script

Load the script in Revit using RevitPy:

```python
import revitpy
from {{ cookiecutter.project_slug.replace('-', '_') }} import main

# Run the main function
main.run()
```

### Development

{% if cookiecutter.use_pytest == 'y' -%}
Run tests:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov={{ cookiecutter.project_slug.replace('-', '_') }} --cov-report=html
```
{% endif %}

{% if cookiecutter.use_black == 'y' -%}
Format code:
```bash
black src/ tests/
isort src/ tests/
```
{% endif %}

{% if cookiecutter.use_mypy == 'y' -%}
Type checking:
```bash
mypy src/
```
{% endif %}

Linting:
```bash
ruff check src/ tests/
```

## Project Structure

```
{{ cookiecutter.project_slug }}/
├── src/
│   └── {{ cookiecutter.project_slug.replace('-', '_') }}/
│       ├── __init__.py
│       └── main.py
{% if cookiecutter.use_pytest == 'y' -%}
├── tests/
│   ├── __init__.py
│   └── test_main.py
{% endif -%}
├── README.md
├── pyproject.toml
└── .gitignore
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the {{ cookiecutter.license }} License - see the [LICENSE](LICENSE) file for details.

## Author

**{{ cookiecutter.author_name }}**
- Email: {{ cookiecutter.author_email }}

## Acknowledgments

- Built with [RevitPy](https://revitpy.dev) framework
- Created using RevitPy CLI project template