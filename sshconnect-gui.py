#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango
import os
import sys
import json
import stat
import subprocess
import shlex
import webbrowser
from pathlib import Path
from typing import List, Dict, Optional

VERSION = "1.2.0"

class SSHHost:
    def __init__(self, name: str, ip: str, username: str = "", port: int = 22, certificate: str = "", links: List[Dict[str, str]] = None):
        self.name = name
        self.ip = ip
        self.username = username
        self.port = port
        self.certificate = certificate
        self.links = links if links is not None else []
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "ip": self.ip,
            "username": self.username,
            "port": self.port,
            "certificate": self.certificate,
            "links": self.links
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SSHHost':
        return cls(
            name=data.get("name", ""),
            ip=data.get("ip", ""),
            username=data.get("username", ""),
            port=data.get("port", 22),
            certificate=data.get("certificate", ""),
            links=data.get("links", [])
        )
    
    def get_ssh_args(self) -> List[str]:
        """Return SSH command as a list of arguments (safe for subprocess)."""
        args = ["ssh"]
        if self.certificate:
            args.extend(["-i", self.certificate])
        if self.port != 22:
            args.extend(["-p", str(self.port)])
        target = f"{self.username}@{self.ip}" if self.username else self.ip
        args.append(target)
        return args

    def get_ssh_command(self) -> str:
        """Return SSH command as string (for display purposes)."""
        return shlex.join(self.get_ssh_args())
    
    def get_display_text(self) -> str:
        host_str = self.ip
        if self.username:
            host_str = f"{self.username}@{self.ip}"
        if self.port != 22:
            host_str += f":{self.port}"
        return f"{self.name} - {host_str}"


class TerminalProfile:
    """A terminal profile with git identity settings."""
    def __init__(self, name: str, git_username: str, git_email: str,
                 ssh_key_path: str = "", working_dir: str = ""):
        self.name = name
        self.git_username = git_username
        self.git_email = git_email
        self.ssh_key_path = ssh_key_path
        self.working_dir = working_dir

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "git_username": self.git_username,
            "git_email": self.git_email,
            "ssh_key_path": self.ssh_key_path,
            "working_dir": self.working_dir
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TerminalProfile':
        return cls(
            name=data.get("name", ""),
            git_username=data.get("git_username", ""),
            git_email=data.get("git_email", ""),
            ssh_key_path=data.get("ssh_key_path", ""),
            working_dir=data.get("working_dir", "")
        )

    def get_display_text(self) -> str:
        return f"{self.name} - {self.git_username} <{self.git_email}>"

    def get_environment(self) -> Dict[str, str]:
        """Return environment variables to set for this profile."""
        env = {
            "GIT_AUTHOR_NAME": self.git_username,
            "GIT_COMMITTER_NAME": self.git_username,
            "GIT_AUTHOR_EMAIL": self.git_email,
            "GIT_COMMITTER_EMAIL": self.git_email,
        }
        if self.ssh_key_path:
            env["GIT_SSH_COMMAND"] = f"ssh -i {shlex.quote(self.ssh_key_path)} -o IdentitiesOnly=yes"
        return env

    def apply_persistent_identity(self, project_dir: str) -> tuple:
        """Apply this profile's git identity permanently to a repository.

        Creates a .gitconfig.local file in the project directory and configures
        git to include it. The identity will persist across terminal sessions.

        Args:
            project_dir: Path to the git repository root

        Returns:
            Tuple of (success: bool, message: str)
        """
        project_path = Path(project_dir)
        git_dir = project_path / ".git"

        if not git_dir.exists():
            return False, "Not a git repository (no .git directory found)"

        # Create .gitconfig.local
        config_file = project_path / ".gitconfig.local"
        config_content = f"[user]\n    name = {self.git_username}\n    email = {self.git_email}\n"

        try:
            config_file.write_text(config_content)
        except OSError as e:
            return False, f"Failed to create .gitconfig.local: {e}"

        # Check if include.path is already set
        try:
            result = subprocess.run(
                ["git", "-C", project_dir, "config", "--local", "--get", "include.path"],
                capture_output=True, text=True
            )
            if ".gitconfig.local" not in result.stdout:
                subprocess.run(
                    ["git", "-C", project_dir, "config", "--local", "include.path", "../.gitconfig.local"],
                    check=True
                )
        except subprocess.CalledProcessError as e:
            return False, f"Failed to configure git include path: {e}"
        except FileNotFoundError:
            return False, "git command not found"

        return True, f"Identity set for {project_path.name}: {self.git_username} <{self.git_email}>"


