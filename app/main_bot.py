# TODO: Enable mypy strict checking for this file (currently excluded in pyproject.toml)
import importlib
import logging
import os
from typing import Optional

try:
    # When running as a script (e.g. python app/main_bot.py)
    import bootstrap
except ImportError:
    # When importing as a module (e.g. pytest)
    from app import bootstrap
bootstrap.setup_project_root()

import nextcord
from nextcord.ext import commands

import app

app.setup_logging("powercord")

import app.common.gsm_loader as gsecrets
from app.common.extension_loader import GadgetInspector
from app.ui.helpers import is_gadget_enabled  # Import validation helper

gsecrets.load_env()


# who you gonna call?
def get_prefix(bot, message):
    prefixes = ["$", "Powercord", "Powerbot"]
    if not message.guild:
        return 0
    return commands.when_mentioned_or(*prefixes)(bot, message)


# enable extra intents for advanced functionality
intents = nextcord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True


class ContextWrapper(commands.Context):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Load needed cog context function definitions into this class
        for cog, contexts in self.bot.cog_report.get("cog_custom_contexts", {}).items():
            if f"app.extensions.{cog}.cog" in self.bot.extensions.keys():
                for context in contexts:
                    module = importlib.import_module(f"app.extensions.{cog}.cog")
                    CogContexts = module.CogContexts
                    func = getattr(CogContexts, context)
                    setattr(self, context, func)


