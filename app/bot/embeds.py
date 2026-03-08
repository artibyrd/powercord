import nextcord


class EmbedFactory:
    """
    Factory for creating consistent embeds.
    """

    @staticmethod
    def _create(title: str, description: str, color: nextcord.Color, **kwargs) -> nextcord.Embed:
        embed = nextcord.Embed(title=title, description=description, color=color, **kwargs)
        return embed

    @staticmethod
    def success(title: str, description: str, **kwargs) -> nextcord.Embed:
        """
        Creates a success embed (Green).

        Args:
            title (str): The title of the embed.
            description (str): The description of the embed.

        Returns:
            nextcord.Embed: A green embed.
        """
        return EmbedFactory._create(title, description, nextcord.Color.green(), **kwargs)

    @staticmethod
    def error(title: str, description: str, **kwargs) -> nextcord.Embed:
        """
        Creates an error embed (Red).

        Args:
            title (str): The title of the embed.
            description (str): The description of the embed.

        Returns:
            nextcord.Embed: A red embed.
        """
        return EmbedFactory._create(title, description, nextcord.Color.red(), **kwargs)

    @staticmethod
    def warning(title: str, description: str, **kwargs) -> nextcord.Embed:
        """
        Creates a warning embed (Gold).

        Args:
            title (str): The title of the embed.
            description (str): The description of the embed.

        Returns:
            nextcord.Embed: A gold embed.
        """
        return EmbedFactory._create(title, description, nextcord.Color.gold(), **kwargs)

    @staticmethod
    def info(title: str, description: str, **kwargs) -> nextcord.Embed:
        """
        Creates an info embed (Blue).

        Args:
            title (str): The title of the embed.
            description (str): The description of the embed.

        Returns:
            nextcord.Embed: A blue embed.
        """
        return EmbedFactory._create(title, description, nextcord.Color.blue(), **kwargs)
