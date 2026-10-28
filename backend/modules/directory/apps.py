from django.apps import AppConfig


class DirectoryConfig(AppConfig):
    """The company directory: one Customer per phone number (or short code), shared by SMS and Calls. Gives caller ID on
    phones and a cross-channel customer timeline in the admin. Not a platform of its own."""

    name = "modules.directory"
    label = "directory"
    verbose_name = "Directory"
