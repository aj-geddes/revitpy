"""Virtual environment management for RevitPy projects."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import virtualenv


class VirtualEnvironmentError(Exception):
    """Exception raised for virtual environment operations."""
    pass


class RevitPyEnvironment:
    """Represents a RevitPy virtual environment."""
    
    def __init__(self, path: Path, name: str, python_version: str, revit_version: str):
        self.path = path
        self.name = name
        self.python_version = python_version
        self.revit_version = revit_version
        self._metadata_file = path / ".revitpy" / "environment.json"
        self._lock_file = path / ".revitpy" / "lock.json"
    
    @property
    def python_executable(self) -> Path:
        """Get the Python executable for this environment."""
        if os.name == 'nt':  # Windows
            return self.path / "Scripts" / "python.exe"
        else:  # Unix-like
            return self.path / "bin" / "python"
    
    @property
    def pip_executable(self) -> Path:
        """Get the pip executable for this environment."""
        if os.name == 'nt':  # Windows
            return self.path / "Scripts" / "pip.exe"
        else:  # Unix-like
            return self.path / "bin" / "pip"
    
    @property
    def site_packages(self) -> Path:
        """Get the site-packages directory."""
        if os.name == 'nt':  # Windows
            return self.path / "Lib" / "site-packages"
        else:  # Unix-like
            version_info = self.python_version.split('.')[:2]
            return self.path / "lib" / f"python{'.'.join(version_info)}" / "site-packages"
    
    @property
    def is_active(self) -> bool:
        """Check if this environment is currently active."""
        current_prefix = getattr(sys, 'prefix', '')
        return str(self.path) == current_prefix
    
    def exists(self) -> bool:
        """Check if the environment directory exists."""
        return self.path.exists() and self.python_executable.exists()
    
    def save_metadata(self):
        """Save environment metadata to disk."""
        metadata = {
            "name": self.name,
            "python_version": self.python_version,
            "revit_version": self.revit_version,
            "created_at": "2024-01-01T00:00:00Z",  # Simplified timestamp
        }
        
        self._metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def load_metadata(self) -> Dict:
        """Load environment metadata from disk."""
        if not self._metadata_file.exists():
            return {}
        
        with open(self._metadata_file, 'r') as f:
            return json.load(f)
    
    def save_lock_file(self, lock_data: Dict):
        """Save dependency lock file."""
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._lock_file, 'w') as f:
            json.dump(lock_data, f, indent=2)
    
    def load_lock_file(self) -> Optional[Dict]:
        """Load dependency lock file."""
        if not self._lock_file.exists():
            return None
        
        with open(self._lock_file, 'r') as f:
            return json.load(f)
    
    def run_command(self, command: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Run a command in this environment."""
        # Security: Validate command to prevent injection attacks
        if not command or not isinstance(command, list):
            raise ValueError("Command must be a non-empty list")
        
        # Security: Ensure shell=False (default) and never allow shell execution
        if kwargs.get('shell', False):
            raise ValueError("Shell execution is not allowed for security reasons")
        
        env = os.environ.copy()
        env["VIRTUAL_ENV"] = str(self.path)
        env["PATH"] = f"{self.path / 'Scripts' if os.name == 'nt' else self.path / 'bin'}{os.pathsep}{env['PATH']}"
        
        # Security: Set safe defaults
        kwargs.setdefault('shell', False)
        kwargs.setdefault('timeout', 300)  # 5 minute timeout
        
        return subprocess.run(command, env=env, **kwargs)
    
    def install_package(self, package_spec: str, upgrade: bool = False) -> bool:
        """Install a package in this environment."""
        cmd = [str(self.pip_executable), "install"]
        if upgrade:
            cmd.append("--upgrade")
        cmd.append(package_spec)
        
        result = self.run_command(cmd, capture_output=True, text=True)
        return result.returncode == 0
    
    def uninstall_package(self, package_name: str) -> bool:
        """Uninstall a package from this environment."""
        cmd = [str(self.pip_executable), "uninstall", "-y", package_name]
        result = self.run_command(cmd, capture_output=True, text=True)
        return result.returncode == 0
    
    def list_packages(self) -> List[Dict[str, str]]:
        """List installed packages in this environment."""
        cmd = [str(self.pip_executable), "list", "--format=json"]
        result = self.run_command(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return []
        
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return []


class VirtualEnvironmentManager:
    """Manages RevitPy virtual environments."""
    
    def __init__(self, base_directory: Optional[Path] = None):
        if base_directory is None:
            # Default to user's RevitPy environments directory
            home = Path.home()
            base_directory = home / ".revitpy" / "environments"
        
        self.base_directory = Path(base_directory)
        self.base_directory.mkdir(parents=True, exist_ok=True)
    
    def list_environments(self) -> List[RevitPyEnvironment]:
        """List all available environments."""
        environments = []
        
        for env_dir in self.base_directory.iterdir():
            if env_dir.is_dir():
                metadata_file = env_dir / ".revitpy" / "environment.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        
                        env = RevitPyEnvironment(
                            path=env_dir,
                            name=metadata.get("name", env_dir.name),
                            python_version=metadata.get("python_version", "3.11"),
                            revit_version=metadata.get("revit_version", "2025")
                        )
                        environments.append(env)
                    except Exception:
                        continue
        
        return environments
    
    def get_environment(self, name: str) -> Optional[RevitPyEnvironment]:
        """Get an environment by name."""
        environments = self.list_environments()
        for env in environments:
            if env.name == name:
                return env
        return None
    
    def create_environment(
        self,
        name: str,
        python_version: str = "3.11",
        revit_version: str = "2025",
        packages: Optional[List[str]] = None
    ) -> RevitPyEnvironment:
        """Create a new virtual environment.
        
        Args:
            name: Name of the environment
            python_version: Python version to use
            revit_version: Target Revit version
            packages: Initial packages to install
        
        Returns:
            Created RevitPyEnvironment instance
        """
        env_path = self.base_directory / name
        
        if env_path.exists():
            raise VirtualEnvironmentError(f"Environment '{name}' already exists")
        
        # Find Python interpreter
        python_executable = self._find_python_executable(python_version)
        if not python_executable:
            raise VirtualEnvironmentError(f"Python {python_version} not found")
        
        # Create virtual environment
        try:
            virtualenv.create_environment(
                str(env_path),
                interpreter=python_executable,
                symlinks=False,  # Use copies for better isolation on Windows
            )
        except Exception as e:
            raise VirtualEnvironmentError(f"Failed to create environment: {e}")
        
        # Create RevitPy environment instance
        env = RevitPyEnvironment(
            path=env_path,
            name=name,
            python_version=python_version,
            revit_version=revit_version
        )
        
        # Save metadata
        env.save_metadata()
        
        # Install base packages
        base_packages = [
            "pip",
            "setuptools",
            "wheel",
            "packaging",  # For version parsing
        ]
        
        for package in base_packages:
            if not env.install_package(package, upgrade=True):
                raise VirtualEnvironmentError(f"Failed to install base package: {package}")
        
        # Install additional packages if specified
        if packages:
            for package in packages:
                if not env.install_package(package):
                    raise VirtualEnvironmentError(f"Failed to install package: {package}")
        
        return env
    
    def delete_environment(self, name: str) -> bool:
        """Delete a virtual environment.
        
        Args:
            name: Name of the environment to delete
        
        Returns:
            True if successful, False otherwise
        """
        env = self.get_environment(name)
        if not env:
            return False
        
        try:
            shutil.rmtree(env.path)
            return True
        except Exception:
            return False
    
    def clone_environment(self, source_name: str, target_name: str) -> RevitPyEnvironment:
        """Clone an existing environment.
        
        Args:
            source_name: Name of the source environment
            target_name: Name of the new environment
        
        Returns:
            New RevitPyEnvironment instance
        """
        source_env = self.get_environment(source_name)
        if not source_env:
            raise VirtualEnvironmentError(f"Source environment '{source_name}' not found")
        
        if self.get_environment(target_name):
            raise VirtualEnvironmentError(f"Target environment '{target_name}' already exists")
        
        # Create new environment
        target_env = self.create_environment(
            name=target_name,
            python_version=source_env.python_version,
            revit_version=source_env.revit_version
        )
        
        # Copy installed packages
        source_packages = source_env.list_packages()
        for package in source_packages:
            if package["name"] not in ["pip", "setuptools", "wheel"]:
                package_spec = f"{package['name']}=={package['version']}"
                target_env.install_package(package_spec)
        
        # Copy lock file if it exists
        source_lock = source_env.load_lock_file()
        if source_lock:
            target_env.save_lock_file(source_lock)
        
        return target_env
    
    def _find_python_executable(self, version: str) -> Optional[str]:
        """Find a Python executable for the specified version."""
        # Common Python executable names
        version_parts = version.split('.')
        major, minor = version_parts[0], version_parts[1] if len(version_parts) > 1 else ""
        
        candidates = [
            f"python{major}.{minor}",
            f"python{major}",
            "python",
            f"python{major}.{minor}.exe",
            f"python{major}.exe",
            "python.exe",
        ]
        
        # Also check common installation paths on Windows
        if os.name == 'nt':
            import winreg
            try:
                # Check Python Launcher
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                   f"SOFTWARE\\Python\\PythonCore\\{major}.{minor}\\InstallPath")
                python_path = winreg.QueryValue(key, "")
                candidates.append(os.path.join(python_path, "python.exe"))
                winreg.CloseKey(key)
            except (OSError, FileNotFoundError):
                pass
        
        for candidate in candidates:
            try:
                # Check if executable exists and is correct version
                result = subprocess.run(
                    [candidate, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    output_version = result.stdout.strip().split()[-1]
                    if output_version.startswith(version) or output_version.startswith(f"{major}.{minor}"):
                        # Return full path
                        full_path = shutil.which(candidate)
                        if full_path:
                            return full_path
                        return candidate
                        
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        return None
    
    def get_current_environment(self) -> Optional[RevitPyEnvironment]:
        """Get the currently active environment."""
        if not hasattr(sys, 'prefix'):
            return None
        
        current_prefix = Path(sys.prefix)
        
        # Check if we're in a RevitPy environment
        metadata_file = current_prefix / ".revitpy" / "environment.json"
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            return RevitPyEnvironment(
                path=current_prefix,
                name=metadata.get("name", current_prefix.name),
                python_version=metadata.get("python_version", "3.11"),
                revit_version=metadata.get("revit_version", "2025")
            )
        except Exception:
            return None