# revitpy-cli

Developer tooling for RevitPy projects: scaffolding, building, a hot-reload
development server, package publishing/installation, and environment
diagnostics.

The console script is **`revitpy-dev`**. It is deliberately not called
`revitpy`, so it can be installed next to the core `revitpy` package without the
two commands clashing.

## Installation

```bash
pip install ./cli            # from a RevitPy checkout
pip install "./cli[dev]"     # plus test and lint tooling
```

Requires Python 3.11+.

## Usage

```bash
revitpy-dev --help           # list command groups
revitpy-dev <group> --help   # list commands in a group
```

### `create`: scaffold projects

| Command | Purpose |
| --- | --- |
| `revitpy-dev create project NAME [-t TEMPLATE] [-o DIR] [--no-git] [--no-interactive] [--force]` | Generate a project from a cookiecutter template |
| `revitpy-dev create list-templates` | Show built-in, cached, and custom templates |
| `revitpy-dev create add-template URL [--name NAME] [--update]` | Register a template from a repository URL or path |
| `revitpy-dev create remove-template NAME [--force]` | Remove a registered template |

Built-in templates: `basic-script` and `addin`.

### `build`: package and validate

| Command | Purpose |
| --- | --- |
| `revitpy-dev build package [PATH] [-o DIR] [--no-validate] [--include-tests] [--sign]` | Build a distributable package |
| `revitpy-dev build validate [PATH] [--fix]` | Check project structure and configuration |
| `revitpy-dev build clean [--all]` | Remove build artifacts |

### `dev`: development server

| Command | Purpose |
| --- | --- |
| `revitpy-dev dev server [PATH] [--host H] [--port P] [--ws-port P] [--no-reload] [--watch GLOB] [--ignore GLOB]` | Run the dev server with WebSocket hot reload |
| `revitpy-dev dev watch [PATH] [--pattern GLOB] [--exec CMD] [--ignore GLOB]` | Watch files and run a command on change |
| `revitpy-dev dev status [PATH]` | Show dev-server and project status |

### `publish`: registry publishing

| Command | Purpose |
| --- | --- |
| `revitpy-dev publish package [FILE] [--registry URL] [--dry-run]` | Upload a built package |
| `revitpy-dev publish login [--registry URL] [--username U] [--token T]` | Store registry credentials |
| `revitpy-dev publish logout [--registry URL] [--all]` | Remove stored credentials |
| `revitpy-dev publish status [--registry URL] [--package NAME]` | Show registry and package status |
| `revitpy-dev publish list-packages [--user U] [--search Q] [--limit N]` | List packages in a registry |

### `install`: package management

`revitpy-dev install package`, `uninstall`, `list`, `show`, `search`, and
`update` install and inspect RevitPy packages.

### `doctor`: diagnostics

| Command | Purpose |
| --- | --- |
| `revitpy-dev doctor check [--verbose] [--fix] [--output FILE]` | Diagnose the environment (Python, Revit, dependencies) |
| `revitpy-dev doctor env [--format table\|json\|env]` | Print environment information |
| `revitpy-dev doctor performance [--benchmark] [--profile]` | System resource and performance report |
| `revitpy-dev doctor cleanup [--logs] [--backup] [--dry-run]` | Clean caches and logs |

### Other commands

| Command | Purpose |
| --- | --- |
| `revitpy-dev version` | Print the CLI version |
| `revitpy-dev config --show \| --edit \| --reset` | Manage CLI configuration |
| `revitpy-dev completion [--shell SHELL] [--install]` | Shell completion (bash, zsh, fish) |
| `revitpy-dev plugins --list \| --install NAME \| --uninstall NAME` | Manage CLI plugins |

## Configuration

Settings are read from the first of these files that exists:

1. `./.revitpy.toml`
2. `./pyproject.toml` (`[tool.revitpy]` table)
3. `~/.revitpy/config.toml`
4. `~/.revitpy.toml`

## License

MIT
