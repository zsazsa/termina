# Termina Launcher

A fast and intuitive SSH connection manager and terminal profile launcher for GNOME/Linux.

## Features

- **Quick Connect**: Type to search and press Enter to connect
- **Host Management**: Add, edit, duplicate, delete, and reorder SSH hosts
- **Terminal Profiles**: Launch local terminals with pre-configured git identities
- **SSH Certificate Support**: Store and use SSH private keys for authentication
- **Smart Search**: Real-time filtering by host name or IP address
- **Auto-connect**: Automatically connects when search returns single result
- **Tabbed Interface**: Switch between SSH Hosts and Terminal Profiles with Tab
- **Persistent Storage**: Configuration saved in `~/.sshconnect` JSON file
- **GNOME Integration**: Desktop entry for easy access from applications menu

## Quick Install

```bash
# Clone the repository
git clone https://github.com/zsazsa/termina.git ~/termina
cd ~/termina

# Make executable
chmod +x sshconnect-gui.py

# Create desktop entry for GNOME integration
cat > ~/.local/share/applications/termina-launcher.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Termina Launcher
Comment=SSH connection manager and terminal profile launcher
Exec=$(pwd)/sshconnect-gui.py
Icon=utilities-terminal
Terminal=false
Categories=Network;RemoteAccess;
Keywords=ssh;remote;connection;terminal;git;profile;
EOF

# Update desktop database
update-desktop-database ~/.local/share/applications/
```

The app should appear in your applications menu within a few seconds. If not, log out and back in.

**Note for Wayland users**: The traditional Alt+F2 → 'r' restart doesn't work on Wayland. The `update-desktop-database` command above should be sufficient, but logging out/in always works.

## Requirements

- Python 3.6+
- GTK 3.0+
- PyGObject
- gnome-terminal

Ubuntu/Debian users can install dependencies with:
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0
```

## Usage

Launch from GNOME applications menu or run:
```bash
./sshconnect-gui.py
```

## Keyboard Shortcuts

- **Type to search**: Filter hosts/profiles in real-time
- **Tab**: Switch between SSH Hosts and Terminal Profiles tabs
- **Enter**: Connect to selected host or launch selected profile
- **Double-click**: Connect/launch selected item
- **Shift + ↑/↓**: Reorder items in the list
- **Escape**: Close application

## Configuration

Configuration is stored in `~/.sshconnect`:

```json
{
  "version": 2,
  "ssh_hosts": [
    {
      "name": "My Server",
      "ip": "192.168.1.100",
      "username": "user",
      "port": 22,
      "certificate": "/home/user/.ssh/id_rsa",
      "links": []
    }
  ],
  "terminal_profiles": [
    {
      "name": "Work GitHub",
      "git_username": "myusername",
      "git_email": "me@work.com",
      "ssh_key_path": "/home/user/.ssh/id_work",
      "working_dir": "/home/user/projects"
    }
  ]
}
```

### SSH Host Fields

- **name**: Display name for the host (required)
- **ip**: IP address or hostname (required)
- **username**: SSH username (optional)
- **port**: SSH port (optional, defaults to 22)
- **certificate**: Path to SSH private key file (optional)
- **links**: List of name/URL pairs for quick access (optional)

### Terminal Profile Fields

- **name**: Display name for the profile (required)
- **git_username**: Git author/committer name (required)
- **git_email**: Git author/committer email (required)
- **ssh_key_path**: Path to SSH key for git operations (optional)
- **working_dir**: Starting directory for terminal (optional)

## Terminal Profiles

Terminal profiles solve a common problem: managing multiple GitHub accounts on the same machine.

### Why Multiple Git Identities?

GitHub identifies you by two things:
1. **Commits**: The name and email in your git commits
2. **Authentication**: The SSH key used to push/pull

If you have both personal and work GitHub accounts, you need different credentials for each. Without terminal profiles, you'd manually reconfigure git each time you switch contexts.

### How It Works

When you launch a terminal profile, Termina sets environment variables that override your global git config:

```bash
GIT_AUTHOR_NAME="Your Name"
GIT_COMMITTER_NAME="Your Name"
GIT_AUTHOR_EMAIL="<your-email>"
GIT_COMMITTER_EMAIL="<your-email>"
GIT_SSH_COMMAND="ssh -i /path/to/key -o IdentitiesOnly=yes"
```

The `GIT_SSH_COMMAND` ensures git uses the correct SSH key when pushing to GitHub, authenticating you to the right account.

### Setup Workflow

1. **Generate separate SSH keys** for each GitHub account:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/id_personal -C "personal"
   ssh-keygen -t ed25519 -f ~/.ssh/id_work -C "work"
   ```

