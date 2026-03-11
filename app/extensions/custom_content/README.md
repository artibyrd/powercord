# Custom Content Extension

The `custom_content` extension provides an interactive way to create and manage custom widgets on the powercord public layout directly from the admin dashboard. 

It is designed to cleanly inject custom HTML or Markdown content anywhere into the UI layout via dynamic UI routing.

## Python Dependencies
- `nh3`: A robust Rust-based HTML sanitization library to automatically scrub XSS risks from rich text data.

## Database Schema Changes
- `CustomContentItem`: Stores the widget ID, guild affiliation, unique reference name, core content string, format toggle (html/markdown), and the `has_frame` layout toggle.

## Features

### UI Elements (Widgets)
- **Dynamic Widgets**: Creates a dynamic widget renderer per item built from the database on launch. Widgets are strictly globally configurable (`global_only` in `extension.json`) rather than server-specific.
- **Admin Editor**: An interactive widget builder located in the Admin Dashboard at (`/admin/custom_content`). It features a seamless toggle between a Markdown text area and a fully-featured Quill.js rich text editor.
- **Auto Injection**: New widgets bypass the standard `extension_manager` loader by directly populating their renderable functions into the active Python module namespace, making them instantly available to the `powerloader` layout engine.

## Security 
- Markdown inputs are passed safely to the frontend `marked.js` interpreter without risking script injection since no innerHTML execution is forced.
- Rich Text inputs (`html` format) are scrubbed server-side by `nh3` before entering the database.

> **Note:** Because this module operates solely via layout widgets and internal API routing, it securely bypasses Discord `cog` loading, making it safer to hot-reload without interrupting active bot sessions.
