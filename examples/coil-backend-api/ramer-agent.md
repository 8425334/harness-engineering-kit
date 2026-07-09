# ramer-agent.md — coil-backend-api Adaptation

## Architecture Style Distribution

This project has two architecture styles coexisting:

| Module | Style | Characteristics |
|--------|-------|----------------|
| `coil-wx-service/wx/` (login) | hexagonal-ddd | `domain/model/` + `port/` + `adapter/` + `application/` |
| `coil-backend-service/` | layered | `controller/` → `service/impl/` → mapper (no port abstraction) |
| `coil-wx-service/wx/` (dispatch) | layered | `service/` + `service/impl/` + `service/dispatch/` support |

The agent detects the target area's existing style during the READ phase and decides during ANALYZE whether to continue or upgrade.

## DDD Reference Implementation

This project's wx login module serves as the RAMER Agent's DDD reference template:

| Concept | File | What the Agent Learns |
|---------|------|----------------------|
| Aggregate Root | `WxLoginSession.java` | Factory method `start()`, invariants in `bind()` |
| Value Object | `WxOpenId.java`, `PhoneNumber.java` | Java record, constructor validation |
| Domain Service | `WxLoginDomainService.java` | Plain Java, `new` instantiation, returns sealed type `Identification` |
| Port (Repository) | `WxUserIdentityRepository.java` | Methods use only `WxOpenId`/`WxUserRef`, no `SysUserVo` leak |
| Adapter (ACL) | `SysUserIdentityRepositoryAdapter.java` | `toRef()` method projects `SysUserVo → WxUserRef` |
| Application Service | `WxLoginApplicationService.java` | Injects 6 port interfaces, orchestrates two-phase login flow |
| Domain Event | `WxUserLoginEvent.java` | extends `ApplicationEvent`, payload uses `WxOpenId` |

## Relationship with Existing Methodology

| Existing Methodology | Relationship to This Document |
|---------------------|------------------------------|
| `ramer-cycle.md` | This is RAMER's **automation execution layer**; ramer-cycle.md defines **principles and phase content** |
| `ddd-modeling.md` | ANALYZE agent's architecture decision tree references DDD strategic/tactical design concepts; MODEL agent produces DDD-compliant contracts |
| `abstraction-first.md` | MODEL agent's contract-first coding order directly implements ACL translation layer |
| `harness-engineering.md` | `/ramer` skill is a component of this project's harness system |
| `fitness-framework.md` | REVIEW agent calls fitness gate as automated quality check |

## Coordination with SDD

RAMER Agent and SDD are not alternatives:

- **SDD** manages change **lifecycle** (propose → apply → sync → archive), tracking specs/deltas/tasks
- **RAMER Agent** automates the **technical implementation** within SDD's apply phase (read context → analyze boundaries → produce design → write code → run gate)

They can be chained: after `/opsx:propose`, use `/ramer` during the apply phase to auto-generate the implementation.