2. **Add each public key** to the corresponding GitHub account (Settings → SSH Keys)

3. **Create terminal profiles** in Termina for each identity, specifying the matching SSH key path

4. **Launch the appropriate profile** when working on projects for that account

All commits made in that terminal session will use the correct identity, and pushes will authenticate to the correct GitHub account.

## Display Format

**SSH Hosts**: `name - username@host:port`
- `My Server - user@192.168.1.100`
- `Web Server - admin@example.com:2222`

**Terminal Profiles**: `name - username <email>`
- `Work GitHub - myusername <me@work.com>`

## Uninstall

```bash
# Remove from GNOME applications
rm ~/.local/share/applications/termina-launcher.desktop
update-desktop-database ~/.local/share/applications/

# Remove the application
rm -rf ~/termina

# Remove configuration (optional)
rm ~/.sshconnect
```

## License

MIT License - see LICENSE file for details.

## Build Your Own with AI

Want to create Termina Launcher from scratch using AI? Copy this entire prompt to your AI assistant:

---

Create a GTK3-based SSH connection manager application for GNOME/Linux with the following specifications:

**Core Requirements:**
- Single Python file named `sshconnect-gui.py` using PyGObject (gi)
- Store configurations in `~/.sshconnect` as JSON
- Create a desktop entry file for GNOME integration
- Use gnome-terminal to open SSH connections and terminal profiles

**Main Window UI (600x400):**
1. Notebook with two tabs: "SSH Hosts" and "Terminal Profiles"
2. Each tab contains:
   - Search entry at top with placeholder text
   - Scrollable list showing items
   - Bottom button bar with: Add, Edit, Duplicate, Delete (left), Connect/Launch (right, suggested-action style)

**SSH Hosts Features:**
1. **Real-time search filtering** - Filter hosts as user types
2. **Auto-connect** - If search returns only one result, pressing Enter connects immediately
3. **Host management** - Add/Edit/Duplicate/Delete hosts with dialog containing:
   - Name (required), IP/Hostname (required), Username, Port (default 22), Certificate path
4. **SSH command generation** with format: `ssh [-i certificate] [user@]host [-p port]`
5. **Close app after launching SSH connection**

**Terminal Profiles Features:**
1. Launch local terminals with pre-configured git environment variables
2. **Profile management** - Add/Edit/Duplicate/Delete profiles with dialog containing:
   - Name (required), Git Username (required), Git Email (required)
   - SSH Key Path (optional), Working Directory (optional)
3. Set environment variables when launching: GIT_AUTHOR_NAME, GIT_COMMITTER_NAME, GIT_AUTHOR_EMAIL, GIT_COMMITTER_EMAIL, GIT_SSH_COMMAND
4. **Close app after launching terminal**

**Keyboard shortcuts:**
- Tab: Switch between SSH Hosts and Terminal Profiles tabs
- Enter: Connect/Launch selected item
- Escape: Close application
- Shift+Up/Down: Reorder items in list

**Storage Format (~/.sshconnect):**
```json
{
  "version": 2,
  "ssh_hosts": [{"name": "...", "ip": "...", "username": "...", "port": 22, "certificate": "..."}],
  "terminal_profiles": [{"name": "...", "git_username": "...", "git_email": "...", "ssh_key_path": "...", "working_dir": "..."}]
}
```

**Implementation Details:**
- Migrate old config format (list) to new format (dict) automatically
- Use Gtk.Notebook for tabbed interface
- Use subprocess.Popen with env parameter for terminal profiles
- Window should be centered on screen
- Disable TreeView's built-in search (set_enable_search(False))

Create all necessary files with proper permissions and a README with installation instructions.

---