class HostDialog(Gtk.Dialog):
    def __init__(self, parent, title="Add Host", host: Optional[SSHHost] = None):
        super().__init__(title=title, parent=parent, modal=True)
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK
        )

        self.set_default_size(500, 400)

        # Connect response signal for validation
        self.connect("response", self.on_response)
        
        # Create notebook for tabs
        notebook = Gtk.Notebook()
        
        # === Connection Tab ===
        connection_grid = Gtk.Grid()
        connection_grid.set_row_spacing(10)
        connection_grid.set_column_spacing(10)
        connection_grid.set_margin_start(10)
        connection_grid.set_margin_end(10)
        connection_grid.set_margin_top(10)
        connection_grid.set_margin_bottom(10)
        
        # Name field
        name_label = Gtk.Label(label="Name:")
        name_label.set_halign(Gtk.Align.END)
        connection_grid.attach(name_label, 0, 0, 1, 1)
        
        self.name_entry = Gtk.Entry()
        self.name_entry.set_hexpand(True)
        if host:
            self.name_entry.set_text(host.name)
        connection_grid.attach(self.name_entry, 1, 0, 1, 1)
        
        # IP field
        ip_label = Gtk.Label(label="IP/Hostname:")
        ip_label.set_halign(Gtk.Align.END)
        connection_grid.attach(ip_label, 0, 1, 1, 1)
        
        self.ip_entry = Gtk.Entry()
        if host:
            self.ip_entry.set_text(host.ip)
        connection_grid.attach(self.ip_entry, 1, 1, 1, 1)
        
        # Username field
        username_label = Gtk.Label(label="Username:")
        username_label.set_halign(Gtk.Align.END)
        connection_grid.attach(username_label, 0, 2, 1, 1)
        
        self.username_entry = Gtk.Entry()
        if host:
            self.username_entry.set_text(host.username)
        connection_grid.attach(self.username_entry, 1, 2, 1, 1)
        
        # Port field
        port_label = Gtk.Label(label="Port:")
        port_label.set_halign(Gtk.Align.END)
        connection_grid.attach(port_label, 0, 3, 1, 1)
        
        self.port_entry = Gtk.Entry()
        self.port_entry.set_text(str(host.port if host else 22))
        connection_grid.attach(self.port_entry, 1, 3, 1, 1)
        
        # Certificate field
        cert_label = Gtk.Label(label="Certificate:")
        cert_label.set_halign(Gtk.Align.END)
        connection_grid.attach(cert_label, 0, 4, 1, 1)
        
        cert_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.cert_entry = Gtk.Entry()
        self.cert_entry.set_hexpand(True)
        if host:
            self.cert_entry.set_text(host.certificate)
        cert_box.pack_start(self.cert_entry, True, True, 0)
        
        browse_button = Gtk.Button(label="Browse")
        browse_button.connect("clicked", self.on_browse_certificate)
        cert_box.pack_start(browse_button, False, False, 0)
        connection_grid.attach(cert_box, 1, 4, 1, 1)
        
        notebook.append_page(connection_grid, Gtk.Label(label="Connection"))
        
        # === Links Tab ===
        links_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        links_box.set_margin_start(10)
        links_box.set_margin_end(10)
        links_box.set_margin_top(10)
        links_box.set_margin_bottom(10)
        
        # Create scrolled window for links list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(250)
        links_box.pack_start(scrolled, True, True, 0)
        
        # Create list store for links (name, url)
        self.links_store = Gtk.ListStore(str, str)
        
        # Load existing links if editing
        if host and host.links:
            for link in host.links:
                self.links_store.append([link.get("name", ""), link.get("url", "")])
        
        # Always add an empty row at the end for new entries
        self.links_store.append(["", ""])
        
        # Create tree view
        self.links_tree = Gtk.TreeView(model=self.links_store)
        
        # Name column
        self.name_renderer = Gtk.CellRendererText()
        self.name_renderer.set_property("editable", True)
        self.name_renderer.connect("edited", self.on_link_name_edited)
        self.name_renderer.connect("editing-started", self.on_editing_started)
        name_column = Gtk.TreeViewColumn("Name", self.name_renderer, text=0)
        name_column.set_expand(True)
        self.links_tree.append_column(name_column)
        
        # URL column
        self.url_renderer = Gtk.CellRendererText()
        self.url_renderer.set_property("editable", True)
        self.url_renderer.connect("edited", self.on_link_url_edited)
        self.url_renderer.connect("editing-started", self.on_editing_started)
        url_column = Gtk.TreeViewColumn("URL", self.url_renderer, text=1)
        url_column.set_expand(True)
        self.links_tree.append_column(url_column)
        
        scrolled.add(self.links_tree)
        
        # Button box for links
        links_button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        add_link_button = Gtk.Button(label="Add Link")
        add_link_button.connect("clicked", self.on_add_link)
        links_button_box.pack_start(add_link_button, False, False, 0)
        
        remove_link_button = Gtk.Button(label="Remove Link")
        remove_link_button.connect("clicked", self.on_remove_link)
        links_button_box.pack_start(remove_link_button, False, False, 0)
        
        links_box.pack_start(links_button_box, False, False, 0)
        
        notebook.append_page(links_box, Gtk.Label(label="Links"))
        
        # Add notebook to dialog
        box = self.get_content_area()
        box.add(notebook)
        
        # Set focus on name entry
        self.name_entry.grab_focus()
        
        self.show_all()
    
    def on_browse_certificate(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Select SSH Certificate",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )
        
        # Set default folder to ~/.ssh if it exists
        ssh_dir = Path.home() / ".ssh"
        if ssh_dir.exists():
            dialog.set_current_folder(str(ssh_dir))
        
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.cert_entry.set_text(dialog.get_filename())
        
        dialog.destroy()
    
    def on_editing_started(self, renderer, editable, path):
        # Connect Tab key to move to next cell
        editable.connect("key-press-event", self.on_cell_key_press, path, renderer)
    
    def on_cell_key_press(self, widget, event, path, renderer):
        if event.keyval == Gdk.KEY_Tab:
            # Finish current edit
            widget.emit("activate")
            
            # Determine next cell to edit
            path_int = int(path)
            if renderer == self.name_renderer:
                # Move to URL column in same row
                GLib.idle_add(self.start_editing, path_int, 1)
            else:  # url_renderer
                # Move to Name column in next row
                GLib.idle_add(self.start_editing, path_int + 1, 0)
            return True
        return False
    
    def start_editing(self, row, column):
        # Ensure the row exists
        if row >= len(self.links_store):
            return False
            
        tree_path = Gtk.TreePath(row)
        tree_column = self.links_tree.get_column(column)
        self.links_tree.set_cursor(tree_path, tree_column, True)
        return False
    
    def ensure_empty_row(self):
        # Check if the last row is empty, if not add one
        if len(self.links_store) == 0:
            self.links_store.append(["", ""])
        else:
            last_row = self.links_store[-1]
            if last_row[0] or last_row[1]:  # If last row has content
                self.links_store.append(["", ""])
    
    def on_add_link(self, button):
        # Find the first empty row or add a new one
        for i, row in enumerate(self.links_store):
            if not row[0] and not row[1]:
                # Focus on this empty row
                tree_path = Gtk.TreePath(i)
                tree_column = self.links_tree.get_column(0)
                self.links_tree.set_cursor(tree_path, tree_column, True)
                return
        
        # If no empty row found, add one and focus it
        self.links_store.append(["", ""])
        tree_path = Gtk.TreePath(len(self.links_store) - 1)
        tree_column = self.links_tree.get_column(0)
        self.links_tree.set_cursor(tree_path, tree_column, True)
    
    def on_remove_link(self, button):
        # Get selected row and remove it
        selection = self.links_tree.get_selection()
        model, iter = selection.get_selected()
        if iter:
            model.remove(iter)
        self.ensure_empty_row()
    
    def on_link_name_edited(self, renderer, path, new_text):
        self.links_store[path][0] = new_text
        self.ensure_empty_row()
    
    def on_link_url_edited(self, renderer, path, new_text):
        self.links_store[path][1] = new_text
        self.ensure_empty_row()
    
    def validate(self) -> Optional[str]:
        """Validate form inputs. Returns error message or None if valid."""
        name = self.name_entry.get_text().strip()
        ip = self.ip_entry.get_text().strip()
        port_text = self.port_entry.get_text().strip()

        if not name:
            self.name_entry.grab_focus()
            return "Name is required."

        if not ip:
            self.ip_entry.grab_focus()
            return "IP/Hostname is required."

        if port_text:
            try:
                port = int(port_text)
                if port < 1 or port > 65535:
                    self.port_entry.grab_focus()
                    return "Port must be between 1 and 65535."
            except ValueError:
                self.port_entry.grab_focus()
                return "Port must be a valid number."

        return None

    def on_response(self, dialog, response_id):
        """Handle dialog response with validation."""
        if response_id == Gtk.ResponseType.OK:
            error = self.validate()
            if error:
                self.show_validation_error(error)
                # Stop the response from closing the dialog
                self.stop_emission_by_name("response")

    def show_validation_error(self, message: str):
        """Show a validation error message."""
        error_dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            message_format="Validation Error"
        )
        error_dialog.format_secondary_text(message)
        error_dialog.run()
        error_dialog.destroy()

    def get_host(self) -> Optional[SSHHost]:
        name = self.name_entry.get_text().strip()
        ip = self.ip_entry.get_text().strip()
        username = self.username_entry.get_text().strip()
        certificate = self.cert_entry.get_text().strip()

        try:
            port = int(self.port_entry.get_text())
            if port < 1 or port > 65535:
                port = 22
        except ValueError:
            port = 22

        # Collect links from the links store (excluding empty rows)
        links = []
        for row in self.links_store:
            link_name = row[0].strip()
            link_url = row[1].strip()
            if link_name and link_url:  # Only add if both fields have content
                links.append({"name": link_name, "url": link_url})

        if name and ip:
            return SSHHost(name, ip, username, port, certificate, links)
        return None


