# Firebase SQL Connect (Firebase Data Connect) Skill

Firebase SQL Connect is a relational database service using Cloud SQL for PostgreSQL with GraphQL schema, auto-generated queries/mutations, and type-safe SDKs.

## Project Structure
```text
dataconnect/
├── dataconnect.yaml      # Service configuration
├── schema/
│   └── schema.gql        # Data model (types with @table)
└── connector/
    ├── connector.yaml    # Connector config + SDK generation
    ├── queries.gql       # Queries
    └── mutations.gql     # Mutations
```

## Schema & Operations Rules
- Use `@table(name: "...", key: "...", singular: "...", plural: "...")`
- Support PostgreSQL jsonb columns via `@col(name: "...", dataType: "jsonb")`
- Auth directives: `@auth(level: PUBLIC)`
- SDK generation outputDir: `../../frontend/src/lib/dataconnect`
