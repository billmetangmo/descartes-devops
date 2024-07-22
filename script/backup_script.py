import os
import asyncio
import aiofiles
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict
import git
import multiprocessing
import concurrent.futures
from loguru import logger
from tabulate import tabulate
import sys
import fire  # type: ignore

class ValidationError(Exception):
    """Exception for backup parameters."""
    pass

class BackupError(Exception):
    """Custom exception for backup errors."""
    pass

def get_current_branch(repo: git.Repo) -> str:
    return repo.active_branch.name

def validate(repo_dir: str, backup_dir: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> None:
    """
        Validate the backup parameters.
    """
    # Check if the backup directory exists, otherwise create it
    if not os.path.exists(backup_dir):
        raise ValidationError(f"The backup folder '{backup_dir}' does not exist")

    # Check if the repository directory exists
    if not os.path.exists(repo_dir):
        raise ValidationError(f"The repository directory '{repo_dir}' does not exist.")

    # Check if the directory is a valid git repository
    try:
        repo = git.Repo(repo_dir)
    except git.exc.InvalidGitRepositoryError as e:
        raise ValidationError(
            f"The directory '{repo_dir}' is not a valid Git repository."
        ) from e

    # Date validation
    today = datetime.now()
    if start_date:
        start_date_obj = datetime.strptime(start_date, '%d-%m-%Y')
        if start_date_obj > today:
            raise ValidationError(f"The start date '{start_date}' is later than today's date")

    if end_date:
        end_date_obj = datetime.strptime(end_date, '%d-%m-%Y')
        if start_date and start_date_obj > end_date_obj:
            raise ValidationError(f"The start date '{start_date}' is after the end date '{end_date}'.")

def get_commits(repo: git.Repo, branch: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[git.Commit]:
    """
        Get the commits from a Git repository.

        Args:
            repo (git.Repo): The Git repository.
            branch (str): The branch name.
            start_date (Optional[str]): The start date in the format '%d-%m-%Y'. Defaults to None.
            end_date (Optional[str]): The end date in the format '%d-%m-%Y'. Defaults to None.

        Returns:
            List[git.Commit]: A list of Git commits.
    """

    if start_date is None and end_date is None:
        return list(repo.iter_commits(branch))
    
    # Convert dates to datetime objects
    start_date_obj = datetime.strptime(start_date, '%d-%m-%Y') if start_date else None
    end_date_obj = datetime.strptime(end_date, '%d-%m-%Y') if end_date else None

    commits: List[git.Commit] = []
    for commit in repo.iter_commits(branch):
        commit_date = datetime.fromtimestamp(commit.committed_date)
        if start_date_obj and commit_date < start_date_obj:
            continue
        if end_date_obj and commit_date > end_date_obj:
            continue
        commits.append(commit)
    return commits

def get_changed_files(args: Tuple[git.Repo, str]) -> Tuple[str, List[str]]:
    """
        Get the changed files for a specific commit in a Git repository.

        Args:
            args (Tuple[git.Repo, str]): A tuple containing the Git repository and the commit SHA.

        Returns:
            Tuple[str, List[str]]: A tuple containing the commit SHA and a list of changed file names.
    """
    repo, commit_sha = args
    return commit_sha, repo.git.show('--pretty=', '--name-only', commit_sha).splitlines()

async def read_file_content(repo: git.Repo, commit: git.Commit, file: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, repo.git.show, f'{commit.hexsha}:{file}')

async def write_file_content(file_path: str, content: str) -> None:
    async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
        await f.write(content)

async def process_file(repo: git.Repo, commit: git.Commit, file: str, commit_backup_dir: str, failed_files: List[Tuple[str, str]]) -> None:
    """
        Given a commit and a file, save the file in commit_backup_dir and log errors in failed_files.
    """

    try:
        file_content = await read_file_content(repo, commit, file)
        file_path = os.path.join(commit_backup_dir, file)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        await write_file_content(file_path, file_content)
    except git.exc.GitCommandError as e:
        if 'does not exist in' in str(e):
            logger.warning(f"The file {file} was deleted in commit {commit.hexsha}")
        else:
            failed_files.append((commit.hexsha, file))
            raise BackupError(
                f"Error processing file {file}: {str(e)}"
            ) from e
    except Exception as e:
        failed_files.append((commit.hexsha, file))
        raise BackupError(
            f"Error processing file {file}: {str(e)}"
        ) from e

async def process_commit(repo: git.Repo, commit_sha: str, files: List[str], backup_dir: str, failed_files: List[Tuple[str, str]]) -> None:
    """
        Given a commit and a list of files, apply process_file for each.
    """

    try:    
        commit = repo.commit(commit_sha)
        commit_backup_dir = os.path.join(backup_dir, commit_sha)
        os.makedirs(commit_backup_dir, exist_ok=True)
        tasks = [process_file(repo, commit, file, commit_backup_dir, failed_files) for file in files]
        await asyncio.gather(*tasks)
    except BackupError as e:
        logger.exception(f"Error backing up commit {commit_sha}: {str(e)}")

async def backup_files(repo: git.Repo, backup_dir: str, current_branch: str, start_date: Optional[str], end_date: Optional[str], failed_files: List[Tuple[str, str]]) -> None:

    commit_shas = get_commits(repo, current_branch, start_date, end_date)

    # Use ProcessPoolExecutor to get modified files in list as this can be considered as CPU and I/O intensive
    with concurrent.futures.ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        future_to_commit = {executor.submit(get_changed_files, (repo, commit.hexsha)): commit.hexsha for commit in commit_shas}
        
        commit_files: Dict[str, List[str]] = {}
        for future in concurrent.futures.as_completed(future_to_commit):
            commit_sha = future_to_commit[future]
            try:
                result = future.result()
                commit_files[result[0]] = result[1]
            except Exception as e:
                failed_files.append((commit_sha, "Files could not be retrieved"))
                logger.exception(f"An error occurred while retrieving files for commit {commit_sha}: {str(e)}")

    # Process commits asynchronously as it's only I/O intensive
    await asyncio.gather(*[process_commit(repo, commit_sha, files, backup_dir, failed_files) for commit_sha, files in commit_files.items()])

async def main(repo_dir: str = ".", backup_dir: str = "./data", start_date: Optional[str] = None, end_date: Optional[str] = None) -> None:

    failed_files: List[Tuple[str, str]] = []

    try:
        validate(repo_dir, backup_dir, start_date, end_date)
        repo = git.Repo(repo_dir)
        current_branch = get_current_branch(repo)
        logger.info(f"Starting backup of branch {current_branch}")
        await backup_files(repo, backup_dir, current_branch, start_date, end_date, failed_files)
        logger.info(f"Finished backup of branch {current_branch}")
        if failed_files:
            headers = ["Commit SHA", "File"]
            table = tabulate(failed_files, headers=headers, tablefmt="grid")
            logger.critical(f"\nFiles that failed during backup:\n{table}")
            sys.exit(1)
        else:
            logger.info("Backup completed successfully.")
    except ValidationError as e:
        logger.exception(f"Validation error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    fire.Fire(main)
