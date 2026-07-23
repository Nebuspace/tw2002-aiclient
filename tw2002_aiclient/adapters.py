"""Thin adapters from the product TUI onto twclient backend APIs."""

from __future__ import annotations

from twclient import credentials, servers


def list_launcher_rows(profiles_path=None, servers_path=None):
    return credentials.list_profile_summaries(
        profiles_path=profiles_path, servers_path=servers_path
    )


def list_server_keys(servers_path=None):
    return [rec["key"] for rec in servers.list_servers(path=servers_path)]


def server_label(key, servers_path=None):
    rec = servers.get_server(key, path=servers_path)
    return f"{rec['key']}  {rec['hostname']}:{rec['port']}"


def create_profile(**kwargs):
    return credentials.create_profile(**kwargs)


def set_autopilot(profile_name, enabled, profiles_path=None):
    credentials.set_profile_autopilot(profile_name, enabled, profiles_path=profiles_path)


def load_profile(name, profiles_path=None, servers_path=None):
    return credentials.load_profile(
        name, profiles_path=profiles_path, servers_path=servers_path
    )


def save_password(profile_name, password, secrets_path=None):
    if password:
        credentials.save_password(profile_name, password, secrets_path=secrets_path)
