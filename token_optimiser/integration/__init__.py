"""Integration boundaries for the Monica cockpit (read/draft-oriented)."""


def read_only_adapter_list():
    return [
        "mail",
        "repo_tasks",
        "cockpit_events",
        "cockpit_tasks",
        "cockpit_reminders",
        "cockpit_panels",
    ]
