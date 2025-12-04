#!/usr/bin/env python3


import sys
import os
import re
import subprocess
import argparse
from pathlib import Path


def parse_imports(python_file):
    imports = set()

    try:
        with open(python_file, 'r') as f:
            content = f.read()
        import_pattern = r'^\s*(?:import|from)\s+([a-zA-Z0-9_]+)'
        matches = re.finditer(import_pattern, content, re.MULTILINE)
        for match in matches:
            package = match.group(1)
            imports.add(package)
        return imports
    except Exception as e:
        print(f"Warning: Could not parse imports from {python_file}: {e}")
        return set()


def map_to_pip_packages(imports):
    # mappings where import name differs from pip package name, most common cases
    package_mapping = {
        'cv2': 'opencv-python',
        'PIL': 'Pillow',
        'sklearn': 'scikit-learn',
        'yaml': 'pyyaml',
        'dotenv': 'python-dotenv',
        'bs4': 'beautifulsoup4',
        'dateutil': 'python-dateutil',
    }
    stdlib = {
        'os', 'sys', 're', 'json', 'time', 'datetime', 'math', 'random',
        'collections', 'itertools', 'functools', 'pathlib', 'subprocess',
        'threading', 'multiprocessing', 'logging', 'argparse', 'io',
        'shutil', 'tempfile', 'glob', 'pickle', 'csv', 'urllib', 'http',
        'socket', 'email', 'html', 'xml', 'sqlite3', 'hashlib', 'hmac',
        'base64', 'binascii', 'struct', 'array', 'enum', 'typing', 'copy',
        'weakref', 'contextlib', 'abc', 'asyncio', 'concurrent', 'queue',
        'secrets', 'string', 'textwrap', 'unicodedata', 'codecs', 'encodings',
        'decimal', 'fractions', 'statistics', 'heapq', 'bisect', 'pprint',
        'reprlib', 'dataclasses', 'graphlib', 'warnings', 'traceback', 'inspect',
        'importlib', 'pkgutil', 'modulefinder', 'runpy', 'site', 'builtins'
    }

    pip_packages = []
    for imp in imports:
        if imp in stdlib:
            continue

        package = package_mapping.get(imp, imp)
        pip_packages.append(package)

    return pip_packages


def create_dockerfile(python_file, pip_packages, work_dir):
    script_name = os.path.basename(python_file)
    dockerfile_content = f"""# auto-generated dockerfile for {script_name}
FROM python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copy Python script
COPY {script_name} /app/

# Install Python dependencies

"""

    if pip_packages:
        packages_str = ' '.join(pip_packages)
        dockerfile_content += f"RUN pip install --no-cache-dir {packages_str}\n"
    else:
        dockerfile_content += "# No external dependencies detected\n"

    dockerfile_content += f"""
# Run the script
CMD ["python3", "{script_name}"]
"""

    dockerfile_path = os.path.join(work_dir, 'Dockerfile')
    with open(dockerfile_path, 'w') as f:
        f.write(dockerfile_content)

    print(f"Created Dockerfile at: {dockerfile_path}")
    return dockerfile_path


def create_requirements_txt(pip_packages, work_dir):
    if not pip_packages:
        return None
    requirements_path = os.path.join(work_dir, 'requirements.txt')
    with open(requirements_path, 'w') as f:
        for package in sorted(pip_packages):
            f.write(f"{package}\n")

    print(f"Created requirements.txt at: {requirements_path}")
    return requirements_path


def build_docker_image(work_dir, image_name):
    print(f"\n [ + ] Building Docker image: {image_name}")
    print("=" * 60)
    try:
        result = subprocess.run(
            ['docker', 'build', '-t', image_name, '.'],
            cwd=work_dir,
            check=True,
            capture_output=False
        )
        print("=" * 60)
        print(f"[ + ] Successfully built image: {image_name}\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ - ] Failed to build Docker image: {e}")
        return False
    except FileNotFoundError:
        print("[ - ] Docker is not installed or not in PATH")
        return False


def run_docker_container(image_name, container_name):
    print(f" [ + ] Running Docker container: {container_name}")
    print("=" * 60)
    try:
        subprocess.run(
            ['docker', 'run', '-d', '--name', container_name, '--rm', image_name],
            check=True
        )
        print("=" * 60)
        print(f"[ + ] Container {container_name} finished execution\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ + ] Container execution failed: {e}")
        return False
    except KeyboardInterrupt:
        print("\n[ + ] Container execution interrupted")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Containerize and run a Python script in Docker'
    )
    parser.add_argument(
        'python_file',
        help='Path to the Python file to containerize'
    )
    parser.add_argument(
        '--no-run',
        action='store_true',
        help='Build the image but do not run it'
    )
    parser.add_argument(
        '--image-name',
        help='Custom Docker image name (default: py-<filename>)'
    )
    parser.add_argument(
        '--container-name',
        help='Custom container name (default: <image-name>-container)'
    )
    args = parser.parse_args()
    python_file = args.python_file
    if not os.path.isfile(python_file):
        print(f"[ - ] Error: File not found: {python_file}")
        sys.exit(1)

    if not python_file.endswith('.py'):
        print(f"[ - ] Error: File must be a Python file (.py): {python_file}")
        sys.exit(1)

    python_file = os.path.abspath(python_file)
    work_dir = os.path.dirname(python_file)
    script_name = os.path.basename(python_file)
    base_name = os.path.splitext(script_name)[0]
    image_name = args.image_name or f"py-{base_name.lower()}"
    container_name = args.container_name or f"{image_name}-container"

    print("\n" + "=" * 60)
    print("Python to Docker Containerizer")
    print("=" * 60)
    print(f"Python file:  {python_file}")
    print(f"Work dir:     {work_dir}")
    print(f"Image name:   {image_name}")
    print(f"Container:    {container_name}")
    print("=" * 60 + "\n")

    print(" [ + ] Analyzing dependencies...")
    imports = parse_imports(python_file)
    pip_packages = map_to_pip_packages(imports)

    if pip_packages:
        print(f"Detected {len(pip_packages)} external dependencies:")
        for pkg in sorted(pip_packages):
            print(f"  - {pkg}")
    else:
        print("No external dependencies detected (stdlib only)")
    print()
    dockerfile_path = create_dockerfile(python_file, pip_packages, work_dir)
    if pip_packages:
        create_requirements_txt(pip_packages, work_dir)
    print()
    if not build_docker_image(work_dir, image_name):
        sys.exit(1)
    if not args.no_run:
        run_docker_container(image_name, container_name)
    else:
        print(f" Skipping container run (--no-run flag set)")
        print(f" To run manually: docker run --rm {image_name}")

    print("\nDone!\n")


if __name__ == '__main__':
    main()