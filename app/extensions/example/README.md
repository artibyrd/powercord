# Example Extension

The `example` extension serves as a template and reference implementation for building new extensions in Powercord. It demonstrates the core concepts of the extension architecture, including database interactions, Discord bot commands, API routes, and dashboard UI components.

## Python Dependencies
- None (Standard Library)

## Database Schema Changes
- `TodoItem`: Represents a basic structure with fields for ID, content, user ID, and completion status. Demonstrates how to initialize tables safely.

## Features

### Bot Features (Cogs)
- **Commands**:
  - `/add_todo`: A slash command to add an item to the database.
  - `/list_todo`: A slash command to retrieve items from the database.
  - `!ping`: A traditional prefix command.
  - `Context Menu Commands`: Includes interactive UI components.
- **Listeners**:
  - `on_message`: Demonstrates how to safely listen to chat events.
- **Tasks**:
  - `example_loop`: An asynchronous background loop that runs periodically to perform maintenance or checks.

> **Note**: Cogs utilizing persistent views or modals cannot be hot-reloaded and require a full bot restart.

### API Routes (Sprockets)
- `GET /example/todos`: Retrieves a list of TodoItems.
- `POST /example/todos`: Creates a new TodoItem.
- `PUT /example/todos/{id}`: Updates an existing TodoItem.
- `DELETE /example/todos/{id}`: Deletes a TodoItem.

### UI Elements (Widgets)
- `public_example_card`: A simple informational widget visible to public visitors.
- `public_example_todo_list`: A live rendering of TodoItems fetched from the active database session.
- `admin_example_controls_widget`: A widget strictly prefixed with `admin_` to guarantee it only appears in the System Admin dashboard, featuring actionable forms hitting backend endpoints.

## Setup Instructions
This extension is enabled by default for demonstration purposes. To create a new extension, simply copy this folder structure, rename the components, and build out your logic!
