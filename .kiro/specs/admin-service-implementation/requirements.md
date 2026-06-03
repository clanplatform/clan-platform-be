# Requirements Document

## Introduction

The `admin-service` is a Python FastAPI microservice within the `clan-platform-domain-be` monorepo. It exposes two relational resources, **domains** and their child **applications**, plus the **menus** that form each application's navigation hierarchy. The service uses PostgreSQL for relational persistence, MongoDB for navigation/menu documents, and Redis for caching. A code review revealed that the service is currently non-runnable: the FastAPI entrypoint (`app/main.py`) is empty, the entire `app/core` layer (config, security, encryption, logging, middleware) is empty, the entire `app/infrastructure` layer (database session/base, cache, mongodb, external identity client, messaging) is empty, the API router and shared API helpers are empty, and all deployment/configuration artifacts (`Dockerfile`, root `docker-compose.yml`, `config/environments/local.env.example`, Alembic config, bootstrap scripts) are empty.

Additionally, the files that *do* contain code are internally inconsistent:
- The domains **route** layer imports from module paths that do not exist (`app.db.database`, `app.models.domain`, `app.schemas.domain`, `app.core.security.get_current_user_id`, `app.services.redis_cache`), while the real structure is `app/infrastructure/database/`, `app/domain_controls/models/`, `app/schemas/domains.py`, and `app/infrastructure/cache/`.
- The applications **route** layer imports from the same kind of non-existent module paths (`app.db.database`, `app.models.application`, `app.models.menu`, `app.models.user`, `app.schemas.application`, `app.schemas.menu`, `app.core.security.get_current_user`, `app.services.redis_cache`, `app.core.mongodb`), references an `Application` model, a `Menu` model, a `User` principal type, and a `Menu` schema that do not yet exist, contains a single-application read endpoint that is commented out, and uses the `get_current_user` dependency (which resolves a user object) rather than the `get_current_user_id` dependency used by the domains route.
- The domains **model** and **schema** define the field set `code`, `name`, `description`, `domain_metadata`, `is_active`, `is_deleted`, `deleted_at`, `created_at`, `updated_at` with a UUID primary key, and the **route** layer uses this same field set.
- The domains **service** layer instead references a different field set (`domain_name`, `domain_code`, `status`, `action`) and uses integer IDs, which is incompatible with the model, schema, and route.
- Both models import `Base` from the non-existent `app.db.database` module.

This feature delivers a runnable admin-service: a wired FastAPI application with Swagger/OpenAPI documentation, a fully reconciled and consistent domains resource (model, schema, repository, service, route), a fully reconciled and consistent applications resource (model, schema, repository, service, route) including create/read/update/soft-delete, per-domain listing, and MongoDB-backed navigation/menu assembly, working PostgreSQL + MongoDB + Redis integration with caching and invalidation, soft-delete cascade from domains to applications, authentication exposing both a caller-identifier dependency and a caller-principal dependency, sensitive-field encryption, structured logging, environment-based configuration, and Docker / docker-compose runnability that provisions the three datastores.

The canonical field set for the domains resource is the one shared by the **model, schema, and route** layers (`code`, `name`, `description`, `domain_metadata`, `is_active`, `is_deleted`, `deleted_at`, `created_at`, `updated_at`, UUID id). The service layer is the outlier and SHALL be reconciled to this canonical set; the legacy `domain_name`/`domain_code`/`status`/`action`/integer-id shape SHALL be removed.

## Glossary