class Bot(commands.Bot):
    def __init__(self, *args, gadget_inspector: GadgetInspector, **kwargs):
        super().__init__(*args, **kwargs)
        self.gadget_inspector = gadget_inspector
        self.cog_report = self.gadget_inspector.inspect_cogs()
        self.persistent_modals_added = False
        self.persistent_views_added = False

    async def close(self):
        import asyncio

        if getattr(self, "bot_api_server", None):
            logging.info("Signaling Bot Internal API to shut down...")
            self.bot_api_server.should_exit = True

        if getattr(self, "bot_api_task", None):
            try:
                # Give Uvicorn a moment to clean up gracefully
                await asyncio.wait_for(self.bot_api_task, timeout=3.0)
            except asyncio.TimeoutError:
                logging.warning("Bot Internal API shutdown timed out, cancelling task...")
                self.bot_api_task.cancel()
            except Exception as e:
                logging.error(f"Error during Bot Internal API shutdown: {e}")

        await super().close()

    def _update_command_routing(self):
        """Dynamically update command routing based on which cogs are enabled in which guilds."""
        # 1. Back up all loaded commands the first time
        if not hasattr(self, "_all_loaded_commands") or not self._all_loaded_commands:
            self._all_loaded_commands = self._connection._application_commands.copy()

        # 2. Reset the bot's application commands state
        self._connection._application_commands.clear()
        self._connection._application_command_ids.clear()
        self._connection._application_command_signatures.clear()

        # Determine strict guilds restriction
        strict_guilds = set(_strict_guild_ids) if _strict_guild_ids else None

        for command in self._all_loaded_commands:
            # Find the extension name if this command is defined in a cog
            cog = getattr(command, "cog", None)
            extension_name = None
            if cog is not None:
                module_name = cog.__module__
                if module_name.startswith("app.extensions."):
                    # e.g., app.extensions.utilities.cog -> utilities
                    parts = module_name.split(".")
                    if len(parts) >= 3:
                        extension_name = parts[2]

            if extension_name:
                # Query enabled guilds for this extension
                enabled_guilds = get_enabled_guild_ids(self, extension_name)
                if strict_guilds:
                    enabled_guilds = enabled_guilds.intersection(strict_guilds)

                if enabled_guilds:
                    # Update command to register only to these guilds
                    command.force_global = False
                    command.use_default_guild_ids = False
                    command.guild_ids_to_rollout = enabled_guilds
                    # Remove the global ID (None) if it was in command_ids
                    command.command_ids.pop(None, None)
                    # Add back to bot
                    self.add_application_command(command, use_rollout=True, pre_remove=False)
                else:
                    # If not enabled in any guild, we do not add it back.
                    # Ensure None is popped from command_ids as well
                    command.command_ids.pop(None, None)
            else:
                # Core/global commands (not part of an extension)
                if strict_guilds:
                    command.force_global = False
                    command.use_default_guild_ids = False
                    command.guild_ids_to_rollout = strict_guilds
                    command.command_ids.pop(None, None)
                else:
                    command.force_global = True
                    command.use_default_guild_ids = False
                    command.guild_ids_to_rollout = set()
                self.add_application_command(command, use_rollout=True, pre_remove=False)

    async def rollout_application_commands(self, guild_id: Optional[int] = None):
        """Syncs application commands to all guilds (or a specific guild)."""
        logging.info(f"Rolling out application commands (guild_id={guild_id})...")
        try:
            self._update_command_routing()

            if guild_id is not None:
                await self.sync_application_commands(guild_id=guild_id)
                logging.info(f"Application commands synced successfully for guild {guild_id}.")
            else:
                # Fetch global commands
                data = {}
                try:
                    data[None] = await self.http.get_global_commands(self.application_id)
                except Exception as e:
                    logging.error(f"Failed to fetch global commands: {e}")

                # Fetch commands for all guilds the bot is currently in
                for guild in self.guilds:
                    try:
                        data[guild.id] = await self.http.get_guild_commands(self.application_id, guild.id)
                    except Exception as e:
                        logging.error(f"Failed to fetch commands for guild {guild.id}: {e}")

                await self.sync_all_application_commands(data=data)
                logging.info("Application commands synced successfully for all guilds.")
        except Exception as e:
            logging.error(f"Failed to sync application commands: {e}")

    async def get_context(self, message: nextcord.Message, *, cls=ContextWrapper):
        return await super().get_context(message, cls=cls)

    def _add_persistent_overrides(self, override_type):
        if override_type == "modal":
            override_list = self.cog_report.get("cog_persistent_modals", {})
        elif override_type == "view":
            override_list = self.cog_report.get("cog_persistent_views", {})
        else:
            return
        for cog, classes in override_list.items():
            if f"app.extensions.{cog}.cog" in self.extensions.keys():
                module = importlib.import_module(f"app.extensions.{cog}.cog")
                override = module.CogPersists
                for cls in classes:
                    override_class = getattr(override, cls)
                    if override_type == "modal":
                        self.add_modal(override_class())
                    elif override_type == "view":
                        self.add_view(override_class())

    def cog_logger(self):
        logging.info("Bot loaded!")
        logging.info(f"Custom cog contexts found: {self.cog_report.get('cog_custom_contexts')}")
        logging.info(f"Cog persistent modals found: {self.cog_report.get('cog_persistent_modals')}")
        logging.info(f"Cog persistent views found: {self.cog_report.get('cog_persistent_views')}")
        logging.info(
            f"{self.user.name}(id:{self.user.id}) has connected to Discord! (nextcord.py v{nextcord.__version__})\n"
        )
        logging.debug("Listening to the following servers...")
        for guild in self.guilds:
            logging.debug("\n============GUILD============\n")
            logging.debug(f"{guild.name}(id:{guild.id})")
            logging.debug("\n---------channels---------")
            for channel in guild.channels:
                logging.debug(f"{channel.name}(id:{channel.id})")
            logging.debug("\n----------members----------")
            for member in guild.members:
                logging.debug(f"{member.name}(id:{member.id})")

    async def on_ready(self):
        if not self.persistent_modals_added:
            logging.info("Adding custom persistent modals...")
            self._add_persistent_overrides("modal")
            self.persistent_modals_added = True
        if not self.persistent_views_added:
            logging.info("Adding custom persistent views...")
            self._add_persistent_overrides("view")
            self.persistent_views_added = True

        if not getattr(self, "bot_api_task", None):
            from app.bot.internal_server import start_bot_api

            logging.info("Starting Bot Internal API...")
            self.bot_api_task = self.loop.create_task(start_bot_api(self))

        if not getattr(self, "_commands_synced", False):
            await self.rollout_application_commands()
            self._commands_synced = True
        else:
            logging.info("Skipping command sync on reconnect (already synced).")

        self.cog_logger()

    async def on_guild_join(self, guild):
        """Sync application commands when the bot joins a new guild."""
        logging.info(f"Joined new guild: {guild.name} (id:{guild.id})")
        try:
            self._update_command_routing()
            await self.sync_application_commands(guild_id=guild.id)
            logging.info(f"Application commands synced for new guild: {guild.name}")
        except Exception as e:
            logging.error(f"Failed to sync commands for new guild {guild.name}: {e}")

    async def on_guild_remove(self, guild):
        """Log when the bot is removed from a guild."""
        logging.info(
            f"Removed from guild: {guild.name} (id:{guild.id}). "
            "Discord will automatically clean up registered commands."
        )


