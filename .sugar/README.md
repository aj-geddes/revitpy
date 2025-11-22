# Sugar Autonomous Development System

This directory contains the configuration and data for Sugar, an autonomous development system that helps manage and execute development tasks.

## Directory Structure

```
.sugar/
├── config.yaml           # Main Sugar configuration
├── tasks.json           # Task database
├── sugar.log            # Execution logs
├── notifications.log    # Notification history
├── logs/                # Error logs and monitoring
├── cache/               # Analysis and data cache
└── backups/             # Backup files before changes
```

## Configuration

The main configuration is in `config.yaml`. Key settings:

- **execution**: Controls autonomous task execution
- **agents**: Specialized agent configuration
- **discovery**: Automatic work discovery from logs, code, and GitHub
- **quality**: Code quality and testing standards
- **safety**: Protected files and approval requirements

## Task Management

Tasks are stored in `tasks.json` with the following structure:

```json
{
  "id": "unique-task-id",
  "title": "Task description",
  "type": "feature|bug_fix|test|refactor|documentation",
  "priority": 1-5,
  "status": "pending|active|completed|failed",
  "context": "Detailed description",
  "technical_requirements": [],
  "agent_assignments": {},
  "success_criteria": [],
  "created_at": "ISO timestamp",
  "updated_at": "ISO timestamp"
}
```

## Usage

### View Status
```bash
/sugar:sugar-status
```

### Create Task
```bash
/sugar:sugar-task
```

### Analyze Codebase
```bash
/sugar:sugar-analyze
```

### Review Tasks
```bash
/sugar:sugar-review
```

### Run Autonomous Mode
```bash
/sugar:sugar-run
```

## Safety Features

Sugar includes several safety features:

- **Protected files**: Git configs, build files, and critical configs are protected
- **Approval required**: Certain operations require explicit approval
- **Backups**: Files are backed up before modification
- **Rollback**: Failed changes can be reverted

## Logs

- `sugar.log`: Main execution log
- `notifications.log`: Task completion and discovery notifications
- `logs/`: Error logs from your application (monitored for issues)

## Getting Started

1. Review the configuration in `config.yaml`
2. Run `/sugar:sugar-analyze` to discover initial tasks
3. Review tasks with `/sugar:sugar-review`
4. Start autonomous mode with `/sugar:sugar-run` (optional)

## Customization

Edit `config.yaml` to:
- Enable/disable agents
- Configure discovery sources
- Adjust execution intervals
- Set quality standards
- Configure integrations

For more information, see the Sugar documentation.
