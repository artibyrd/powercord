# Core Utilities Documentation

This document describes the core utilities available in `app/api`, `app/bot`, and `app/ui`.

## API Utilities

### Responses (`app.api.responses`)

Standardized response models for consistent API communication.

```python
from app.api.responses import success_response, error_response

@app.get("/items/{item_id}")
async def read_item(item_id: int):
    if item_id == 0:
        return error_response(message="Item not found", status_code=404)
    return success_response(data={"item_id": item_id}, message="Item retrieved")
```

### Dependencies (`app.api.dependencies`)

#### `get_current_api_user`

Unified API authentication dependency. Validates Internal API keys,
Database API keys, and Discord OAuth tokens. Returns a dict with
`identity` and `scopes`.

```python
from app.api.dependencies import get_current_api_user
from fastapi import Depends

@app.get("/protected", dependencies=[Depends(get_current_api_user)])
async def protected_route():
    ...
```

#### `api_scope_required`

Dependency generator to secure an endpoint to a specific scope.

```python
from app.api.dependencies import api_scope_required
from fastapi import Depends

@app.get("/honeypot/data", dependencies=[Depends(api_scope_required("honeypot"))])
async def honeypot_data():
    ...
```

## Bot Utilities

### Embeds (`app.bot.embeds`)

#### `EmbedFactory`

Creates standardized embeds with consistent colors.

```python
from app.bot.embeds import EmbedFactory

embed = EmbedFactory.success(title="Success!", description="Operation completed.")
await ctx.send(embed=embed)
```

- `success`: Green
- `error`: Red
- `warning`: Gold
- `info`: Blue

### Views (`app.bot.views`)

#### `ConfirmationView`

A simple "Confirm/Cancel" view.

```python
from app.bot.views import ConfirmationView

view = ConfirmationView()
await ctx.send("Are you sure?", view=view)
await view.wait()

if view.value is True:
    await ctx.send("Confirmed!")
elif view.value is False:
    await ctx.send("Cancelled!")
else:
    await ctx.send("Timed out.")
```

## UI Utilities

### Components (`app.ui.components`)

Reusable FastHTML components for consistent styling.

```python
from app.ui.components import PrimaryButton, Card, FormInput

form = Form(
    FormInput(name="username", placeholder="Username"),
    PrimaryButton("Submit"),
)

card = Card(title="Login", content=form)
```