def get_enabled_guild_ids(bot, extension_name: str) -> set[int]:
    """Helper to get all guild IDs where a specific extension is enabled."""
    from sqlmodel import Session, select

    from app.common.alchemy import init_connection_engine
    from app.db.models import GuildExtensionSettings

    engine = init_connection_engine()
    try:
        with Session(engine) as session:
            # 1. Check Global Setting
            global_stmt = select(GuildExtensionSettings).where(
                GuildExtensionSettings.guild_id == 0,
                GuildExtensionSettings.extension_name == extension_name,
                GuildExtensionSettings.gadget_type == "cog",
            )
            global_setting = session.exec(global_stmt).first()

            # If global setting is explicitly disabled or missing, return empty set
            if not global_setting or not global_setting.is_enabled:
                return set()

            # 2. Get all local settings for this extension
            local_stmt = select(GuildExtensionSettings).where(
                GuildExtensionSettings.guild_id != 0,
                GuildExtensionSettings.extension_name == extension_name,
                GuildExtensionSettings.gadget_type == "cog",
            )
            local_settings = session.exec(local_stmt).all()
            local_map = {row.guild_id: row.is_enabled for row in local_settings}
    except Exception as e:
        logging.error(f"Error checking enabled guild IDs for {extension_name}: {e}")
        return set()

    enabled_guilds = set()
    for guild in bot.guilds:
        # Respect local override if present; default to True (inherit Global) if not present
        if local_map.get(guild.id, True):
            enabled_guilds.add(guild.id)

    return enabled_guilds


def _parse_strict_guild_ids() -> list[int]:
    """Parse POWERCORD_STRICT_GUILD_IDS from env (comma-separated integers).

    When set, commands are restricted to ONLY these guilds.
    Returns an empty list when unset, which registers commands globally.
    """
    raw = os.environ.get("POWERCORD_STRICT_GUILD_IDS", "")
    if not raw.strip():
        return []
    try:
        return [int(gid.strip()) for gid in raw.split(",") if gid.strip()]
    except ValueError:
        logging.warning(
            "POWERCORD_STRICT_GUILD_IDS contains non-integer values; falling back to global command registration."
        )
        return []


gadget_inspector = GadgetInspector()

_strict_guild_ids = _parse_strict_guild_ids()
if _strict_guild_ids:
    logging.info(f"Strict guild restriction active — commands limited to: {_strict_guild_ids}")
else:
    logging.info("No guild IDs configured; commands will register globally.")

bot = Bot(
    command_prefix=get_prefix,
    intents=intents,
    description="Powercord Powerbot",
    gadget_inspector=gadget_inspector,
    default_guild_ids=_strict_guild_ids or None,
)

# Load the powerloader cog first, as it's a core part of the bot
bot.load_extension("app.bot.powerloader")

# Load all other cogs found by the inspector
for cog_name in bot.cog_report.get("all_cogs", []):
    # Check if the cog is globally enabled (guild_id=0)
    if not is_gadget_enabled(0, cog_name, "cog"):
        logging.info(f"Skipping extension '{cog_name}' (disabled globally).")
        continue

    try:
        bot.load_extension(f"app.extensions.{cog_name}.cog")
    except Exception as e:
        logging.error(f"Failed to load extension {cog_name}: {e}")


if __name__ == "__main__":
    token = os.getenv("POWERCORD_DISCORD_TOKEN")
    if not token:
        logging.error("POWERCORD_DISCORD_TOKEN environment variable not set.")
        exit(1)

    # Suppress asyncio errors when the loop is closed.
    # This prevents the noisy 'sys.meta_path is None' ImportError caused by
    # rich attempting to log unclosed transport warnings during interpreter shutdown.
    import asyncio

    loop = asyncio.get_event_loop_policy().get_event_loop()

    def silence_event_loop_closed(loop, context):
        if loop.is_closed():
            return
        loop.default_exception_handler(context)

    loop.set_exception_handler(silence_event_loop_closed)

    bot.run(token)
