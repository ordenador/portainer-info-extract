# Portainer-Info-Extract

## Overview
Portainer-Info-Extract is a Python-based tool designed for gathering and analyzing Docker Swarm information through the Portainer API. It provides a streamlined way to extract key details about services, secrets, nodes, and container statistics.

## Features
- Automated retrieval of services, secrets, nodes, and container data in Docker Swarm.
- Extraction and processing of environment variables, configurations, and mounts.
- Excel report generation for detailed analysis.
- Comprehensive error logging for API requests.

## Setup and Installation
1. Clone the repository.
2. Create and activate a virtual environment:
   ```bash
   make venv
   ```
3. Install dependencies:
   ```bash
   make pip-compile
   ```

## Running the Script
- Execute the script with:
  ```bash
  make run
  ```

## Development Tools
- Auto-formatting: `make autopep8`
- Code style check: `make pycodestyle`
- Lint check: `make check`

## Cleaning Up
- To clean the virtual environment and temporary files:
  ```bash
  make clean
  ```

## Help
- For a list of available commands:
  ```bash
  make help
  ```