class TerminalProfileDialog(Gtk.Dialog):
    """Dialog for adding/editing terminal profiles."""
    def __init__(self, parent, title="Add Terminal Profile", profile: Optional[TerminalProfile] = None):
        super().__init__(title=title, parent=parent, modal=True)
        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK
        )

        self.set_default_size(450, 300)
        self.connect("response", self.on_response)

        # Create form grid
        grid = Gtk.Grid()
        grid.set_row_spacing(10)
        grid.set_column_spacing(10)
        grid.set_margin_start(10)
        grid.set_margin_end(10)
        grid.set_margin_top(10)
        grid.set_margin_bottom(10)

        # Name field
        name_label = Gtk.Label(label="Profile Name:")
        name_label.set_halign(Gtk.Align.END)
        grid.attach(name_label, 0, 0, 1, 1)

        self.name_entry = Gtk.Entry()
        self.name_entry.set_hexpand(True)
        if profile:
            self.name_entry.set_text(profile.name)
        grid.attach(self.name_entry, 1, 0, 1, 1)

        # Git Username field
        git_user_label = Gtk.Label(label="Git Username:")
        git_user_label.set_halign(Gtk.Align.END)
        grid.attach(git_user_label, 0, 1, 1, 1)

        self.git_username_entry = Gtk.Entry()
        if profile:
            self.git_username_entry.set_text(profile.git_username)
        grid.attach(self.git_username_entry, 1, 1, 1, 1)

        # Git Email field
        git_email_label = Gtk.Label(label="Git Email:")
        git_email_label.set_halign(Gtk.Align.END)
        grid.attach(git_email_label, 0, 2, 1, 1)

        self.git_email_entry = Gtk.Entry()
        if profile:
            self.git_email_entry.set_text(profile.git_email)
        grid.attach(self.git_email_entry, 1, 2, 1, 1)

        # SSH Key Path field
        ssh_key_label = Gtk.Label(label="SSH Key:")
        ssh_key_label.set_halign(Gtk.Align.END)
        grid.attach(ssh_key_label, 0, 3, 1, 1)

        ssh_key_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.ssh_key_entry = Gtk.Entry()
        self.ssh_key_entry.set_hexpand(True)
        if profile:
            self.ssh_key_entry.set_text(profile.ssh_key_path)
        ssh_key_box.pack_start(self.ssh_key_entry, True, True, 0)

        ssh_key_browse = Gtk.Button(label="Browse")
        ssh_key_browse.connect("clicked", self.on_browse_ssh_key)
        ssh_key_box.pack_start(ssh_key_browse, False, False, 0)
        grid.attach(ssh_key_box, 1, 3, 1, 1)

        # Working Directory field
        working_dir_label = Gtk.Label(label="Working Dir:")
        working_dir_label.set_halign(Gtk.Align.END)
        grid.attach(working_dir_label, 0, 4, 1, 1)

        working_dir_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.working_dir_entry = Gtk.Entry()
        self.working_dir_entry.set_hexpand(True)
        if profile:
            self.working_dir_entry.set_text(profile.working_dir)
        working_dir_box.pack_start(self.working_dir_entry, True, True, 0)

        working_dir_browse = Gtk.Button(label="Browse")
        working_dir_browse.connect("clicked", self.on_browse_working_dir)
        working_dir_box.pack_start(working_dir_browse, False, False, 0)
        grid.attach(working_dir_box, 1, 4, 1, 1)

        # Add grid to dialog
        box = self.get_content_area()
        box.add(grid)

        self.name_entry.grab_focus()
        self.show_all()

    def on_browse_ssh_key(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Select SSH Key",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )
        ssh_dir = Path.home() / ".ssh"
        if ssh_dir.exists():
            dialog.set_current_folder(str(ssh_dir))

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.ssh_key_entry.set_text(dialog.get_filename())
        dialog.destroy()

    def on_browse_working_dir(self, button):
        dialog = Gtk.FileChooserDialog(
            title="Select Working Directory",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN, Gtk.ResponseType.OK
        )
        dialog.set_current_folder(str(Path.home()))

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.working_dir_entry.set_text(dialog.get_filename())
        dialog.destroy()

    def validate(self) -> Optional[str]:
        """Validate form inputs. Returns error message or None if valid."""
        name = self.name_entry.get_text().strip()
        git_username = self.git_username_entry.get_text().strip()
        git_email = self.git_email_entry.get_text().strip()

        if not name:
            self.name_entry.grab_focus()
            return "Profile name is required."
        if not git_username:
            self.git_username_entry.grab_focus()
            return "Git username is required."
        if not git_email:
            self.git_email_entry.grab_focus()
            return "Git email is required."
        if git_email and "@" not in git_email:
            self.git_email_entry.grab_focus()
            return "Git email must be a valid email address."
        return None

    def on_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            error = self.validate()
            if error:
                self.show_validation_error(error)
                self.stop_emission_by_name("response")

    def show_validation_error(self, message: str):
        error_dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            message_format="Validation Error"
        )
        error_dialog.format_secondary_text(message)
        error_dialog.run()
        error_dialog.destroy()

    def get_profile(self) -> Optional[TerminalProfile]:
        name = self.name_entry.get_text().strip()
        git_username = self.git_username_entry.get_text().strip()
        git_email = self.git_email_entry.get_text().strip()
        ssh_key_path = self.ssh_key_entry.get_text().strip()
        working_dir = self.working_dir_entry.get_text().strip()

        if name and git_username and git_email:
            return TerminalProfile(name, git_username, git_email, ssh_key_path, working_dir)
        return None


class SSHConnectWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title=f"Termina Launcher v{VERSION}")
        self.set_default_size(600, 400)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.config_file = Path.home() / ".sshconnect"
        self.hosts: List[SSHHost] = []
        self.terminal_profiles: List[TerminalProfile] = []
        self.load_config()

        # Create UI
        self.setup_ui()

        # Connect signals
        self.connect("destroy", Gtk.main_quit)
        self.connect("key-press-event", self.on_key_press)

        # Load data into lists
        self.populate_host_list()
        self.populate_profiles_list()

        # Focus search entry on first tab
        self.hosts_search_entry.grab_focus()
    
    def setup_ui(self):
        # Main vertical box
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        self.add(vbox)

        # Create notebook for tabs
        self.notebook = Gtk.Notebook()
        vbox.pack_start(self.notebook, True, True, 0)

        # === SSH Hosts Tab ===
        hosts_page = self.create_hosts_tab()
        self.notebook.append_page(hosts_page, Gtk.Label(label="SSH Hosts"))

        # === Terminal Profiles Tab ===
        profiles_page = self.create_profiles_tab()
        self.notebook.append_page(profiles_page, Gtk.Label(label="Terminal Profiles"))

        self.show_all()

    def create_hosts_tab(self) -> Gtk.Box:
        """Create the SSH Hosts tab content."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(6)
        vbox.set_margin_end(6)
        vbox.set_margin_top(6)
        vbox.set_margin_bottom(6)

        # Search box
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(search_box, False, False, 0)

        search_label = Gtk.Label(label="Search:")
        search_box.pack_start(search_label, False, False, 0)

        self.hosts_search_entry = Gtk.SearchEntry()
        self.hosts_search_entry.set_placeholder_text("Type to filter hosts...")
        self.hosts_search_entry.connect("search-changed", self.on_hosts_search_changed)
        search_box.pack_start(self.hosts_search_entry, True, True, 0)

        # Create scrolled window for list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        vbox.pack_start(scrolled, True, True, 0)

        # Create list store and tree view
        self.hosts_list_store = Gtk.ListStore(str, object, str)  # Display text, SSHHost object, Links text
        self.hosts_tree_view = Gtk.TreeView(model=self.hosts_list_store)
        self.hosts_tree_view.set_headers_visible(False)
        self.hosts_tree_view.set_enable_search(False)
        self.hosts_tree_view.connect("row-activated", self.on_host_row_activated)

        # Host column
        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        host_column = Gtk.TreeViewColumn("Host", renderer, text=0)
        host_column.set_expand(True)
        self.hosts_tree_view.append_column(host_column)

        # Links column
        links_renderer = Gtk.CellRendererText()
        links_column = Gtk.TreeViewColumn("Links", links_renderer)
        links_column.set_cell_data_func(links_renderer, self.render_links_cell)
        self.hosts_tree_view.append_column(links_column)

        # Connect button press event for link clicking
        self.hosts_tree_view.connect("button-press-event", self.on_hosts_tree_button_press)

        scrolled.add(self.hosts_tree_view)

        # Button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(button_box, False, False, 0)

        add_button = Gtk.Button(label="Add")
        add_button.connect("clicked", self.on_host_add_clicked)
        button_box.pack_start(add_button, False, False, 0)

        edit_button = Gtk.Button(label="Edit")
        edit_button.connect("clicked", self.on_host_edit_clicked)
        button_box.pack_start(edit_button, False, False, 0)

        duplicate_button = Gtk.Button(label="Duplicate")
        duplicate_button.connect("clicked", self.on_host_duplicate_clicked)
        button_box.pack_start(duplicate_button, False, False, 0)

        delete_button = Gtk.Button(label="Delete")
        delete_button.connect("clicked", self.on_host_delete_clicked)
        button_box.pack_start(delete_button, False, False, 0)

        connect_button = Gtk.Button(label="Connect")
        connect_button.get_style_context().add_class("suggested-action")
        connect_button.connect("clicked", self.on_host_connect_clicked)
        button_box.pack_end(connect_button, False, False, 0)

        return vbox

    def create_profiles_tab(self) -> Gtk.Box:
        """Create the Terminal Profiles tab content."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.set_margin_start(6)
        vbox.set_margin_end(6)
        vbox.set_margin_top(6)
        vbox.set_margin_bottom(6)

        # Search box
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(search_box, False, False, 0)

        search_label = Gtk.Label(label="Search:")
        search_box.pack_start(search_label, False, False, 0)

        self.profiles_search_entry = Gtk.SearchEntry()
        self.profiles_search_entry.set_placeholder_text("Type to filter profiles...")
        self.profiles_search_entry.connect("search-changed", self.on_profiles_search_changed)
        search_box.pack_start(self.profiles_search_entry, True, True, 0)

        # Create scrolled window for list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        vbox.pack_start(scrolled, True, True, 0)

        # Create list store and tree view
        self.profiles_list_store = Gtk.ListStore(str, object)  # Display text, TerminalProfile object
        self.profiles_tree_view = Gtk.TreeView(model=self.profiles_list_store)
        self.profiles_tree_view.set_headers_visible(False)
        self.profiles_tree_view.set_enable_search(False)
        self.profiles_tree_view.connect("row-activated", self.on_profile_row_activated)

        # Profile column
        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        profile_column = Gtk.TreeViewColumn("Profile", renderer, text=0)
        profile_column.set_expand(True)
        self.profiles_tree_view.append_column(profile_column)

        scrolled.add(self.profiles_tree_view)

        # Button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vbox.pack_start(button_box, False, False, 0)

        add_button = Gtk.Button(label="Add")
        add_button.connect("clicked", self.on_profile_add_clicked)
        button_box.pack_start(add_button, False, False, 0)

        edit_button = Gtk.Button(label="Edit")
        edit_button.connect("clicked", self.on_profile_edit_clicked)
        button_box.pack_start(edit_button, False, False, 0)

        duplicate_button = Gtk.Button(label="Duplicate")
        duplicate_button.connect("clicked", self.on_profile_duplicate_clicked)
        button_box.pack_start(duplicate_button, False, False, 0)

        delete_button = Gtk.Button(label="Delete")
        delete_button.connect("clicked", self.on_profile_delete_clicked)
        button_box.pack_start(delete_button, False, False, 0)

        launch_button = Gtk.Button(label="Launch")
        launch_button.get_style_context().add_class("suggested-action")
        launch_button.connect("clicked", self.on_profile_launch_clicked)
        button_box.pack_end(launch_button, False, False, 0)

        return vbox
    
    def show_error_dialog(self, title: str, message: str):
        """Display an error dialog to the user."""
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            message_format=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def load_config(self):
        """Load configuration with migration from old format."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)

                # Check if old format (list) or new format (dict)
                if isinstance(data, list):
                    # Old format - migrate
                    self.hosts = [SSHHost.from_dict(host) for host in data]
                    self.terminal_profiles = []
                    # Save in new format
                    self.save_config()
                else:
                    # New format
                    self.hosts = [SSHHost.from_dict(h) for h in data.get("ssh_hosts", [])]
                    self.terminal_profiles = [TerminalProfile.from_dict(p)
                                              for p in data.get("terminal_profiles", [])]
            except json.JSONDecodeError as e:
                self.hosts = []
                self.terminal_profiles = []
                GLib.idle_add(self.show_error_dialog, "Configuration Error",
                    f"Failed to parse configuration file:\n{self.config_file}\n\nError: {e}")
            except Exception as e:
                self.hosts = []
                self.terminal_profiles = []
                GLib.idle_add(self.show_error_dialog, "Configuration Error",
                    f"Failed to load configuration:\n{e}")

    def save_config(self):
        """Save configuration in new format."""
        try:
            data = {
                "version": 2,
                "ssh_hosts": [host.to_dict() for host in self.hosts],
                "terminal_profiles": [profile.to_dict() for profile in self.terminal_profiles]
            }
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
            # Restrict permissions to owner only (600)
            os.chmod(self.config_file, stat.S_IRUSR | stat.S_IWUSR)
        except Exception as e:
            self.show_error_dialog("Save Error",
                f"Failed to save configuration to:\n{self.config_file}\n\nError: {e}")
    
    # === SSH Hosts Methods ===

    def populate_host_list(self, filter_text=""):
        self.hosts_list_store.clear()

        filter_lower = filter_text.lower()
        for host in self.hosts:
            if filter_lower in host.name.lower() or filter_lower in host.ip.lower():
                links_text = " | ".join([link["name"] for link in host.links]) if host.links else ""
                self.hosts_list_store.append([host.get_display_text(), host, links_text])

        if len(self.hosts_list_store) == 1:
            self.hosts_tree_view.set_cursor(Gtk.TreePath(0))

    def render_links_cell(self, column, cell, model, iter, data):
        links_text = model.get_value(iter, 2)
        if links_text:
            cell.set_property("markup", f'<span foreground="#3584e4" underline="single">{GLib.markup_escape_text(links_text)}</span>')
        else:
            cell.set_property("text", "")

    def on_hosts_tree_button_press(self, widget, event):
        if event.button == 1:
            path_info = widget.get_path_at_pos(int(event.x), int(event.y))
            if path_info:
                path, column, cell_x, cell_y = path_info
                if column == widget.get_column(1):
                    iter = self.hosts_list_store.get_iter(path)
                    host = self.hosts_list_store.get_value(iter, 1)
                    if host.links:
                        self.show_links_menu(event, host.links)
                        return True
        return False

    def show_links_menu(self, event, links):
        menu = Gtk.Menu()
        for link in links:
            item = Gtk.MenuItem(label=link["name"])
            item.connect("activate", lambda w, url=link["url"]: webbrowser.open(url))
            menu.append(item)
        menu.show_all()
        menu.popup_at_pointer(event)

    def move_host_up(self):
        selection = self.hosts_tree_view.get_selection()
        model, iter = selection.get_selected()
        if not iter:
            return

        selected_host = model[iter][1]
        selected_index = self.hosts.index(selected_host)

        if selected_index > 0:
            self.hosts[selected_index], self.hosts[selected_index - 1] = \
                self.hosts[selected_index - 1], self.hosts[selected_index]
            self.save_config()
            self.populate_host_list(self.hosts_search_entry.get_text())

            for i, row in enumerate(self.hosts_list_store):
                if row[1] == selected_host:
                    self.hosts_tree_view.set_cursor(Gtk.TreePath(i))
                    break

    def move_host_down(self):
        selection = self.hosts_tree_view.get_selection()
        model, iter = selection.get_selected()
        if not iter:
            return

        selected_host = model[iter][1]
        selected_index = self.hosts.index(selected_host)

        if selected_index < len(self.hosts) - 1:
            self.hosts[selected_index], self.hosts[selected_index + 1] = \
                self.hosts[selected_index + 1], self.hosts[selected_index]
            self.save_config()
            self.populate_host_list(self.hosts_search_entry.get_text())

            for i, row in enumerate(self.hosts_list_store):
                if row[1] == selected_host:
                    self.hosts_tree_view.set_cursor(Gtk.TreePath(i))
                    break

    def get_selected_host(self) -> Optional[SSHHost]:
        selection = self.hosts_tree_view.get_selection()
        model, iter = selection.get_selected()
        if iter:
            return model[iter][1]
        return None

    def connect_to_host(self, host: SSHHost):
        """Open SSH connection in a new terminal window."""
        args = ["gnome-terminal", "--"] + host.get_ssh_args()
        try:
            subprocess.Popen(args)
        except FileNotFoundError:
            self.show_error_dialog("Terminal Not Found",
                "gnome-terminal is not installed. Please install it or configure an alternative terminal.")
            return
        except Exception as e:
            self.show_error_dialog("Connection Error", f"Failed to launch terminal: {e}")
            return
        self.close()

    def on_hosts_search_changed(self, entry):
        self.populate_host_list(entry.get_text())

    def on_host_row_activated(self, tree_view, path, column):
        host = self.hosts_list_store[path][1]
        self.connect_to_host(host)

    def on_host_add_clicked(self, button):
        dialog = HostDialog(self, "Add Host")
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            new_host = dialog.get_host()
            if new_host:
                self.hosts.append(new_host)
                self.save_config()
                self.populate_host_list(self.hosts_search_entry.get_text())
        dialog.destroy()

    def on_host_edit_clicked(self, button):
        host = self.get_selected_host()
        if not host:
            return
        dialog = HostDialog(self, "Edit Host", host)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            edited_host = dialog.get_host()
            if edited_host:
                index = self.hosts.index(host)
                self.hosts[index] = edited_host
                self.save_config()
                self.populate_host_list(self.hosts_search_entry.get_text())
        dialog.destroy()

    def on_host_duplicate_clicked(self, button):
        host = self.get_selected_host()
        if not host:
            return
        # Create a copy with " (copy)" appended to name
        duplicate = SSHHost(
            name=f"{host.name} (copy)",
            ip=host.ip,
            username=host.username,
            port=host.port,
            certificate=host.certificate,
            links=[dict(link) for link in host.links]  # Deep copy links
        )
        self.hosts.append(duplicate)
        self.save_config()
        self.populate_host_list(self.hosts_search_entry.get_text())

    def on_host_delete_clicked(self, button):
        host = self.get_selected_host()
        if not host:
            return
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            message_format=f"Delete host '{host.name}'?"
        )
        dialog.format_secondary_text("This action cannot be undone.")
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            self.hosts.remove(host)
            self.save_config()
            self.populate_host_list(self.hosts_search_entry.get_text())

    def on_host_connect_clicked(self, button):
        host = self.get_selected_host()
        if host:
            self.connect_to_host(host)

    # === Terminal Profiles Methods ===

    def populate_profiles_list(self, filter_text=""):
        self.profiles_list_store.clear()

        filter_lower = filter_text.lower()
        for profile in self.terminal_profiles:
            if (filter_lower in profile.name.lower() or
                filter_lower in profile.git_username.lower() or
                filter_lower in profile.git_email.lower()):
                self.profiles_list_store.append([profile.get_display_text(), profile])

        if len(self.profiles_list_store) == 1:
            self.profiles_tree_view.set_cursor(Gtk.TreePath(0))

    def get_selected_profile(self) -> Optional[TerminalProfile]:
        selection = self.profiles_tree_view.get_selection()
        model, iter = selection.get_selected()
        if iter:
            return model[iter][1]
        return None

    def launch_terminal_profile(self, profile: TerminalProfile):
        """Open a terminal with git environment variables set."""
        env = os.environ.copy()
        env.update(profile.get_environment())

        # If working directory is a git repo, set persistent identity
        if profile.working_dir:
            git_dir = Path(profile.working_dir) / ".git"
            if git_dir.exists():
                profile.apply_persistent_identity(profile.working_dir)

        args = ["gnome-terminal"]
        if profile.working_dir:
            args.extend(["--working-directory", profile.working_dir])

        try:
            subprocess.Popen(args, env=env)
        except FileNotFoundError:
            self.show_error_dialog("Terminal Not Found",
                "gnome-terminal is not installed. Please install it or configure an alternative terminal.")
            return
        except Exception as e:
            self.show_error_dialog("Launch Error", f"Failed to launch terminal: {e}")
            return
        self.close()

    def move_profile_up(self):
        selection = self.profiles_tree_view.get_selection()
        model, iter = selection.get_selected()
        if not iter:
            return

        selected_profile = model[iter][1]
        selected_index = self.terminal_profiles.index(selected_profile)

        if selected_index > 0:
            self.terminal_profiles[selected_index], self.terminal_profiles[selected_index - 1] = \
                self.terminal_profiles[selected_index - 1], self.terminal_profiles[selected_index]
            self.save_config()
            self.populate_profiles_list(self.profiles_search_entry.get_text())

            for i, row in enumerate(self.profiles_list_store):
                if row[1] == selected_profile:
                    self.profiles_tree_view.set_cursor(Gtk.TreePath(i))
                    break

    def move_profile_down(self):
        selection = self.profiles_tree_view.get_selection()
        model, iter = selection.get_selected()
        if not iter:
            return

        selected_profile = model[iter][1]
        selected_index = self.terminal_profiles.index(selected_profile)

        if selected_index < len(self.terminal_profiles) - 1:
            self.terminal_profiles[selected_index], self.terminal_profiles[selected_index + 1] = \
                self.terminal_profiles[selected_index + 1], self.terminal_profiles[selected_index]
            self.save_config()
            self.populate_profiles_list(self.profiles_search_entry.get_text())

            for i, row in enumerate(self.profiles_list_store):
                if row[1] == selected_profile:
                    self.profiles_tree_view.set_cursor(Gtk.TreePath(i))
                    break

    def on_profiles_search_changed(self, entry):
        self.populate_profiles_list(entry.get_text())

    def on_profile_row_activated(self, tree_view, path, column):
        profile = self.profiles_list_store[path][1]
        self.launch_terminal_profile(profile)

    def on_profile_add_clicked(self, button):
        dialog = TerminalProfileDialog(self, "Add Terminal Profile")
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            new_profile = dialog.get_profile()
            if new_profile:
                self.terminal_profiles.append(new_profile)
                self.save_config()
                self.populate_profiles_list(self.profiles_search_entry.get_text())
        dialog.destroy()

    def on_profile_edit_clicked(self, button):
        profile = self.get_selected_profile()
        if not profile:
            return
        dialog = TerminalProfileDialog(self, "Edit Terminal Profile", profile)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            edited_profile = dialog.get_profile()
            if edited_profile:
                index = self.terminal_profiles.index(profile)
                self.terminal_profiles[index] = edited_profile
                self.save_config()
                self.populate_profiles_list(self.profiles_search_entry.get_text())
        dialog.destroy()

    def on_profile_duplicate_clicked(self, button):
        profile = self.get_selected_profile()
        if not profile:
            return
        # Create a copy with " (copy)" appended to name
        duplicate = TerminalProfile(
            name=f"{profile.name} (copy)",
            git_username=profile.git_username,
            git_email=profile.git_email,
            ssh_key_path=profile.ssh_key_path,
            working_dir=profile.working_dir
        )
        self.terminal_profiles.append(duplicate)
        self.save_config()
        self.populate_profiles_list(self.profiles_search_entry.get_text())

    def on_profile_delete_clicked(self, button):
        profile = self.get_selected_profile()
        if not profile:
            return
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            message_format=f"Delete profile '{profile.name}'?"
        )
        dialog.format_secondary_text("This action cannot be undone.")
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            self.terminal_profiles.remove(profile)
            self.save_config()
            self.populate_profiles_list(self.profiles_search_entry.get_text())

    def on_profile_launch_clicked(self, button):
        profile = self.get_selected_profile()
        if profile:
            self.launch_terminal_profile(profile)

    # === Keyboard Handling ===

    def on_key_press(self, widget, event):
        # Escape closes the app
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True

        # Tab switches between notebook tabs (when search entry or tree view has focus)
        if event.keyval == Gdk.KEY_Tab:
            focus_widget = self.get_focus()
            if focus_widget in [self.hosts_tree_view, self.profiles_tree_view,
                                self.hosts_search_entry, self.profiles_search_entry]:
                current_page = self.notebook.get_current_page()
                next_page = (current_page + 1) % self.notebook.get_n_pages()
                self.notebook.set_current_page(next_page)
                # Focus the search entry of the new page
                if next_page == 0:
                    self.hosts_search_entry.grab_focus()
                else:
                    self.profiles_search_entry.grab_focus()
                return True

        # Enter key handling
        if event.keyval == Gdk.KEY_Return:
            current_page = self.notebook.get_current_page()
            if current_page == 0:  # SSH Hosts tab
                if self.hosts_search_entry.has_focus() and len(self.hosts_list_store) == 1:
                    host = self.hosts_list_store[0][1]
                    self.connect_to_host(host)
                    return True
                elif self.hosts_tree_view.has_focus():
                    host = self.get_selected_host()
                    if host:
                        self.connect_to_host(host)
                        return True
            else:  # Terminal Profiles tab
                if self.profiles_search_entry.has_focus() and len(self.profiles_list_store) == 1:
                    profile = self.profiles_list_store[0][1]
                    self.launch_terminal_profile(profile)
                    return True
                elif self.profiles_tree_view.has_focus():
                    profile = self.get_selected_profile()
                    if profile:
                        self.launch_terminal_profile(profile)
                        return True

        # Shift+Arrow keys for reordering
        if event.state & Gdk.ModifierType.SHIFT_MASK:
            current_page = self.notebook.get_current_page()
            if event.keyval == Gdk.KEY_Up:
                if current_page == 0:
                    self.move_host_up()
                else:
                    self.move_profile_up()
                return True
            elif event.keyval == Gdk.KEY_Down:
                if current_page == 0:
                    self.move_host_down()
                else:
                    self.move_profile_down()
                return True

        return False

def main():
    app = SSHConnectWindow()
    Gtk.main()

if __name__ == "__main__":
    main()