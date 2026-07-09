# abstraction-first.md — coil-backend-api Adaptation

## ACL in This Project

- **A (Abstraction)**: `coil-app/coil-common/domain/` — Entity, VO, BO define domain concepts
- **C (Contract)**: Mapper interfaces (`BaseMapperPlus`), Service interfaces, Domain Events (`ApplicationEvent`)
- **L (Logic)**: `coil-service/coil-backend-service/service/` — concrete implementations

## Entity Quartet Pattern

Each business entity requires 5 coordinated artifacts:

| Artifact | Module | Package | Notes |
|----------|--------|---------|-------|
| Entity | `coil-app/coil-common` | `org.dromara.coil.domain` | Extends `TenantEntity`, uses `@TableName`, `@TableId(type=ASSIGN_ID)` (snowflake), `@TableLogic` |
| VO | `coil-app/coil-common` | `org.dromara.coil.domain.vo` | `@AutoMapper(target=Driver.class)` enables auto-conversion |
| BO | `coil-app/coil-common` | `org.dromara.coil.domain.bo` | Input object for create/update |
| Mapper | `coil-app/coil-dal` | `org.dromara.coil.mapper` | Extends `BaseMapperPlus<Entity, Vo>` |
| XML | `coil-app/coil-dal` | `resources/mapper/coil/` | Custom SQL for complex queries |

MapStruct-Plus (`@AutoMapper`) auto-generates bidirectional converters between Entity and VO. `BaseMapperPlus` leverages these converters via `selectVoOne()`, `selectVoList()` — no manual mapper interfaces needed.