- **Admin_Service**: The FastAPI microservice as a whole, exposing HTTP endpoints under `/api/v1`.
- **Application_Bootstrap**: The startup component implemented in `app/main.py` that constructs the FastAPI application instance, registers middleware, mounts routers, configures lifecycle (startup/shutdown) handlers, and exposes documentation.
- **Configuration_Provider**: The component in `app/core/config.py` that loads, validates, and exposes typed settings (database URLs, Redis URL, MongoDB URL, secrets, feature flags, cache TTL) from environment variables.
- **Domain_Router**: The API route layer in `app/api/v1/routes/domains/domains.py` that handles HTTP requests for the domains resource.
- **Domain_Service**: The service layer in `app/domain_controls/services/domains.py` containing domains business logic.
- **Domain_Repository**: The persistence/data-access layer in `app/domain_controls/repositories/` for the domains resource.
- **Domain_Model**: The SQLAlchemy ORM model in `app/domain_controls/models/domains.py` representing the `domains` table.
- **Domain_Schema**: The Pydantic schemas in `app/schemas/domains.py` (`DomainCreate`, `DomainUpdate`, `DomainResponse`).
- **Application_Model**: The SQLAlchemy ORM model in `app/domain_controls/models/applications.py` representing the `applications` table, which references a domain via `domain_id` and back-populates `Domain_Model.applications`.
- **Application_Router**: The API route layer in `app/api/v1/routes/applications/applications.py` that handles HTTP requests for the applications resource and the application navigation/menu endpoints.
- **Application_Service**: The service layer for the applications resource containing applications business logic, mirroring the placement convention of the Domain_Service.
- **Application_Repository**: The persistence/data-access layer for the applications resource, mirroring the placement convention of the Domain_Repository.
- **Application_Schema**: The Pydantic schemas in `app/schemas/applications.py` (`ApplicationBase`, `ApplicationCreate`, `ApplicationUpdate`, `ApplicationResponse`, `ApplicationWithMenusResponse`).
- **Canonical_Application_Fields**: The application field set `id` (UUID primary key), `domain_id` (UUID foreign key to `domains.id`), `name`, `description`, `version`, `status`, `config`, `is_active`, `access`, the navigation/UI fields `key`, `label`, `route`, `level`, `icon`, `badge`, `section_title`, `order_index`, and the soft-delete and timestamp fields `is_deleted`, `deleted_at`, `created_at`, `updated_at`.
- **Menu_Model**: The SQLAlchemy ORM model in `app/domain_controls/models/menus.py` representing the `menus` table, with fields `id`, `application_id`, `parent_menu_id`, `name`, `key`, `label`, `icon`, `menus_description`, `badge`, `section_title`, `route`, `component`, `level`, `order_index`, `is_active`, `deleted_at`, and `created_at`, modeling a self-referential parent/child menu hierarchy via `parent_menu_id`.
- **Menu_Schema**: The Pydantic schema in `app/schemas/menu.py` (`MenuResponse`) representing a menu in API responses.
- **Navigation_Document**: The assembled `mainNavigation` response with shape `{_id, config, mainNavigation, profileSection}`, where `mainNavigation` is an array containing one application sub-document and its recursive menu hierarchy, sourced from MongoDB and falling back to PostgreSQL-built structure when the MongoDB application sub-document is absent.
- **User_Principal**: The authenticated-caller object (the `User` type referenced by the Application_Router) returned by the Authenticator's `get_current_user` dependency.
- **Canonical_Domain_Fields**: The domain field set `code`, `name`, `description`, `domain_metadata`, `is_active`, `is_deleted`, `deleted_at`, `created_at`, `updated_at` with a UUID primary key `id`.
- **Postgres_Session_Provider**: The component in `app/infrastructure/database/` (`base.py`, `session.py`) that defines the declarative `Base`, the SQLAlchemy engine/session factory, and the `get_db` dependency.
- **Cache_Provider**: The Redis-backed component in `app/infrastructure/cache/` exposing `get`, `set`, `delete`, `delete_pattern`, `cache_domain`, and `get_cached_domain` operations.
- **Mongo_Provider**: The component in `app/infrastructure/mongodb/` that establishes the MongoDB connection and exposes a `get_mongodb` accessor.
- **Authenticator**: The authentication component in `app/core/security.py` (backed by `app/infrastructure/external/identity_client.py`) that resolves the authenticated caller and exposes both the `get_current_user_id` dependency (returning the caller's identifier) and the `get_current_user` dependency (returning the User_Principal).
- **Mongo_Navigation_Sync**: The behavior performed by the Application_Router during an application update that propagates navigation-relevant application field changes into the MongoDB Navigation_Document.
- **Encryption_Provider**: The component in `app/core/hybrid_encryption.py` exposing `encrypt_sensitive_field` and `decrypt_sensitive_field`.
- **Logging_Provider**: The component in `app/core/logging.py` that configures structured application logging.
- **Request_Middleware**: The middleware component in `app/core/middleware.py` (request context, correlation/request ID, error translation).
- **Event_Publisher**: The component in `app/infrastructure/messaging/` and `app/domain_controls/events/` that publishes domain lifecycle events to Kafka.
- **OpenAPI_Documentation**: The auto-generated Swagger UI and OpenAPI schema served by the Admin_Service.
- **Container_Runtime**: The Docker image (built from `services/admin-service/deploy/Dockerfile`) and the root `docker-compose.yml` orchestration that provisions the Admin_Service together with PostgreSQL, MongoDB, and Redis.
- **Local_Env_Template**: The environment configuration template at `config/environments/local.env.example`.
- **Soft_Delete**: Marking a record as removed by setting `is_active = false`, `is_deleted = true`, and `deleted_at` to the deletion timestamp, without physically removing the row.

## Requirements

### Requirement 1: FastAPI Application Bootstrap

**User Story:** As a backend developer, I want a complete FastAPI entrypoint, so that the admin-service starts and serves requests.

#### Acceptance Criteria

1. THE Application_Bootstrap SHALL construct a FastAPI application instance exposing a service title, description, and version, where each of the title, description, and version is a non-empty string.
2. THE Application_Bootstrap SHALL register the version 1 API router so that all domain and application endpoints are reachable only under the `/api/v1` path prefix.
3. WHEN the Admin_Service process starts, THE Application_Bootstrap SHALL execute startup logic that initializes the Postgres_Session_Provider, Cache_Provider, and Mongo_Provider connections, completing all three initializations within 30 seconds.
4. IF any of the Postgres_Session_Provider, Cache_Provider, or Mongo_Provider connections fails to initialize, or does not complete initialization within 30 seconds during startup, THEN THE Application_Bootstrap SHALL abort startup by terminating the process with a non-zero exit status, emitting an error that names the failed connection, and serving no requests.
5. WHEN the Admin_Service process receives a shutdown signal, THE Application_Bootstrap SHALL execute shutdown logic that closes the Postgres_Session_Provider, Cache_Provider, and Mongo_Provider connections within 30 seconds.
6. THE Application_Bootstrap SHALL register the Request_Middleware on the FastAPI application instance.
7. THE Application_Bootstrap SHALL configure the Logging_Provider during application startup before the first request is served.
8. WHEN the Admin_Service receives a GET request at the health-check path, THE Admin_Service SHALL respond within 500 milliseconds with HTTP status 200 and a JSON body indicating service health, performing a shallow liveness check that issues no queries to the Postgres_Session_Provider, Cache_Provider, or Mongo_Provider.

### Requirement 2: Configuration Management

**User Story:** As an operator, I want all runtime configuration sourced from environment variables, so that I can run the service across local, dev, and production environments without code changes.

#### Acceptance Criteria

1. THE Configuration_Provider SHALL expose typed settings for the PostgreSQL connection URL (string), the Redis connection URL (string), the MongoDB connection URL (string), the JWT/identity secret (string with a minimum length of 1 character), and the default cache TTL (integer expressed in whole seconds).
2. WHEN the Admin_Service starts, THE Configuration_Provider SHALL read each configuration value exclusively from its corresponding environment variable.
3. IF a required configuration value is absent at startup, THEN THE Configuration_Provider SHALL halt startup before the Admin_Service begins serving requests and raise a startup error that names the missing configuration key, even when a fallback default could otherwise be applied.
4. THE Configuration_Provider SHALL expose the default cache TTL as the setting `CACHE_DEFAULT_TTL`, an integer in whole seconds ranging from 1 to 86,400 inclusive, referenced by the Domain_Router.
5. THE Local_Env_Template SHALL document every environment variable that the Configuration_Provider reads, including the PostgreSQL URL, Redis URL, MongoDB URL, identity/JWT secret, and cache TTL, with a non-empty placeholder value for each variable suitable for local development.
6. WHERE an optional configuration value is not provided at startup, THE Configuration_Provider SHALL resolve the corresponding setting to the documented default value recorded in the Local_Env_Template.
7. IF a provided environment variable value cannot be parsed into its declared type or violates its declared bounds (for example, `CACHE_DEFAULT_TTL` is non-numeric or outside the range 1 to 86,400), THEN THE Configuration_Provider SHALL halt startup before the Admin_Service begins serving requests and raise a startup error that names the offending configuration key.

### Requirement 3: Module Path and Import Reconciliation

**User Story:** As a backend developer, I want all imports to resolve against the real project structure, so that the service imports without ModuleNotFoundError.

#### Acceptance Criteria

1. THE Domain_Router SHALL import the database session dependency, Domain_Model, Domain_Schema, Authenticator dependency, and Cache_Provider from module paths that resolve to existing modules in the project structure, such that each import statement loads without raising ModuleNotFoundError or ImportError.
2. THE Domain_Model SHALL import the declarative `Base` from the single Postgres_Session_Provider module that defines it, such that the import resolves to an existing `Base` attribute without raising ModuleNotFoundError, ImportError, or AttributeError.
3. THE Application_Model SHALL import the declarative `Base` from the same Postgres_Session_Provider module path used by the Domain_Model, such that both models reference one identical `Base` object.
4. WHEN the Admin_Service application module tree is imported at startup, THE Admin_Service SHALL resolve every Domain_Router, Domain_Model, Domain_Schema, Authenticator, Cache_Provider, and Postgres_Session_Provider import and complete import resolution without raising ModuleNotFoundError or ImportError.
5. THE Domain_Router SHALL reference the authenticated caller through the `get_current_user_id` dependency exposed by the Authenticator, such that the dependency import resolves to an existing callable without raising ModuleNotFoundError, ImportError, or AttributeError.
6. THE Domain_Router SHALL reference the cache operations through the Cache_Provider instance exposed by the infrastructure cache module, such that the instance import resolves to an existing object without raising ModuleNotFoundError, ImportError, or AttributeError.
7. THE Application_Router SHALL import the database session dependency, Application_Model, Menu_Model, Application_Schema, Menu_Schema, User_Principal type, Authenticator `get_current_user` dependency, Cache_Provider, and Mongo_Provider `get_mongodb` accessor from module paths that resolve to existing modules in the project structure, such that each import statement loads without raising ModuleNotFoundError, ImportError, or AttributeError.
8. THE Application_Model and Menu_Model SHALL import the declarative `Base` from the same Postgres_Session_Provider module path used by the Domain_Model, such that all three models reference one identical `Base` object.
9. WHEN the Admin_Service application module tree is imported at startup, THE Admin_Service SHALL resolve every Application_Router, Application_Model, Menu_Model, Application_Schema, Menu_Schema, and User_Principal import and complete import resolution without raising ModuleNotFoundError or ImportError.
10. IF any module path referenced by the Admin_Service application module tree cannot be resolved at startup, THEN THE Admin_Service SHALL halt startup and surface an error indicating the unresolved module path or attribute.

### Requirement 4: Domain Field-Set Reconciliation

**User Story:** As a backend developer, I want the model, schema, service, and route layers to agree on domain fields and identifier types, so that requests flow through all layers without attribute or type errors.

#### Acceptance Criteria

1. THE Domain_Model, Domain_Schema, Domain_Repository, Domain_Service, and Domain_Router SHALL reference domain attributes only from the Canonical_Domain_Fields (`id`, `code`, `name`, `description`, `domain_metadata`, `is_active`, `is_deleted`, `deleted_at`, `created_at`, `updated_at`).
2. THE Domain_Model SHALL define the domain primary key `id` as a UUID.
3. THE Domain_Service SHALL identify a domain by its UUID `id` and SHALL NOT accept or query domains by an integer identifier.
4. THE Domain_Service SHALL reference domain attributes using `code` and `name`, and SHALL NOT reference `domain_code` or `domain_name`.
5. THE Domain_Service SHALL NOT reference the removed legacy attributes `status` and `action` on the Domain_Model.
6. WHEN a domain is serialized in an API response, THE Domain_Router SHALL include exactly the fields `id`, `code`, `name`, `description`, `domain_metadata`, `is_active`, `created_at`, and `updated_at`.
7. WHEN a create, read, update, or delete request flows from the Domain_Router through the Domain_Service and Domain_Repository to the Domain_Model, THE Admin_Service SHALL complete the operation without raising an attribute-resolution error or an identifier type-mismatch error.
8. IF a request supplies a domain identifier that is not a valid UUID, THEN THE Domain_Router SHALL respond with a validation error and SHALL NOT query the Domain_Repository.

### Requirement 5: PostgreSQL Persistence Integration

**User Story:** As a backend developer, I want a working SQLAlchemy session layer, so that domain and application data persist to PostgreSQL.

#### Acceptance Criteria

1. THE Postgres_Session_Provider SHALL define exactly one declarative `Base` class that the Domain_Model, Application_Model, and Menu_Model inherit from, so that all models share the same metadata registry.
2. THE Postgres_Session_Provider SHALL create a SQLAlchemy engine using the PostgreSQL connection URL exposed by the Configuration_Provider.
3. THE Postgres_Session_Provider SHALL expose a `get_db` dependency that provides exactly one database session for the duration of a single request.
4. WHEN a request handler depends on `get_db`, THE Postgres_Session_Provider SHALL provide a session bound to the engine created from the configured PostgreSQL connection URL.
5. WHEN a request that depends on `get_db` completes successfully, THE Postgres_Session_Provider SHALL close the session before control returns to the server.
6. IF an error occurs while a `get_db` session is in use, THEN THE Postgres_Session_Provider SHALL roll back any uncommitted changes and close the session before propagating the error.
7. THE Postgres_Session_Provider SHALL provide a schema-creation capability that creates the `domains`, `applications`, and `menus` tables from the registered models, creating each table only if it does not already exist and leaving any existing table and its rows unchanged.

### Requirement 6: Domain CRUD Operations

**User Story:** As an API consumer, I want to create, read, update, and delete domains, so that I can manage the platform's core domain resource.

#### Acceptance Criteria

1. WHEN an authenticated caller submits a create-domain request with a `code` of 1 to 50 characters that is unique among non-deleted domains and a `name` of 1 to 100 characters that is unique among non-deleted domains, THE Domain_Router SHALL persist a new domain and respond with the created domain representation.
2. IF a create-domain request supplies a `name` that already exists on a non-deleted domain, THEN THE Domain_Router SHALL respond with HTTP status 400 and an error message indicating a duplicate name, and SHALL NOT persist a domain.
3. IF a create-domain request supplies a `code` that already exists on a non-deleted domain, THEN THE Domain_Router SHALL respond with HTTP status 400 and an error message indicating a duplicate code, and SHALL NOT persist a domain.
4. IF a create-domain request omits `code` or `name`, or supplies a `code` outside the 1 to 50 character range, or supplies a `name` outside the 1 to 100 character range, THEN THE Domain_Router SHALL respond with a validation error indicating the invalid field and SHALL NOT persist a domain.
5. WHEN an authenticated caller requests a list of domains, THE Domain_Router SHALL return only non-deleted domains ordered by `created_at` descending, applying a pagination offset (default 0, minimum 0) and a limit (default 100, minimum 1, maximum 1000).
6. WHEN an authenticated caller requests a domain by an `id` that exists and is non-deleted, THE Domain_Router SHALL return that domain.
7. IF an authenticated caller requests a domain by an `id` that does not exist or is deleted, THEN THE Domain_Router SHALL respond with HTTP status 404.
8. WHEN an authenticated caller submits an update-domain request for an existing non-deleted domain, THE Domain_Router SHALL apply only the fields present in the request, leave omitted fields unchanged, and return the updated domain.
9. IF an update-domain request targets an `id` that does not exist or is deleted, THEN THE Domain_Router SHALL respond with HTTP status 404 and SHALL NOT modify any domain.
10. IF an update-domain request changes `name` or `code` to a value already used by a different non-deleted domain, THEN THE Domain_Router SHALL respond with HTTP status 400 and an error message indicating the conflict, and SHALL NOT modify the target domain.
11. WHEN an authenticated caller submits a delete-domain request for an existing non-deleted domain, THE Domain_Router SHALL mark the domain as deleted, exclude it from subsequent list and read responses, and respond with a success confirmation.

### Requirement 7: Soft-Delete with Cascade to Applications

**User Story:** As an API consumer, I want deleting a domain to soft-delete its applications, so that no orphaned active applications remain after a domain is removed.

#### Acceptance Criteria

1. WHEN an authenticated caller deletes an existing non-deleted domain, THE Domain_Router SHALL apply Soft_Delete to that domain.
2. WHEN an authenticated caller deletes a domain, THE Domain_Router SHALL apply Soft_Delete to every non-deleted Application_Model record whose `domain_id` equals the deleted domain's `id`.
3. WHEN a domain soft-delete completes successfully, THE Domain_Router SHALL respond with a confirmation message that states the count of related applications that were soft-deleted.
4. IF a caller deletes a domain `id` that does not exist or is already deleted, THEN THE Domain_Router SHALL respond with HTTP status 404.
5. IF an error occurs during the domain soft-delete transaction, THEN THE Domain_Router SHALL roll back the transaction and respond with HTTP status 500.
6. WHEN a Soft_Delete is applied to a record, THE Admin_Service SHALL set `is_active` to false, `is_deleted` to true, and `deleted_at` to the deletion timestamp on that record, regardless of the record's prior `is_active` state.

### Requirement 8: Redis Caching and Invalidation

**User Story:** As an API consumer, I want domain reads served from cache and kept fresh, so that responses are fast and never stale after a write.

#### Acceptance Criteria

1. THE Cache_Provider SHALL expose the operations `get`, `set`, `delete`, `delete_pattern`, `cache_domain`, and `get_cached_domain` used by the Domain_Router.
2. WHEN the Domain_Router serves a domain list or single-domain read and a corresponding cache entry exists, THE Domain_Router SHALL return the cached value without querying PostgreSQL.
3. WHEN the Domain_Router serves a domain read that is not present in the cache, THE Domain_Router SHALL query PostgreSQL and store the result in the Cache_Provider using the default cache TTL from the Configuration_Provider.
4. WHEN a domain is created, updated, or deleted, THE Domain_Router SHALL invalidate the cached domains-list entries via the `domains:list:*` pattern.
5. WHEN a domain is updated or deleted, THE Domain_Router SHALL invalidate the cached single-domain entry for that domain `id`.
6. IF the Cache_Provider is unavailable when serving a read request, THEN THE Domain_Router SHALL serve the request from PostgreSQL without returning an error to the caller.
7. IF the Cache_Provider is unavailable during a domain create, update, or delete operation, THEN THE Domain_Router SHALL complete the PostgreSQL write and respond successfully without returning a cache error to the caller.

### Requirement 9: Cache Round-Trip Integrity

**User Story:** As a backend developer, I want cached domain representations to deserialize back into equivalent values, so that cached reads return the same data a fresh read would.

#### Acceptance Criteria

1. WHEN a domain representation is written to the Cache_Provider and subsequently read back before expiry, THE Cache_Provider SHALL return a value equal to the value that was written.
2. WHEN the Domain_Router serializes a domain for caching, THE Domain_Router SHALL produce a representation that deserializes into the same field values as the source domain.

### Requirement 10: Authentication

**User Story:** As a platform owner, I want domain endpoints to require an authenticated caller, so that only authorized users can manage domains.

#### Acceptance Criteria

1. THE Authenticator SHALL expose a `get_current_user_id` dependency that resolves the authenticated caller's identifier from the incoming request credentials.
2. THE Authenticator SHALL expose a `get_current_user` dependency that resolves the authenticated caller as a User_Principal object from the incoming request credentials, used by the Application_Router.
3. IF a request to a protected domain or application endpoint omits valid credentials, THEN THE Authenticator SHALL cause the Admin_Service to respond with HTTP status 401.
4. WHEN a request to a protected domain endpoint includes valid credentials, THE Authenticator SHALL provide the caller's identifier to the request handler through the `get_current_user_id` dependency.
5. WHEN a request to a protected application endpoint includes valid credentials, THE Authenticator SHALL provide the caller's User_Principal to the request handler through the `get_current_user` dependency.
6. THE Authenticator SHALL validate caller credentials using the identity secret exposed by the Configuration_Provider.

### Requirement 11: Sensitive-Field Encryption

**User Story:** As a security engineer, I want sensitive stored fields encrypted at rest, so that confidential values are protected in the database.

#### Acceptance Criteria

1. THE Encryption_Provider SHALL expose an `encrypt_sensitive_field` operation and a `decrypt_sensitive_field` operation.
2. WHEN a value is encrypted and then decrypted by the Encryption_Provider, THE Encryption_Provider SHALL return a value equal to the original input (round-trip property).
3. IF the Encryption_Provider attempts to decrypt a value that is not in encrypted form, THEN THE Encryption_Provider SHALL signal a decryption failure that the calling service layer can handle.

### Requirement 12: MongoDB Integration

**User Story:** As a backend developer, I want a working MongoDB accessor, so that navigation and menu document features can read and write MongoDB.

#### Acceptance Criteria

1. THE Mongo_Provider SHALL expose a `get_mongodb` accessor that returns a handle to the configured MongoDB database.
2. WHEN the Admin_Service starts, THE Mongo_Provider SHALL establish a connection using the MongoDB connection URL exposed by the Configuration_Provider.
3. IF the MongoDB connection cannot be established when a handler requests it, THEN THE Mongo_Provider SHALL signal unavailability so the handler can respond with HTTP status 503.

### Requirement 13: OpenAPI / Swagger Documentation

**User Story:** As an API consumer, I want interactive API documentation, so that I can explore and exercise the admin-service endpoints.

#### Acceptance Criteria

1. THE Admin_Service SHALL serve a Swagger UI documentation page at a documentation path.
2. THE Admin_Service SHALL serve an OpenAPI schema document describing the registered domain, application, and menu/navigation endpoints.
3. THE OpenAPI_Documentation SHALL include, for each domain and application endpoint, the request schema, the response schema, and the success status code.
4. THE OpenAPI_Documentation SHALL include, for the application navigation/menu endpoint, the response schema and the success status code.
5. THE OpenAPI_Documentation SHALL describe the authentication scheme required by protected endpoints.

### Requirement 14: Structured Logging and Request Middleware

**User Story:** As an operator, I want structured logs with request correlation, so that I can trace and diagnose requests across the service.

#### Acceptance Criteria

1. THE Logging_Provider SHALL configure application logging with a consistent structured format during startup.
2. WHEN the Admin_Service receives an HTTP request, THE Request_Middleware SHALL associate a request identifier with the request for the duration of its processing.
3. IF an unhandled error occurs while processing a request, THEN THE Request_Middleware SHALL translate the error into a JSON error response with an appropriate HTTP status code, overriding any partial successful response for that request.
4. WHEN a request completes, THE Logging_Provider SHALL emit a log entry that includes the request method, path, and response status code.

### Requirement 15: Domain Lifecycle Event Publishing

**User Story:** As a platform integrator, I want domain changes published as events, so that other services can react to domain lifecycle changes.

#### Acceptance Criteria

1. WHEN a domain is created, updated, or soft-deleted, THE Event_Publisher SHALL publish a corresponding domain lifecycle event that includes the domain `id` and the change type.
2. IF the Event_Publisher cannot reach the messaging broker, THEN THE Admin_Service SHALL complete the originating domain operation and record the publish failure in the logs.
3. WHERE event publishing is disabled by configuration, THE Admin_Service SHALL process domain operations without publishing events.

### Requirement 16: Docker and docker-compose Runnability

**User Story:** As a developer, I want to run the whole service and its datastores with one command, so that I can start the admin-service locally without manual setup.

#### Acceptance Criteria

1. THE Container_Runtime SHALL provide a Dockerfile that builds an image containing the Admin_Service and its Python dependencies.
2. THE Container_Runtime SHALL define a docker-compose configuration that provisions services for the Admin_Service, PostgreSQL, MongoDB, and Redis.
3. WHEN the docker-compose configuration is started, THE Container_Runtime SHALL inject the PostgreSQL, MongoDB, and Redis connection URLs into the Admin_Service container via environment variables consumed by the Configuration_Provider.
4. WHEN the Admin_Service container starts under docker-compose with all datastores available, THE Admin_Service SHALL become reachable and respond to its health-check endpoint with HTTP status 200.
5. WHEN the docker-compose configuration starts the Admin_Service, THE Container_Runtime SHALL run a schema-provisioning step that creates the `domains`, `applications`, and `menus` tables if they do not already exist.
6. THE Admin_Service SHALL respond to its health-check endpoint with HTTP status 200 independently of whether the `domains`, `applications`, and `menus` tables have finished provisioning.
7. THE requirements.txt SHALL declare the runtime dependencies (FastAPI, the ASGI server, SQLAlchemy, the PostgreSQL driver, the Redis client, the MongoDB driver, and the Kafka client) required to build and run the Container_Runtime image.

### Requirement 17: Dependency Declaration and Project Tooling

**User Story:** As a developer, I want declared dependencies and runnable entrypoints, so that the service installs and starts consistently.

#### Acceptance Criteria

1. THE requirements.txt SHALL pin versions for the declared runtime dependencies.
2. WHEN the declared dependencies are installed into a clean environment, THE Admin_Service SHALL import and start without a missing-dependency error.
3. THE Admin_Service SHALL expose an ASGI application object that an ASGI server can load to run the service.
