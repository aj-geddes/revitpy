"""Git repository management utilities."""

import subprocess
from pathlib import Path
from typing import List, Optional

from git import Repo, InvalidGitRepositoryError
from git.exc import GitCommandError

from ..core.exceptions import CommandError
from ..core.logging import get_logger

logger = get_logger(__name__)


class GitManager:
    """Git repository management utilities."""
    
    def __init__(self, repo_path: Path) -> None:
        """Initialize Git manager.
        
        Args:
            repo_path: Path to repository directory
        """
        self.repo_path = repo_path
        self._repo: Optional[Repo] = None
    
    @property
    def repo(self) -> Repo:
        """Get Git repository instance.
        
        Returns:
            Git repository instance
            
        Raises:
            CommandError: If not a valid Git repository
        """
        if self._repo is None:
            try:
                self._repo = Repo(self.repo_path)
            except InvalidGitRepositoryError as e:
                raise CommandError(
                    "git",
                    f"Not a git repository: {self.repo_path}",
                    suggestion="Run 'git init' to initialize a repository"
                ) from e
        return self._repo
    
    def init(self) -> None:
        """Initialize a new Git repository.
        
        Raises:
            CommandError: If initialization fails
        """
        try:
            self._repo = Repo.init(self.repo_path)
            logger.info(f"Initialized git repository at {self.repo_path}")
        except Exception as e:
            raise CommandError("git init", str(e)) from e
    
    def is_git_repository(self) -> bool:
        """Check if directory is a Git repository.
        
        Returns:
            True if directory is a Git repository
        """
        try:
            Repo(self.repo_path)
            return True
        except InvalidGitRepositoryError:
            return False
    
    def add_all(self) -> None:
        """Add all files to Git staging area.
        
        Raises:
            CommandError: If add operation fails
        """
        try:
            self.repo.git.add("--all")
            logger.debug("Added all files to git staging area")
        except GitCommandError as e:
            raise CommandError("git add", str(e)) from e
    
    def add(self, files: List[str]) -> None:
        """Add specific files to Git staging area.
        
        Args:
            files: List of file paths to add
            
        Raises:
            CommandError: If add operation fails
        """
        try:
            self.repo.index.add(files)
            logger.debug(f"Added {len(files)} files to git staging area")
        except Exception as e:
            raise CommandError("git add", str(e)) from e
    
    def commit(self, message: str, author: Optional[str] = None) -> None:
        """Create a Git commit.
        
        Args:
            message: Commit message
            author: Optional commit author
            
        Raises:
            CommandError: If commit fails
        """
        try:
            kwargs = {}
            if author:
                kwargs["author"] = author
            
            self.repo.index.commit(message, **kwargs)
            logger.info(f"Created commit: {message}")
        except Exception as e:
            raise CommandError("git commit", str(e)) from e
    
    def get_status(self) -> dict:
        """Get Git repository status.
        
        Returns:
            Dictionary with repository status information
        """
        try:
            repo = self.repo
            return {
                "branch": repo.active_branch.name,
                "is_dirty": repo.is_dirty(),
                "untracked_files": repo.untracked_files,
                "modified_files": [item.a_path for item in repo.index.diff(None)],
                "staged_files": [item.a_path for item in repo.index.diff("HEAD")],
            }
        except Exception as e:
            logger.warning(f"Failed to get git status: {e}")
            return {}
    
    def get_remote_url(self, remote: str = "origin") -> Optional[str]:
        """Get remote repository URL.
        
        Args:
            remote: Remote name (default: origin)
            
        Returns:
            Remote URL or None if not found
        """
        try:
            return self.repo.remote(remote).url
        except Exception:
            return None
    
    def has_commits(self) -> bool:
        """Check if repository has any commits.
        
        Returns:
            True if repository has commits
        """
        try:
            list(self.repo.iter_commits(max_count=1))
            return True
        except Exception:
            return False
    
    def get_current_branch(self) -> Optional[str]:
        """Get current branch name.
        
        Returns:
            Current branch name or None if detached HEAD
        """
        try:
            return self.repo.active_branch.name
        except Exception:
            return None
    
    def create_branch(self, branch_name: str) -> None:
        """Create a new branch.
        
        Args:
            branch_name: Name of the new branch
            
        Raises:
            CommandError: If branch creation fails
        """
        try:
            self.repo.create_head(branch_name)
            logger.info(f"Created branch: {branch_name}")
        except Exception as e:
            raise CommandError("git branch", str(e)) from e
    
    def checkout_branch(self, branch_name: str) -> None:
        """Checkout a branch.
        
        Args:
            branch_name: Name of branch to checkout
            
        Raises:
            CommandError: If checkout fails
        """
        try:
            self.repo.git.checkout(branch_name)
            logger.info(f"Checked out branch: {branch_name}")
        except Exception as e:
            raise CommandError("git checkout", str(e)) from e
    
    def tag(self, tag_name: str, message: Optional[str] = None) -> None:
        """Create a Git tag.
        
        Args:
            tag_name: Name of the tag
            message: Optional tag message
            
        Raises:
            CommandError: If tagging fails
        """
        try:
            if message:
                self.repo.create_tag(tag_name, message=message)
            else:
                self.repo.create_tag(tag_name)
            logger.info(f"Created tag: {tag_name}")
        except Exception as e:
            raise CommandError("git tag", str(e)) from e


def clone_repository(url: str, destination: Path, branch: Optional[str] = None) -> GitManager:
    """Clone a Git repository.
    
    Args:
        url: Repository URL
        destination: Destination directory
        branch: Optional branch to clone
        
    Returns:
        GitManager instance for cloned repository
        
    Raises:
        CommandError: If cloning fails
    """
    try:
        kwargs = {}
        if branch:
            kwargs["branch"] = branch
        
        repo = Repo.clone_from(url, destination, **kwargs)
        logger.info(f"Cloned repository from {url} to {destination}")
        return GitManager(destination)
        
    except Exception as e:
        raise CommandError("git clone", str(e)) from e


def is_git_url(url: str) -> bool:
    """Check if URL is a Git repository URL.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL appears to be a Git repository
    """
    git_indicators = [
        ".git",
        "github.com",
        "gitlab.com",
        "bitbucket.org",
        "git://",
        "ssh://git",
    ]
    
    return any(indicator in url.lower() for indicator in git_indicators)