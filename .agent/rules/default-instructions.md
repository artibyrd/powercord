---
trigger: always_on
---

Follow these instructions at all times:
- Run python scripts using poetry.
- Check the @/Justfile for commands to interact with the project.  Update the @/Justfile with new recipes when relevant.
- Ensure solutions are scalable and secure.
- Create new tests to cover your changes.  Keep overall test coverage over 80%.
- Run `just db-upgrade` after making database schema changes.
- Run `just qa fix` to resolve any linting errors and prevent regressions after making changes.
- Make sure code has robust and accurate inline comments.
- Update/create README.md files explaining technical details and implementation steps.