# Example Extension

The `example` extension serves as a template and reference implementation for building new extensions in Powercord. It demonstrates the core concepts of the extension architecture, including database interactions, Discord bot commands, API routes, and dashboard UI components.

## Python Dependencies
- None (Standard Library)

## Database Schema Changes
- `TodoItem`: Represents a basic structure with fields for ID, content, user ID, and completion status. Demonstrates how to initialize tables safely.

## Features

### Bot Features (Cogs)
- **Commands**:
  - `!helloworld`: A simple prefix command that replies with "Hello, world!".
  - `!headsortails`: A prefix command for a coin flip game.
  - `!roll`: A dice-rolling prefix command in NdN format.
  - `Context Menu Commands`: Includes interactive UI components (user and message commands).
- **Listeners**:
  - `on_message_delete`: Logs deleted messages to the channel.
  - `on_message_edit`: Logs message edits showing before/after content.
- **Tasks**:
  - `bg_counter_task`: An asynchronous background loop (using `tasks.loop`) that runs periodically to demonstrate background task execution.

> **Note**: Cogs utilizing persistent views or modals cannot be hot-reloaded and require a full bot restart.

### API Routes (Sprockets)
- `GET /example/todos/`: Retrieves a list of TodoItems.
- `POST /example/todos/`: Creates a new TodoItem.
- `PUT /example/todos/{id}`: Updates an existing TodoItem.
- `DELETE /example/todos/{id}`: Deletes a TodoItem.

### UI Elements (Widgets)
- `welcome_widget`: A simple informational widget visible to visitors.
- `another_widget`: An additional example widget.
- `todo_widget`: A live rendering of TodoItems fetched from the active database session.
- `admin_example_controls_widget`: A widget strictly prefixed with `admin_` to guarantee it only appears in the System Admin dashboard, featuring actionable forms hitting backend endpoints.

## Setup Instructions
This extension is enabled by default for demonstration purposes. To create a new extension, simply copy this folder structure, rename the components, and build out your logic!

### Environment Variables
- `POWERCORD_EXAMPLE_WEBHOOK_URL`: (Optional) The URL of a Discord webhook to send a message to for testing purposes.
