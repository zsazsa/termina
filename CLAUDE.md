# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Termina Launcher is a GTK3-based SSH connection manager and terminal profile launcher for GNOME/Linux. It's a single-file Python application that provides a GUI for managing SSH hosts and launching terminals with pre-configured git identities.

## Development Commands

### Running the Application
```bash
# Direct execution
./sshconnect-gui.py

# Using Python explicitly
python3 sshconnect-gui.py
```

### Installation Commands
```bash
# Make files executable
chmod +x sshconnect-gui.py

# Create desktop entry for GNOME integration (see README for full command)
# Desktop entry is not included in repo to avoid committing local paths
update-desktop-database ~/.local/share/applications/
```

### Testing
No formal test suite exists. Manual testing involves:
1. Running the application
2. Adding/editing/deleting hosts and terminal profiles
3. Testing SSH connections and terminal profile launches
4. Verifying configuration saves to `~/.sshconnect`

## Architecture

### Single-File Application Structure
The entire application is in `sshconnect-gui.py` with these main classes:

1. **SSHHost**: Data model for SSH connections
   - Handles serialization to/from JSON
   - Generates SSH command arguments (list-based for security)
   - Creates display text for UI
   - Stores links associated with each host

2. **TerminalProfile**: Data model for terminal profiles
   - Stores git identity (username, email, SSH key path)
   - Stores optional working directory
   - Generates environment variables for git configuration

3. **HostDialog**: GTK dialog for adding/editing SSH hosts
   - Tabbed interface (Connection and Links tabs)
   - Form validation
   - File chooser for SSH certificates

4. **TerminalProfileDialog**: GTK dialog for adding/editing terminal profiles
   - Form fields for git identity settings
   - File choosers for SSH key and working directory

5. **SSHConnectWindow**: Main application window
   - Tabbed interface (SSH Hosts and Terminal Profiles)
   - Manages host/profile lists and filtering
   - Handles all user interactions
   - Persists data to `~/.sshconnect`
   - Launches SSH connections and terminal profiles via gnome-terminal

### Configuration Format
```json
{
  "version": 2,
  "ssh_hosts": [
    {"name": "...", "ip": "...", "username": "...", "port": 22, "certificate": "...", "links": []}
  ],
  "terminal_profiles": [
    {"name": "...", "git_username": "...", "git_email": "...", "ssh_key_path": "...", "working_dir": "..."}
  ]
}
```

### Key Design Patterns

**Security:**
- Uses subprocess with list arguments (no shell=True)
- SSH key paths properly quoted with shlex.quote()
- Config file permissions restricted to 600
- Markup text escaped to prevent injection

**Event-Driven GTK Architecture:**
- Tab key switches between SSH Hosts and Terminal Profiles tabs
- Search changes trigger real-time filtering
- Keyboard events handled globally via `on_key_press`
- Row activation (double-click/Enter) triggers connections/launches

**Auto-Connect/Launch Logic:**
When search returns single result, Enter key connects/launches immediately.

**Terminal Profile Environment:**
Sets these environment variables when launching:
- GIT_AUTHOR_NAME, GIT_COMMITTER_NAME
- GIT_AUTHOR_EMAIL, GIT_COMMITTER_EMAIL
- GIT_SSH_COMMAND (if SSH key specified)

## Important Files

- `sshconnect-gui.py`: Main application (~1270 lines)
- `~/.sshconnect`: User's configuration (JSON format, permissions 600)
- `~/.local/share/applications/termina-launcher.desktop`: Desktop entry (user-created, see README)

## Dependencies

Required system packages (Ubuntu/Debian):
- python3-gi
- python3-gi-cairo
- gir1.2-gtk-3.0
- gnome-terminal

## Notes

- The application closes automatically after launching a connection/profile
- No password storage - uses SSH keys/certificates only
- Config file permissions are automatically set to 600 (owner read/write only)
- Wayland users may need to log out/in for desktop entry to appear
- TreeView's built-in search is disabled to avoid conflicts with custom search
