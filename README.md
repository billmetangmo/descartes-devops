# Backup Script Project

This project provides a script for backing up modified files on branch `01-01-2022-test` of a [Descartes devops repository](https://github.com/descartes-underwriting/devops-technical-test-data).

It's executed as github action located in `.github/workflows/backup.yml`.

## Local development

### Prequesistes

If you want to execute the project locally, you need to have:
- Python 3.10 or later
- `pip`
- `curl`
- `Taskfile`(https://taskfile.dev/installation/)

### Installation

To install all prerequisites for this project, run the following command:

```bash
task install
```

This command will:
1. Install `act` for local GitHub Actions testing.
2. Install `pipx` and `pip-tools`.
3. Install all necessary Python dependencies from `requirements-dev.txt`.


### End-to-End Backup Script Execution

Clones a test repository, executes the backup script, and compares the resulting file fingerprints with a reference.

```bash
task e2e
```

### Local CI Testing

Tests the CI pipeline locally using `act`.

```bash
task ci
```

### Clean Data

Removes the `data` directory.

```bash
task clean
```

### Static and Unit Tests

Executes static type checking and unit tests.

```bash
task test
```

### Generate Requirements

Generates `requirements.txt` and `requirements-dev.txt` using `pip-compile`.

```bash
task generate-reqs
```

### Running the Backup Script

To run the backup script manually, use the following command:

```bash
python3 script/backup_script.py --repo_dir=path_to_repo
```

You can also specify optional parameters for `start_date` and `end_date`:

```bash
python3 script/backup_script.py --repo_dir=path_to_repo --start_date=01-01-2023 --end_date=31-12-2023
```

