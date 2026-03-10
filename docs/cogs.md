# About Powercord Cog Hotloading
Certain Nextcord features (custom contexts, persistent modals/views) cannot be hot loaded and must be loaded when the bot first starts up.

When using custom cog contexts, use a class named `CogContexts` that inherits from `commands.Context`, and place your custom context functions in this class with the prefix `cc_`.

For persistent modals/views, create a class called `CogPersists` in your cog, and put your persistent modal/view classes inside this class.  Persistent modal classes inside this class should inherit from `nextcord.ui.Modal`, and persistent views from `nextcord.ui.View`.

See the [example cog](../app/extensions/example/cog.py) for implementation details.

Powercord will perform introspection on all cog files found in the extensions folder, and create a dictionary of cog names mapped to lists of any custom contexts or persistent modals/views found in each one.  This is referenced before the bot is first instantiated, so any cogs that use custom contexts or persistent modals/views will now have their components found and registered properly before the bot starts up!

**NOTICE:** Cogs that use these features cannot be hot loaded for these same reasons. Powercord will also use this introspection to prevent hot loading/unloading/reloading of any cogs that have registered custom contexts or persistent modals/views.  To make changes to these features, the bot must be restarted.

## Auto-Reload on Toggle

When a cog is toggled on or off via the **Manage Extensions (Global)** section on the Admin Dashboard, Powercord will automatically attempt to load or unload the cog in the running bot instance:

- **Toggled ON** → The cog is loaded and its slash commands are synced to Discord.
- **Toggled OFF** → The cog is unloaded and its slash commands are removed from Discord.

If the cog has registered preload requirements (persistent views/modals/contexts), the auto-reload is **skipped** and a warning message is displayed instead, indicating that a full bot restart is needed.

The manual **Reload** button (🔄) on each extension card remains available for forcing a reload at any time.

## Restart Bot

A **Restart Bot** button is available on the Admin Dashboard under the **Bot Management** section. This gracefully shuts down the bot process. In production environments (Docker, systemd), the process manager will automatically restart it. During local development with `just dev`, the bot process will stop and must be manually restarted.
