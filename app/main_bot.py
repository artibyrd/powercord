# TODO: Enable mypy strict checking for this file (currently excluded in pyproject.toml)
import importlib
import logging
import os

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

    async def rollout_application_commands(self):
        """Syncs application commands to all guilds."""
        logging.info("Rolling out application commands...")
        # Force sync of application commands
        try:
            await self.sync_all_application_commands()

            logging.info("Application commands synced successfully.")
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

        await self.rollout_application_commands()  # Force sync on startup

        self.cog_logger()


gadget_inspector = GadgetInspector()

bot = Bot(
    command_prefix=get_prefix,
    intents=intents,
    description="Powercord Powerbot",
    gadget_inspector=gadget_inspector,
    default_guild_ids=[256838244027727872],  # Force commands to be guild-specific for dev
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
        logging.error("DISCORD_TOKEN environment variable not set.")
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
