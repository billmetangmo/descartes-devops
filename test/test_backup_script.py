import pytest
import os
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime
import git
from script import backup_script

def test_get_changed_files():
    mock_repo = Mock()
    mock_repo.git.show.return_value = "file1.txt\nfile2.txt"
    commit_sha = "abc123"
    result = backup_script.get_changed_files((mock_repo, commit_sha))
    assert result == (commit_sha, ["file1.txt", "file2.txt"])

def test_get_commits():
    mock_repo = Mock()
    branch = 'main'
    
    # Creating simulated commits
    commit_dates = [
        datetime(2023, 1, 1),
        datetime(2023, 2, 1),
        datetime(2023, 3, 1),
        datetime(2023, 4, 1),
        datetime(2023, 5, 1)
    ]
    commits = [Mock(committed_date=date.timestamp()) for date in commit_dates]
    mock_repo.iter_commits.return_value = commits

    # Base case: retrieve all commits
    all_commits = backup_script.get_commits(mock_repo, branch)
    assert all_commits == commits

    # Case with only start_date specified
    start_date = '01-03-2023'
    expected_commits = commits[2:]
    start_date_commits = backup_script.get_commits(mock_repo, branch, start_date=start_date)
    assert start_date_commits == expected_commits

    # Case with only end_date specified
    end_date = '01-03-2023'
    expected_commits = commits[:3]
    end_date_commits = backup_script.get_commits(mock_repo, branch, end_date=end_date)
    assert end_date_commits == expected_commits

    # Case with both start_date and end_date specified
    start_date = '01-02-2023'
    end_date = '01-04-2023'
    expected_commits = commits[1:4]
    date_range_commits = backup_script.get_commits(mock_repo, branch, start_date=start_date, end_date=end_date)
    assert date_range_commits == expected_commits

@pytest.mark.asyncio
async def test_read_file_content():
    mock_repo = Mock()
    mock_repo.git.show.return_value = "file content"
    mock_commit = Mock()
    mock_commit.hexsha = "abc123"
    content = await backup_script.read_file_content(mock_repo, mock_commit, "test.txt")
    assert content == "file content"

@pytest.mark.asyncio
async def test_write_file_content(tmp_path):
    file_path = tmp_path / "test.txt"
    content = "test content"
    await backup_script.write_file_content(str(file_path), content)
    assert file_path.read_text() == content

@pytest.mark.asyncio
async def test_process_file(tmp_path):
    mock_repo = Mock()
    mock_repo.git.show.return_value = "file content"
    mock_commit = Mock()
    mock_commit.hexsha = "abc123"
    file = "test.txt"
    commit_backup_dir = tmp_path / "backup"
    failed_files = []
    
    await backup_script.process_file(mock_repo, mock_commit, file, str(commit_backup_dir), failed_files)
    
    assert (commit_backup_dir / file).read_text() == "file content"
    assert len(failed_files) == 0

    mock_repo.git.show.side_effect = backup_script.BackupError
    with pytest.raises(backup_script.BackupError):
        await backup_script.process_file(mock_repo, mock_commit, file, str(commit_backup_dir), failed_files)
    assert len(failed_files) == 1, "The 'failed_files' list should contain one entry"
    assert failed_files[0] == ("abc123", "test.txt"), "The failure should be related to test.txt"

    mock_repo.git.show.side_effect = git.GitCommandError("show", "file does not exist in commit hexsha")
    await backup_script.process_file(mock_repo, mock_commit, file, str(commit_backup_dir), failed_files)
    assert len(failed_files) == 1, "The 'failed_files' list should contain one entry"
    assert failed_files[0] == ("abc123", "test.txt"), "The failure should be related to test.txt"
