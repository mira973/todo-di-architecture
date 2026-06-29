---
name: archtool-web-fractal-style
description: Use when writing, reviewing, or refactoring Python code in a project that uses archtool (>=2.0) and web_fractal (FastAPI + SQLAlchemy async). Covers the canonical 9-file module layout per bounded context (interfaces, exceptions, dtos, dms, models, repos, services, controllers, dependencies), Clean Architecture layer enforcement, DI via class-level annotations and manual register() for pre-built clients and async resources, web_fractal helpers (UnitOfWork, serialize, apply_filters, Pagination, HttpControllerABC with reg_route), DDD-style domain exceptions mapped to HTTPException only inside controllers, the archtool CLI (init, add-module, validate, graph), and migration from legacy archtool 0.x to 2.x. Trigger on requests to add a domain, add an endpoint, wire up a third-party service, write a test with a mock, refactor to this style, or any work in a repo that imports from archtool or web_fractal.
---

# Архитектурный стиль: archtool + web_fractal

Документ для агента, который пишет код в этом стеке. Содержит правила, шаблоны и рецепты. Project-agnostic — везде, где нужно подставить имя домена/сущности, используются плейсхолдеры:

- `<Domain>` — CamelCase, singular (`Order`, `Project`, `Page`)
- `<domain>` — snake_case, singular (`order`, `project`, `page`)
- `<domains>` — snake_case, plural — для API-префикса и `__tablename__` (`orders`, `projects`, `pages`)
- `<Entity>` — дополнительная сущность внутри домена (`OrderItem` внутри `Order`)

## Целевая версия

Этот документ описывает **archtool ≥ 2.0** (`register()`-API, явный `project_root`, реальный layer-enforcement, list-of-layers). Если видишь в коде паттерны из таблицы ниже — это легаси v0.x, переписывай:

| Легаси (v0.x) | Канон (v2.x) |
|---|---|
| `injector._reg_dependency(K, v, use_serialization_function=True, nested_injections_allowed=False)` | `injector.register(key=K, value=v, inject_into=False)` |
| `app_layers = frozenset([Layer1, Layer2, ...])` | `app_layers = [Layer1, Layer2, ...]` — список, порядок важен |
| `sys.path.insert(0, apps_root)` в `bundle_project` | `DependencyInjector(..., project_root=BACKEND_ROOT)` |
| Свой `PresentationLayer` в `archtool_conf/custom_layers.py` | Импортировать из `archtool.layers.default_layers` |
| Глобальный `logging.basicConfig` от archtool в логах | По умолчанию `NullHandler`; включай локально через `ARCHTOOL_VERBOSE=1` |
| `injector._dependencies` | `injector.dependencies` (публичный атрибут) |

`_register = register` оставлен в v2.x как бэккомпат-алиас. Использовать **`register()`**.

**web_fractal**: на момент написания используем актуальную in-development версию (`Base`, `Unset`/`UNSET`, `UnitOfWork`, `serialize`, `apply_filters`, `paginate`, `Pagination`, `HttpControllerABC` с `reg_route`, `import_all_models`, `initialize_controllers_api`, `get_settings_value(s)`). API стабилизируется; если что-то из этого переименовано — следуй текущим импортам в проекте.

---

## 1. Что это за стек

**archtool** — DI и контроль слоёв. Сам сканирует модули, инстанциирует классы, подставляет зависимости через `setattr` по аннотациям. Никакого ручного wiring, никаких декораторов, никакого `__init__(self, *args)`.

**web_fractal** — батарейки поверх archtool под FastAPI + SQLAlchemy (async). Даёт:

- `Base` — declarative-база SQLAlchemy и Pydantic `Base` для DTO/DM
- `UnitOfWork` — async-контекстник сессии
- `HttpControllerABC` — базовый класс контроллера с авто-регистрацией роутов
- хелперы: `serialize`, `apply_filters`, `paginate`, `Pagination`
- `import_all_models`, `initialize_controllers_api` — для сборки приложения
- `get_settings_value(s)` — доступ к `app.config`

**Принципы:**

1. **Interface-first** — `interfaces.py` каждого модуля является спецификацией ограниченного контекста; реализации — это исполнение контракта.
2. **Bounded context на модуль** — каждый `AppModule` владеет одним доменом.
3. **DI через классовые аннотации** — зависимости объявляются как `field: SomeABC` на конкретном классе, archtool подставляет инстанс. Никаких `__init__(self, repo, …)`.
4. **Слои принудительны** — нарушение слоя ловится при `injector.inject()`, до старта.
5. **Чистый Pydantic на границах** — `DTO` на входе, `DM` на выходе, ORM-модели не покидают репозиторий/сервис.
6. **DDD-пуризм в исключениях** — репозиторий и сервис кидают доменные исключения; в `HTTPException` их превращает только контроллер.

---

## 2. Mental model archtool

### 2.1 Двухпроходная инъекция с проверкой слоёв

При вызове `injector.inject()`:

**Pass 1 — Discover & register.** Для каждого слоя archtool обходит его `ComponentPattern`-ы. Например, у `InfrastructureLayer` есть паттерн `("repos", superclass=ABCRepo)`. Для каждого `AppModule`:

1. Сканирует `<module>/interfaces.py` → находит абстрактные подклассы `ABCRepo` → собирает контракты.
2. Сканирует `<module>/repos.py` → находит неабстрактные подклассы этих контрактов → инстанциирует как `Cls()` (без аргументов).
3. Регистрирует под ключом — полным dotted-путём интерфейса (`app.<domain>.interfaces.<Domain>RepoABC` → instance).

Так же для `services.py` / `ABCService` и `controllers.py` / `ABCController`.

**Между проходами:**

- **`_check_layer_violations()`** — если `enforce_layers=True` (дефолт), проверяет граф зависимостей. Если компонент из внутреннего слоя зависит от компонента из внешнего слоя — `TopLevelLayerUsingException`, инжектор падает до Pass 2. Ручные регистрации (`register()`) пропускаются — у них нет известного слоя.
- **Топосортировка** через DFS. Если граф циклический — archtool **не падает**, выводит один `WARNING`, продолжает (в двухпроходной схеме циклы валидны: все объекты уже созданы перед `setattr`). Обычно это знак, что два класса взяли на себя слишком много.

**Pass 2 — Inject.** В топологическом порядке (deepest first) для каждого инстанса archtool читает `vars(cls).__annotations__` и для каждой аннотации, чей тип зарегистрирован, делает `setattr(instance, name, registered_instance)`. Для инстансов, зарегистрированных вручную с `inject_into=False`, второй проход пропускается.

### 2.2 Универсальный механизм ручной регистрации

`injector.register(key=K, value=instance, inject_into=True|False)` регистрирует **готовый объект** под ключом (классом). Любой потребитель с аннотацией `field: K` получит этот инстанс автоматически на Pass 2.

`async_sessionmaker`, `AsyncEngine`, `Minio`, `CentrifugoClient` — всё это просто примеры этого паттерна. Сам `session_maker` ничем не «универсален», он — обычный объект SQLAlchemy, используемый по прямому назначению. Универсален именно механизм регистрации.

**Применения:**

- pre-built клиенты (Minio, Centrifugo, httpx)
- async-ресурсы (engine, session_maker — нельзя создать в синхронном `inject()`)
- конфигурация (dataclass-обёртка, регается одним инстансом)
- моки в тестах
- условные реализации (S3 vs Local, прод vs стейджинг)

**Семантика `inject_into`:**

- `True` (дефолт) — archtool в Pass 2 также прочитает аннотации этого инстанса и заинжектит в них зависимости. Используй для собственных классов с archtool-аннотациями.
- `False` — Pass 2 пропускает этот инстанс. Используй для **сторонних объектов** (sqlalchemy, httpx, minio) — у них нет archtool-аннотаций, попытка инжекта в них ничего не сломает, но и не даст пользы; явный `False` снимает неоднозначность.

**Идемпотентность:** повторный `register(K, тот_же_инстанс)` — silent no-op. `register(K, другой_инстанс)` — `DependencyDuplicate`. Удобно для тестов и горячей переинициализации.

**Discriminator-подкласс** нужен, если в системе сосуществуют два инстанса одного базового класса (внутренний и публичный Minio-клиент):

```python
# app/core_integrations/dep_keys.py
from minio import Minio

class MinioInternalKey(Minio):
    """Discriminator для внутреннего Minio-клиента."""
    ...

class MinioPubKey(Minio):
    """Discriminator для публичного Minio-клиента."""
    ...
```

```python
# app/core_integrations/reg_deps.py
injector.register(key=MinioInternalKey, value=internal_minio, inject_into=False)
injector.register(key=MinioPubKey, value=public_minio, inject_into=False)

# потребитель
class FileRepo(FileRepoABC):
    minio: MinioInternalKey   # внутренний
    minio_pub: MinioPubKey    # публичный
```

Discriminator не нужен, если инстанс один на тип. `session_maker` один, регается просто под ключом `async_sessionmaker`.

### 2.3 Слои (стандартные)

| Слой | Файл | Маркер | Зависит от |
|---|---|---|---|
| `InfrastructureLayer` | `repos.py` | `ABCRepo` | — |
| `DomainLayer` | `services.py` | `ABCService` | Infrastructure |
| `ApplicationLayer` | `controllers.py` | `ABCController` | Domain |
| `PresentationLayer` | `views.py` | `ABCView` | Application |

`default_layers` в v2.x — это **список**, не frozenset:

```python
from archtool.layers.default_layers import (
    default_layers,        # готовый список из 4-х
    InfrastructureLayer,
    DomainLayer,
    ApplicationLayer,
    PresentationLayer,
)
```

Правило: **внутренний слой не знает о внешнем**. Сервис может зависеть от репо, контроллер — от сервиса, но не наоборот. Нарушение → `TopLevelLayerUsingException` при `inject()`.

`PresentationLayer` уже в `default_layers` начиная с v2.0 — **не переопределяй его в своём `custom_layers.py`**, просто импортируй.

---

## 3. Каркас модуля

```
app/<domain>/
├── __init__.py        — пустой
├── interfaces.py      — ABC-контракты домена (контроллеры, сервисы, репо)
├── exceptions.py      — доменные исключения (NotFound, AccessDenied, ConflictError, ...)
├── dtos.py            — Pydantic-модели ВХОДЯЩИЕ (Create/Update/Filter)
├── dms.py             — Pydantic-модели ИСХОДЯЩИЕ (response / domain models)
├── models.py          — SQLAlchemy ORM-модели
├── repos.py           — конкретные реализации репо (БД + внешние API); кидают доменные исключения
├── services.py        — конкретные реализации сервисов (бизнес-логика); кидают доменные исключения
├── controllers.py     — конкретные реализации контроллеров (HTTP-роуты); ловят доменные, кидают HTTPException
└── dependencies.py    — FastAPI Depends-хелперы (опционально)
```

### 3.1 Кому что принадлежит

| Файл | Что туда | Что НЕ туда |
|---|---|---|
| `interfaces.py` | Абстрактные классы: `<Domain>RepoABC(ABCRepo)`, `<Domain>ServiceABC(ABCService)`, `<Domain>ControllerABC(ABCController, HttpControllerABC)`. Только `@abstractmethod` + docstring. | Реализация, импорты конкретов |
| `exceptions.py` | Доменные исключения: `<Domain>NotFound`, `<Domain>AccessDenied`, `<Domain>ConflictError`, и т.д. Никакого `HTTPException`. | HTTP-коды, FastAPI-зависимости |
| `dtos.py` | `Create<Domain>DTO`, `Update<Domain>DTO`, `Filter<Domain>DTO` — то, что приходит с фронта. Наследуют `web_fractal.dtos.Base`. | Респонс-модели |
| `dms.py` | `<Domain>DM` — то, что отдаём наружу. Наследуют `web_fractal.dtos.Base`. | Реквест-модели |
| `models.py` | ORM-классы (наследуют `web_fractal.db.Base` + миксины), `relationship`, `mapped_column`. | Бизнес-логика, методы кроме property |
| `repos.py` | Доступ к БД (запросы, ownership-чеки) или к внешним API (GitHub, Stripe). Сессия — **параметром метода**, не в `self`. Кидает доменные исключения. | Бизнес-логика, HTTP-обработка, `HTTPException` |
| `services.py` | Бизнес-логика, multi-step операции, merge-логика, оркестрация репозиториев. **Только если она реально есть** — простой CRUD прямо в контроллере. Кидает доменные исключения. | I/O-операции (это репо), HTTP-форматирование (это контроллер), `HTTPException` |
| `controllers.py` | FastAPI-эндпоинты, координация репо/сервисов внутри `UnitOfWork`, сериализация в DM. **Единственное место, где доменные исключения превращаются в `HTTPException`**. | Прямые SQL-запросы (выноси в репо), бизнес-логика (выноси в сервис) |
| `dependencies.py` | FastAPI `Depends`-хелперы: `get_current_user_id`, `get_<smth>_or_404`. | Любая логика, требующая инстанса репо/сервиса (это уже не Depends) |

---

## 4. Шаблоны файлов

### 4.1 `interfaces.py`

```python
from abc import abstractmethod
from uuid import UUID
from typing import TYPE_CHECKING

from archtool.layers.default_layer_interfaces import (
    ABCController,
    ABCRepo,
    ABCService,
)
from web_fractal.http.interfaces import HttpControllerABC

from sqlalchemy.ext.asyncio import AsyncSession

from .dtos import *  # noqa: F401,F403 — намеренный re-export для use в аннотациях
from .dms import *   # noqa: F401,F403

if TYPE_CHECKING:
    from .models import <Domain>


# ------------------------------------
# Repos
# ------------------------------------
class <Domain>RepoABC(ABCRepo):
    """Доступ к данным <Domain>."""

    @abstractmethod
    async def get_<domain>_for_owner(
        self,
        session: AsyncSession,
        <domain>_id: UUID,
        owner_id: UUID,
    ) -> "<Domain>":
        """
        Возвращает <Domain> с проверкой владельца.
        Бросает <Domain>NotFound, если не найден.
        Бросает <Domain>AccessDenied, если найден, но чужой.
        """
        ...


# ------------------------------------
# Services
# ------------------------------------
class <Domain>ServiceABC(ABCService):
    """Бизнес-логика домена <Domain>. Создавать только если есть multi-step / merge / orchestration."""

    @abstractmethod
    async def <some_business_op>(
        self,
        session: AsyncSession,
        <domain>: "<Domain>",
        update_data: dict,
    ) -> "<Domain>":
        ...


# ------------------------------------
# Controllers
# ------------------------------------
class <Domain>ControllerABC(ABCController, HttpControllerABC):
    """HTTP API для <Domain>."""

    @abstractmethod
    async def create_<domain>(self, payload: Create<Domain>DTO) -> <Domain>DM: ...

    @abstractmethod
    async def find_<domain>(self, pk: UUID) -> <Domain>DM: ...

    @abstractmethod
    async def filter_<domains>(self, filters: Filter<Domain>DTO) -> list[<Domain>DM]: ...

    @abstractmethod
    async def update_<domain>(self, pk: UUID, payload: Update<Domain>DTO) -> <Domain>DM: ...

    @abstractmethod
    async def delete_<domain>(self, pk: UUID) -> None: ...
```

**Правила:**

- Сначала Repos, потом Services, потом Controllers — слои сверху вниз по зависимости.
- В контроллере всегда указывать ОБЕ базы: `(ABCController, HttpControllerABC)`. Первая — маркер слоя для archtool, вторая даёт `reg_route()` и интеграцию с FastAPI.
- Все методы async, кроме хелперов внутри сервиса/репо, которые точно sync.
- Docstring обязателен у `@abstractmethod` — это и есть твоя архдокументация (см. interface-first).
- В docstring у методов репо/сервиса перечисляются доменные исключения, которые они могут бросить.

### 4.2 `exceptions.py`

```python
from uuid import UUID


class <Domain>Error(Exception):
    """Базовое доменное исключение <Domain>."""


class <Domain>NotFound(<Domain>Error):
    def __init__(self, <domain>_id: UUID):
        self.<domain>_id = <domain>_id
        super().__init__(f"<Domain> {<domain>_id} не найден")


class <Domain>AccessDenied(<Domain>Error):
    def __init__(self, <domain>_id: UUID, owner_id: UUID):
        self.<domain>_id = <domain>_id
        self.owner_id = owner_id
        super().__init__(f"<Domain> {<domain>_id} недоступен для {owner_id}")


class <Domain>ConflictError(<Domain>Error):
    """Например, уникальный constraint."""
    def __init__(self, field: str, value: str):
        self.field = field
        self.value = value
        super().__init__(f"<Domain> с {field}={value} уже существует")


class <Domain>ValidationError(<Domain>Error):
    """Бизнес-валидация не прошла (не структура, а правила)."""
```

**Правила:**

- Все исключения наследуют от `<Domain>Error`, чтобы контроллер мог поймать одну базу при необходимости.
- В `__init__` принимаешь типизированные поля, в `super().__init__()` формируешь человекочитаемое сообщение.
- Никаких HTTP-кодов в исключениях. Это маппинг делает контроллер.
- Маппинг `domain exception → HTTP code` — это политика приложения; стандартный набор:
  - `<Domain>NotFound` → 404
  - `<Domain>AccessDenied` → 404 (чтобы не утечь существование) или 403 (если факт существования и так публичен)
  - `<Domain>ConflictError` → 409
  - `<Domain>ValidationError` → 422

### 4.3 `dtos.py`

```python
from typing import Optional
from uuid import UUID
from pydantic import EmailStr

from web_fractal.dtos import Base, Unset
from web_fractal.types import UNSET


class Create<Domain>DTO(Base):
    """Что приходит на POST /<domains>"""
    name: str
    description: Optional[str] = None
    # обязательные поля без дефолта, опциональные с None


class Update<Domain>DTO(Base):
    """Что приходит на PATCH /<domains>/{pk}. Все поля Optional."""
    name: Optional[str] = None
    description: Optional[str] = None


class Filter<Domain>DTO(Base):
    """Что приходит на POST /<domains>/filter. Фильтры через UNSET-sentinel."""
    name: Optional[str | Unset] = UNSET
    owner_id: Optional[UUID | Unset] = UNSET
```

**Правила:**

- `Base` — это `web_fractal.dtos.Base`, не голый Pydantic. Даёт `.not_blank`, конфиг и прочее.
- Для **фильтров** используется паттерн `Optional[X | Unset] = UNSET`. `UNSET` отличается от `None`: `None` означает «фильтруй по NULL», `UNSET` — «не фильтруй вообще». В контроллере вызывается `filters.not_blank` → словарь без UNSET-полей → передаётся в `apply_filters(query, Model, filters.not_blank)`.
- Для **update** обычные `Optional[X] = None` — `None` означает «не менять это поле».

### 4.4 `dms.py`

```python
from datetime import datetime
from typing import Optional
from uuid import UUID

from web_fractal.dtos import Base


class <Domain>DM(Base):
    """Респонс-модель <Domain>."""
    id: UUID
    name: str
    description: Optional[str]
    owner_id: UUID
    created_at: datetime
    updated_at: datetime


# Если домен — это иерархия (Project содержит Schema содержит Table), то DM нижнего уровня
# может включаться в DM верхнего как nested поле:
class <Domain>WithDetailsDM(<Domain>DM):
    related_items: list["<Entity>DM"] = []
```

**Правила:**

- DM — это то, что видит фронт. ORM-объект конвертируется в DM через `serialize(<Domain>DM, orm_obj, as_list=False)`.
- Не пихай в DM поля, которые не должны утечь (`password_hash`, `internal_token`). DM — это публичный API-контракт.
- Если нужны разные представления для разных эндпоинтов (`<Domain>ShortDM`, `<Domain>FullDM`) — делай несколько DM, не пытайся обойтись одним.

### 4.5 `models.py`

```python
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from web_fractal.db import Base
from app.base.models import WithDescription, WithTimestamps, FrontendMetadata

if TYPE_CHECKING:
    from app.users.models import User


class <Domain>(Base, WithDescription, WithTimestamps):
    __tablename__ = "<domains>"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String)

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    owner: Mapped["User"] = relationship(back_populates="<domains>")

    # JSON-поле с merge-логикой обновления — делать MutableDict.as_mutable
    settings: Mapped[Optional[dict[str, Any]]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
        default=dict,
    )

    __table_args__ = (
        Index("idx_<domain>_owner", "owner_id"),
    )
```

**Правила:**

- Все модели наследуют `web_fractal.db.Base` (это SQLAlchemy declarative base).
- Общие миксины — в `app/base/models.py`: `WithTimestamps` (`created_at`/`updated_at`), `WithDescription` (`description`), `FrontendMetadata` (`frontend_metadata: dict`). Подключай миксины, не дублируй поля.
- `UUID` через `uuid4` — стандарт.
- Cross-domain `relationship` через строковые ссылки и `TYPE_CHECKING`-импорт.
- `Index` через `__table_args__` — для часто-используемых FK и поисковых полей.
- Для JSON-полей, которые обновляются через `.update(...)`, обязательно `MutableDict.as_mutable(JSON)` — иначе SQLAlchemy не заметит изменение.
- ORM-модель **не выходит за пределы репо/сервиса**. В контроллере она сразу сериализуется в DM.

### 4.6 `repos.py`

```python
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .exceptions import <Domain>AccessDenied, <Domain>NotFound
from .interfaces import <Domain>RepoABC
from .models import <Domain>


class <Domain>Repo(<Domain>RepoABC):
    """Репозиторий <Domain>. Без __init__, без полей-зависимостей."""

    async def get_<domain>_for_owner(
        self,
        session: AsyncSession,
        <domain>_id: UUID,
        owner_id: UUID,
    ) -> <Domain>:
        <domain> = await session.get(<Domain>, <domain>_id)
        if <domain> is None:
            raise <Domain>NotFound(<domain>_id)
        if <domain>.owner_id != owner_id:
            raise <Domain>AccessDenied(<domain>_id, owner_id)
        return <domain>

    # Сложный запрос с join — пример для cross-domain ownership
    async def get_<entity>_for_owner(
        self,
        session: AsyncSession,
        <entity>_id: UUID,
        owner_id: UUID,
    ) -> "<Entity>":
        from .models import <Entity>
        from .exceptions import <Entity>NotFound

        stmt = (
            select(<Entity>)
            .join(<Domain>, <Entity>.<domain>_id == <Domain>.id)
            .where(<Entity>.id == <entity>_id, <Domain>.owner_id == owner_id)
        )
        <entity> = (await session.execute(stmt)).scalars().first()
        if <entity> is None:
            raise <Entity>NotFound(<entity>_id)
        return <entity>
```

**Правила:**

- **Сессия передаётся аргументом метода, а не хранится в `self`.** Контроллер контролирует транзакцию через `UnitOfWork`, репо лишь выполняет запросы.
- **Если репо нужен фабричный `session_maker` (например, чтобы открыть собственную транзакцию вне переданной)**, объяви как классовую аннотацию:
  ```python
  class <Domain>Repo(<Domain>RepoABC):
      session_maker: async_sessionmaker

      async def standalone_method(self, ...) -> ...:
          async with UnitOfWork(self.session_maker) as uow:
              session = uow.get_session()
              ...
  ```
  Это редкий кейс. Дефолт — сессия аргументом.
- **Ownership-проверки живут здесь** в виде `get_<domain>_for_owner`, кидающего `<Domain>NotFound` / `<Domain>AccessDenied`. Маппинг в HTTP-код — задача контроллера.
- **Репозиторий не знает о HTTP.** Никаких `HTTPException`, никаких импортов из FastAPI. Только доменные исключения из `exceptions.py` соседнего файла.
- Если запрос join-ит несколько доменов и не понятно, чьё это исключение — относи к тому домену, чей объект искал. `get_<entity>_for_owner` ищет `<Entity>` → кидает `<Entity>NotFound`.

**Репо для внешнего API** (GitHub, Stripe, и т.д.):

```python
import httpx

from .exceptions import <External>APIError
from .interfaces import <External>RepoABC


class <External>Repo(<External>RepoABC):
    """Репозиторий-обёртка над внешним API."""

    BASE_URL = "https://api.example.com"

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    async def fetch_something(self, token: str, resource_id: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/resource/{resource_id}",
                    headers=self._headers(token),
                )
        except httpx.HTTPError as exc:
            raise <External>APIError(f"Сетевая ошибка: {exc}") from exc

        if response.status_code != 200:
            raise <External>APIError(
                f"API вернул {response.status_code}: {response.text[:200]}"
            )
        return response.json()
```

Внешний-API-репо живёт в `repos.py` вместе с БД-репо. Если их много и хочется отделить — заведи кастомный слой `IntegrationsLayer` с файлом `clients.py` и маркером `ABCClient` (см. раздел про кастомные слои).

### 4.7 `services.py`

```python
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .exceptions import <Domain>ValidationError
from .interfaces import <Domain>RepoABC, <Domain>ServiceABC
from .models import <Domain>


class <Domain>Service(<Domain>ServiceABC):
    """
    Сервис создаётся, КОГДА В ДОМЕНЕ ЕСТЬ ЧТО-ТО СЛОЖНЕЕ ПРОСТОГО CRUD:
    - merge-логика для JSON-полей
    - multi-step операции с откатом
    - оркестрация нескольких репо
    - валидации, требующие нескольких запросов
    """

    <domain>_repo: <Domain>RepoABC

    async def update_<domain>_with_merge(
        self,
        session: AsyncSession,
        <domain>: <Domain>,
        update_data: dict,
    ) -> <Domain>:
        # Особая обработка JSON-поля: merge, а не replace
        if "settings" in update_data and update_data["settings"] is not None:
            if <domain>.settings is None:
                <domain>.settings = {}
            <domain>.settings.update(update_data["settings"])
            del update_data["settings"]

        for key, val in update_data.items():
            if val is not None:
                setattr(<domain>, key, val)

        session.add(<domain>)
        return <domain>

    async def transfer_ownership(
        self,
        session: AsyncSession,
        <domain>: <Domain>,
        new_owner_id: UUID,
    ) -> <Domain>:
        if <domain>.owner_id == new_owner_id:
            raise <Domain>ValidationError("Новый владелец совпадает с текущим")
        <domain>.owner_id = new_owner_id
        session.add(<domain>)
        return <domain>
```

**Правила:**

- **Не плоди пустые сервисы.** Если в домене нет ничего, кроме CRUD, нет нужды в `services.py` с одним «прокидывающим» сервисом. Контроллер вызывает репо напрямую.
- Зависимости через аннотации, как везде: `<domain>_repo: <Domain>RepoABC`.
- Сессия — аргументом метода, как в репо.
- Сервис может зависеть от **нескольких репо** (своего и чужого):
  ```python
  class OrderService(OrderServiceABC):
      order_repo: OrderRepoABC
      user_repo: UserRepoABC  # cross-domain
  ```
- Сервис **не возвращает `HTTPException`** — это уровень контроллера. Сервис кидает доменные исключения из своего `exceptions.py`.

### 4.8 `controllers.py`

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from web_fractal.db import (
    UnitOfWork,
    async_sessionmaker,
    serialize,
    apply_filters,
    paginate,
    Pagination,
)

from app.users.dependencies import get_current_user_id

from .dtos import (
    Create<Domain>DTO,
    Update<Domain>DTO,
    Filter<Domain>DTO,
)
from .dms import <Domain>DM
from .exceptions import (
    <Domain>AccessDenied,
    <Domain>ConflictError,
    <Domain>NotFound,
    <Domain>ValidationError,
)
from .interfaces import <Domain>ControllerABC, <Domain>RepoABC, <Domain>ServiceABC
from .models import <Domain>


class <Domain>Controller(<Domain>ControllerABC):
    router = APIRouter(prefix="/<domains>", tags=["<domains>"])
    session_maker: async_sessionmaker
    <domain>_repo: <Domain>RepoABC
    <domain>_service: <Domain>ServiceABC  # только если он есть

    def init_http_routes(self) -> None:
        self.reg_route(self.create_<domain>, methods=["POST"])
        self.reg_route(self.find_<domain>, methods=["GET"])
        self.reg_route(self.filter_<domains>, methods=["POST"])
        self.reg_route(self.update_<domain>, methods=["PATCH"])
        self.reg_route(self.delete_<domain>, methods=["DELETE"])

    # ------------------------------------------------------------------
    # Mapping доменных исключений на HTTP-коды — единственное место в коде,
    # где это происходит. Каждый эндпоинт оборачивает свой блок логики.
    # ------------------------------------------------------------------

    async def create_<domain>(
        self,
        payload: Create<Domain>DTO,
        current_user_id: UUID = Depends(get_current_user_id),
    ) -> <Domain>DM:
        async with UnitOfWork(self.session_maker) as uow:
            session = uow.get_session()
            try:
                <domain> = <Domain>(**payload.model_dump(), owner_id=current_user_id)
                session.add(<domain>)
                await session.commit()
                await session.refresh(<domain>)
            except <Domain>ConflictError as exc:
                raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
            except <Domain>ValidationError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
            return serialize(<Domain>DM, <domain>, as_list=False)

    async def find_<domain>(
        self,
        pk: UUID,
        current_user_id: UUID = Depends(get_current_user_id),
    ) -> <Domain>DM:
        async with UnitOfWork(self.session_maker) as uow:
            session = uow.get_session()
            try:
                <domain> = await self.<domain>_repo.get_<domain>_for_owner(
                    session, pk, current_user_id
                )
            except (<Domain>NotFound, <Domain>AccessDenied):
                # 404 в обоих случаях — не утекаем факт существования чужого объекта
                raise HTTPException(status.HTTP_404_NOT_FOUND, "<Domain> не найден")
            return serialize(<Domain>DM, <domain>, as_list=False)

    async def filter_<domains>(
        self,
        filters: Filter<Domain>DTO,
        pag: Pagination = Depends(),
        current_user_id: UUID = Depends(get_current_user_id),
    ) -> list[<Domain>DM]:
        async with UnitOfWork(self.session_maker) as uow:
            session = uow.get_session()
            filters_data = filters.not_blank
            filters_data["owner_id"] = current_user_id  # ownership через фильтр

            q = select(<Domain>)
            q = apply_filters(q, <Domain>, filters_data)
            q = paginate(q, pag)

            results = (await session.execute(q)).scalars().all()
            return serialize(<Domain>DM, results, as_list=True)

    async def update_<domain>(
        self,
        pk: UUID,
        payload: Update<Domain>DTO,
        current_user_id: UUID = Depends(get_current_user_id),
    ) -> <Domain>DM:
        async with UnitOfWork(self.session_maker) as uow:
            session = uow.get_session()
            try:
                <domain> = await self.<domain>_repo.get_<domain>_for_owner(
                    session, pk, current_user_id
                )
                # Если есть merge-логика — делегируй сервису.
                # Если простой setattr — делай прямо тут без сервиса.
                <domain> = await self.<domain>_service.update_<domain>_with_merge(
                    session, <domain>, payload.model_dump()
                )
                await session.commit()
                await session.refresh(<domain>)
            except (<Domain>NotFound, <Domain>AccessDenied):
                raise HTTPException(status.HTTP_404_NOT_FOUND, "<Domain> не найден")
            except <Domain>ValidationError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
            return serialize(<Domain>DM, <domain>, as_list=False)

    async def delete_<domain>(
        self,
        pk: UUID,
        current_user_id: UUID = Depends(get_current_user_id),
    ) -> None:
        async with UnitOfWork(self.session_maker) as uow:
            session = uow.get_session()
            try:
                <domain> = await self.<domain>_repo.get_<domain>_for_owner(
                    session, pk, current_user_id
                )
            except (<Domain>NotFound, <Domain>AccessDenied):
                raise HTTPException(status.HTTP_404_NOT_FOUND, "<Domain> не найден")
            await session.delete(<domain>)
            await session.commit()
```

**Правила:**

- `router = APIRouter(prefix="/<domains>", tags=["<domains>"])` как **поле класса**.
- `session_maker: async_sessionmaker` — обязательная аннотация в любом контроллере, который работает с БД.
- Зависимости-репо/сервисы — классовые аннотации, как везде.
- `init_http_routes` — метод из `HttpControllerABC`, регистрирует роуты. `self.reg_route(self.method_name, methods=[...])` авто-выводит path из имени метода (`create_<domain>` → `POST /create_<domain>`). Чтобы задать кастомный path — `path="/me/tokens"`.
- Каждый эндпоинт открывает свой `UnitOfWork(self.session_maker)`. Не пытайся переиспользовать сессию между эндпоинтами.
- Авторизация через `current_user_id: UUID = Depends(get_current_user_id)` — стандартный паттерн.
- **`HTTPException` рождается только в контроллере.** В `try/except` ловишь доменные исключения, конвертируешь в нужный HTTP-код. Если в эндпоинте нет ни одного `except <Domain>Error` — либо ты что-то забыл, либо это редкий случай чистого insert/update без проверок.
- Сериализация в DM — последняя строка эндпоинта, всегда через `serialize(DM, obj, as_list=False|True)`.

**Помощник, чтобы не дублировать try/except в каждом методе** (опционально):

```python
# app/<domain>/controllers.py — наверху файла или в base
from contextlib import asynccontextmanager
from fastapi import HTTPException, status
from .exceptions import <Domain>AccessDenied, <Domain>ConflictError, <Domain>NotFound, <Domain>ValidationError


@asynccontextmanager
async def map_<domain>_errors():
    """Конвертирует доменные исключения в HTTPException."""
    try:
        yield
    except (<Domain>NotFound, <Domain>AccessDenied):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "<Domain> не найден")
    except <Domain>ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except <Domain>ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


# использование
async def find_<domain>(self, pk, current_user_id=Depends(get_current_user_id)):
    async with UnitOfWork(self.session_maker) as uow, map_<domain>_errors():
        session = uow.get_session()
        <domain> = await self.<domain>_repo.get_<domain>_for_owner(session, pk, current_user_id)
        return serialize(<Domain>DM, <domain>, as_list=False)
```

Когда маппингов мало (1-2 типа исключений) — оставь явный try/except. Когда их становится много и они повторяются во всех эндпоинтах домена — выноси в `map_<domain>_errors()` помощник.

### 4.9 `dependencies.py` (опционально)

```python
from uuid import UUID

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import JWT_ALGORITHM, JWT_SECRET_KEY


security = HTTPBearer()


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> UUID:
    """Достаёт user_id из JWT в заголовке Authorization."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
        subject = payload.get("sub")
        if not subject:
            raise ValueError("missing subject")
        return UUID(subject)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен",
        )
```

**Когда нужен файл:**

- FastAPI-`Depends`-функции, которые надо переиспользовать.
- Конвертация сырых query/header параметров в типизированные объекты.

**Когда НЕ нужен:**

- Если хелпер требует инстанса репо/сервиса — это уже не `Depends`, выноси в сервис.

---

## 5. Ручная регистрация инстансов через `register()`

Авто-обнаружение работает для классов с конвенцией `<file>.py + <Marker>ABC + наследник`. Всё остальное регается вручную **до** `injector.inject()`.

### 5.1 Когда нужна ручная регистрация

- pre-built клиенты сторонних сервисов: Minio, Centrifugo, httpx
- async-ресурсы: `AsyncEngine`, `async_sessionmaker` (нельзя создать внутри синхронного `inject()`)
- конфиг-объекты (если хочешь типизированный config-DI вместо `from app.config import X`)
- моки в тестах

### 5.2 Шаблон ручной регистрации

Файлы стандартизированы в модуле `app/core_integrations/`:

**`app/core_integrations/dep_keys.py`** — discriminator-классы:

```python
from minio import Minio


class MinioInternalKey(Minio):
    """Discriminator для внутреннего Minio-клиента."""
    ...


class MinioPubKey(Minio):
    """Discriminator для публичного Minio-клиента."""
    ...
```

Discriminator нужен, если два инстанса одного типа сосуществуют. Если инстанс один — discriminator не нужен (см. `async_sessionmaker`).

**`app/core_integrations/reg_deps.py`** — функция регистрации:

```python
from archtool.dependency_injector import DependencyInjector
from minio import Minio

from web_fractal.utils import get_settings_values

from .dep_keys import MinioInternalKey, MinioPubKey


def reg_deps(injector: DependencyInjector) -> None:
    """Регистрирует pre-built клиенты в инжекторе ДО inject()."""
    (
        ENABLE_MINIO,
        MINIO_HOST,
        MINIO_PUBLIC_HOST,
        MINIO_PORT,
        MINIO_USER,
        MINIO_PASSWORD,
    ) = get_settings_values([
        "ENABLE_MINIO",
        "MINIO_HOST",
        "MINIO_PUBLIC_HOST",
        "MINIO_PORT",
        "MINIO_USER",
        "MINIO_PASSWORD",
    ])

    if ENABLE_MINIO:
        internal = Minio(f"{MINIO_HOST}:{MINIO_PORT}",
                         access_key=MINIO_USER, secret_key=MINIO_PASSWORD, secure=False)
        public = Minio(f"{MINIO_PUBLIC_HOST}:{MINIO_PORT}",
                       access_key=MINIO_USER, secret_key=MINIO_PASSWORD, secure=False)

        injector.register(key=MinioInternalKey, value=internal, inject_into=False)
        injector.register(key=MinioPubKey, value=public, inject_into=False)
```

**`app/archtool_conf/bundle_project.py`** — вызов из сборки:

```python
def init_deps(injector: DependencyInjector) -> AsyncEngine:
    engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI_ASYNC,
                                 echo=False, poolclass=NullPool)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession,
                                       expire_on_commit=False)

    # Async-ресурсы. inject_into=False — это sqlalchemy-объекты, без archtool-аннотаций.
    injector.register(key=AsyncEngine, value=engine, inject_into=False)
    injector.register(key=async_sessionmaker, value=session_maker, inject_into=False)

    # Pre-built клиенты
    reg_deps(injector)
    return engine
```

**Правила:**

- Сторонние объекты — `inject_into=False`. Свои классы с archtool-аннотациями — `inject_into=True` (или опусти, дефолт).
- Имя метода — **`register()`** (не `_register`, не `_reg_dependency`). `_register` — бэккомпат-алиас в v2.x, существует, но публичное имя в коде смотрится чище.
- Параметра `use_serialization_function` больше нет — archtool в v2.x всегда сериализует ключ через `serialize_dep_key`. Если ты видишь его в коде — это легаси v0.x.

### 5.3 Использование зарегистрированных инстансов

В любом классе, который archtool инстанциирует, добавь аннотацию того же типа, под которым инстанс зарегистрирован:

```python
class FileRepo(FileRepoABC):
    minio: MinioInternalKey            # внутренний инстанс
    minio_pub: MinioPubKey             # публичный инстанс
    session_maker: async_sessionmaker  # просто sqlalchemy-объект, заинжекчен

    async def upload(self, ...) -> str:
        # используем minio/session_maker как обычно — это нормальные объекты
        ...
```

### 5.4 Подмена реализации в тестах

`register()` идемпотентен по `(key, тот_же_value)`. Регистрация перед `inject()` отменяет авто-обнаружение для этого ключа — archtool увидит, что ключ занят, и не пойдёт сканировать реализацию:

```python
def test_<domain>_logic():
    injector = DependencyInjector(
        modules_list=[AppModule("app.<domain>")],
        project_root=PROJECT_ROOT,
    )
    stub_repo = Stub<Domain>Repo(returns=[...])
    injector.register(key=<Domain>RepoABC, value=stub_repo)  # отменит авто-discovery
    injector.inject()

    svc = injector.get_dependency(<Domain>ServiceABC)
    # ... assertions ...
```

---

## 6. Кастомные слои

`PresentationLayer` теперь в `default_layers` — **не определяй его заново**. Кастомные слои нужны для других случаев.

### 6.1 Когда заводить новый слой

- API-клиенты сторонних сервисов хочется отделить от БД-репо (`clients.py` + `ABCClient`).
- Адаптеры очередей, фоновых воркеров, и т.п.

### 6.2 Шаблон

`app/archtool_conf/custom_layers.py`:

```python
from abc import ABC

from archtool.components.default_component import ComponentPattern
from archtool.global_types import AppModule
from archtool.layers import Layer
from archtool.layers.default_layers import (
    ApplicationLayer,
    DomainLayer,
    InfrastructureLayer,
    PresentationLayer,  # импортируем готовый, не переопределяем
)


# ----- Свой маркер -----
class ABCClient(ABC):
    """Маркер для API-клиентов сторонних сервисов."""
    ...


# ----- Свой слой -----
class IntegrationsLayer(Layer):
    """Слой интеграций: API-клиенты живут отдельно от БД-репо."""
    depends_on = InfrastructureLayer

    class Components:
        clients = ComponentPattern(
            module_name_regex="clients",
            superclass=ABCClient,
        )


# ----- Финальный список слоёв -----
# Список (не frozenset). Порядок: outermost → innermost.
app_layers: list[type[Layer]] = [
    PresentationLayer,
    ApplicationLayer,
    DomainLayer,
    IntegrationsLayer,
    InfrastructureLayer,
]


# ----- Список модулей (актуализировать при добавлении домена) -----
APPS: list[AppModule] = [
    AppModule("app.core_integrations"),
    AppModule("app.<domain1>"),
    AppModule("app.<domain2>"),
    # ...
]
```

### 6.3 Использование

В модуле, где появляется `clients.py`:

```python
# app/<domain>/interfaces.py
from archtool.layers.default_layer_interfaces import ABCRepo

from app.archtool_conf.custom_layers import ABCClient


class <External>ClientABC(ABCClient):
    @abstractmethod
    async def call_api(self, ...) -> dict: ...


class <Domain>RepoABC(ABCRepo):
    ...
```

```python
# app/<domain>/clients.py
class <External>Client(<External>ClientABC):
    async def call_api(self, ...) -> dict:
        ...
```

```python
# app/<domain>/services.py — может зависеть и от репо, и от клиента
class <Domain>Service(<Domain>ServiceABC):
    <domain>_repo: <Domain>RepoABC
    external_client: <External>ClientABC
```

Если в каком-то модуле `clients.py` нет, отключи слой для этого модуля:

```python
AppModule("app.users", ignore=[IntegrationsLayer.Components.clients])
```

---

## 7. web_fractal cheatsheet

### 7.1 Базы

```python
from web_fractal.dtos import Base, Unset          # Pydantic-база с .not_blank
from web_fractal.types import UNSET               # sentinel «не фильтровать»
from web_fractal.db import Base                   # SQLAlchemy declarative base
from web_fractal.db import async_sessionmaker, AsyncSession  # re-export
```

### 7.2 UnitOfWork и сессия

```python
from web_fractal.db import UnitOfWork

async def my_method(self, ...) -> ...:
    async with UnitOfWork(self.session_maker) as uow:
        session = uow.get_session()
        # ... запросы ...
        await session.commit()  # явный commit
        return ...
```

`UnitOfWork.__aexit__` коммитит на выходе, если был успех, и откатывает, если было исключение. Но принято делать **явный `await session.commit()`** перед выходом — это позволяет ловить и обрабатывать commit-ошибки в той же транзакции.

### 7.3 Сериализация ORM → DM

```python
from web_fractal.db import serialize

obj = await session.get(<Domain>, pk)
dm = serialize(<Domain>DM, obj, as_list=False)

results = (await session.execute(query)).scalars().all()
dms = serialize(<Domain>DM, results, as_list=True)
```

### 7.4 Фильтры и пагинация

```python
from web_fractal.db import apply_filters, paginate, Pagination
from fastapi import Depends

async def filter_<domains>(
    self,
    filters: Filter<Domain>DTO,
    pag: Pagination = Depends(),  # автоматический пагинатор
    current_user_id: UUID = Depends(get_current_user_id),
) -> list[<Domain>DM]:
    async with UnitOfWork(self.session_maker) as uow:
        session = uow.get_session()
        filters_data = filters.not_blank          # убираем UNSET
        filters_data["owner_id"] = current_user_id  # ownership через фильтр

        q = select(<Domain>)
        q = apply_filters(q, <Domain>, filters_data)
        q = paginate(q, pag)

        results = (await session.execute(q)).scalars().all()
        return serialize(<Domain>DM, results, as_list=True)
```

### 7.5 HttpControllerABC: контракт HTTP-контроллера

Чтобы archtool + web_fractal увидели класс как HTTP-ручку и подключили его к FastAPI, нужны **три обязательных условия**:

**1. Интерфейс контроллера наследует обе базы:**

```python
# app/<domain>/interfaces.py
from archtool.layers.default_layer_interfaces import ABCController
from web_fractal.http.interfaces import HttpControllerABC

class <Domain>ControllerABC(ABCController, HttpControllerABC):
    ...
```

- `ABCController` — маркер слоя `ApplicationLayer` для archtool. Без него класс не попадёт в DI-сборку.
- `HttpControllerABC` — миксин web_fractal, даёт метод `reg_route()` и контракт `init_http_routes()`. Без него `initialize_controllers_api()` пропустит контроллер.

Если контроллер не экспоузит HTTP (используется только внутренне) — наследуй только `ABCController`. Это редкий случай; обычно если не HTTP, то это сервис.

**2. Конкретный контроллер задаёт `router` как поле класса:**

```python
# app/<domain>/controllers.py
from fastapi import APIRouter

class <Domain>Controller(<Domain>ControllerABC):
    router = APIRouter(prefix="/<domains>", tags=["<domains>"])
    ...
```

`router` — обязательное поле. Без него `initialize_controllers_api()` не сможет подключить роуты к FastAPI-приложению.

- `prefix` — относительный путь домена; глобальный `API_PREFIX` (обычно `/api`) добавляется при подключении.
- `tags` — для Swagger UI; используй имя домена.

**3. Метод `init_http_routes(self)` регистрирует все методы контроллера как FastAPI-эндпоинты:**

```python
def init_http_routes(self) -> None:
    self.reg_route(self.create_<domain>, methods=["POST"])
    self.reg_route(self.find_<domain>, methods=["GET"])
    self.reg_route(self.update_<domain>, methods=["PATCH"])
    self.reg_route(self.delete_<domain>, methods=["DELETE"])
    self.reg_route(self.update_my_token, methods=["PATCH"], path="/me/token")  # кастомный path
```

`reg_route(self.method, methods=[...], path=None)` подвешивает метод на `self.router`. Если `path` не задан — берётся имя метода (`create_<domain>` → `/create_<domain>`). Финальный URL: `{global_API_PREFIX}{router.prefix}{path}`.

**Что делает `initialize_controllers_api`:**

`initialize_controllers_api(injector, app)` в `bundle_project.bundle()` сам обходит все найденные контроллеры в инжекторе, вызывает у каждого `init_http_routes()` и подключает их `router` к FastAPI с глобальным `API_PREFIX`. Тебе не нужно делать `app.include_router(...)` вручную — это автоматизировано.

### 7.6 Настройки

```python
from web_fractal.utils import get_settings_value, get_settings_values

ENABLE_X = get_settings_value("ENABLE_X")  # читает app.config.ENABLE_X
(A, B, C) = get_settings_values(["A", "B", "C"])  # batch
```

Используется на верхнем уровне модулей, где надо условно инициализировать (например, ставить мок-реп, если фича выключена):

```python
# repos.py
ENABLE_OPENOBSERVE = get_settings_value("ENABLE_OPENOBSERVE")

if ENABLE_OPENOBSERVE:
    class LoggerRepo(LoggerRepoABC):
        ...
else:
    class LoggerRepoMock(LoggerRepoABC):
        async def log(self, ...): ...
```

archtool возьмёт ту реализацию, которая видна в модуле в данный запуск.

---

## 8. Рецепты

### 8.1 Новый проект с нуля

```bash
archtool init <project-name>
cd <project-name>
pip install -e ".[dev]"
make test
```

Создаёт каркас с `entrypoints/run.py`, `tests/test_assembly.py`, `Makefile`, `Dockerfile`, `pyproject.toml`. Затем добавляешь web_fractal-специфику в `bundle_project.py` (см. раздел 12).

### 8.2 Новый домен в существующем проекте

1. **Скаффолд через CLI:**
   ```bash
   archtool add-module <domain>
   ```
   Создаст `app/<domain>/` с заглушками `interfaces.py`, `services.py`, `repos.py` и `tests/`.

2. **Допиши недостающие файлы** под web_fractal-стиль: `dtos.py`, `dms.py`, `models.py`, `exceptions.py`, `controllers.py`, (опционально `dependencies.py`).

3. **Заполни `interfaces.py` ПЕРВЫМ.** Это твоя архитектурная спецификация — какие методы будут у репо/сервиса/контроллера. Реализация пишется под контракт, а не наоборот.

4. **Зарегистрируй модуль в `APPS`:**
   ```python
   # app/archtool_conf/custom_layers.py
   APPS: list[AppModule] = [
       # ...
       AppModule("app.<domain>"),
   ]
   ```

5. **Если у домена есть ORM-модели** — убедись, что они импортируются. `web_fractal.import_all_models(Base)` делает это автоматически на старте, но `models.py` должен быть в `app/<domain>/`.

6. **Прогоняй сборку:**
   ```bash
   archtool validate                                        # проверка структуры модулей
   ARCHTOOL_VERBOSE=1 python entrypoints/run.py             # подробный лог DI
   ```

7. **Тест сборки** (создаётся `archtool init`, но стоит проверить):
   ```python
   # tests/test_assembly.py
   def test_di_assembles():
       from app.archtool_conf.bundle_project import bundle
       from fastapi import FastAPI
       bundle(FastAPI())   # бросает исключение при любой ошибке разводки
   ```

### 8.3 Новый эндпоинт в существующем домене

1. **Добавь абстрактный метод в `<Domain>ControllerABC`:**
   ```python
   @abstractmethod
   async def export_<domain>(self, pk: UUID, format: str) -> ExportResultDM: ...
   ```

2. **Добавь DTO/DM, если нужно** (если параметры — query/path, DTO не нужен; если тело JSON — нужен).

3. **Реализуй в `<Domain>Controller`:**
   ```python
   async def export_<domain>(
       self,
       pk: UUID,
       format: str,
       current_user_id: UUID = Depends(get_current_user_id),
   ) -> ExportResultDM:
       async with UnitOfWork(self.session_maker) as uow:
           session = uow.get_session()
           try:
               <domain> = await self.<domain>_repo.get_<domain>_for_owner(session, pk, current_user_id)
           except (<Domain>NotFound, <Domain>AccessDenied):
               raise HTTPException(404, "<Domain> не найден")
           # ... логика экспорта (вынести в сервис, если нетривиальна) ...
           return ExportResultDM(...)
   ```

4. **Зарегистрируй роут в `init_http_routes`:**
   ```python
   self.reg_route(self.export_<domain>, methods=["GET"], path="/{pk}/export")
   ```

### 8.4 Новый метод репо

1. **Добавь `@abstractmethod` в `<Domain>RepoABC`** в `interfaces.py`, в docstring перечисли возможные доменные исключения.
2. **Если нужны новые исключения** — добавь их в `exceptions.py`.
3. **Реализуй в `<Domain>Repo`** в `repos.py`. Сессия — параметром.
4. Контроллер использует через классовую аннотацию: `<domain>_repo: <Domain>RepoABC`, оборачивает в нужный `except`.

### 8.5 Новый сервис в домене, где сервиса не было

1. **Создай `<Domain>ServiceABC(ABCService)` в `interfaces.py`** с конкретными методами (не пустой!).
2. **Создай `<Domain>Service(<Domain>ServiceABC)` в `services.py`.** Зависимости — классовые аннотации.
3. **Контроллер: добавь аннотацию** `<domain>_service: <Domain>ServiceABC`.
4. Если до этого не было `services.py` — создай его, archtool автоматически подцепит.

### 8.6 Cross-domain зависимость

Сервис из `orders` нужен из `payments`?

```python
# app/payments/services.py
from app.orders.interfaces import OrderServiceABC

class PaymentService(PaymentServiceABC):
    payment_repo: PaymentRepoABC
    order_service: OrderServiceABC   # cross-module — archtool разрешит сам
```

Никакого `from app.orders.services import OrderService` — это нарушение слоя (контракт-vs-конкрет). Импортируешь только интерфейс.

Доменные исключения из `app.orders.exceptions` тоже можно импортировать в `app.payments.services` — это нормально, исключения часть публичного API ограниченного контекста.

### 8.7 Интеграция со сторонним сервисом (новый клиент)

**Вариант А — клиент как обычный репо в `repos.py`:**

Подходит, если клиент простой (один-два метода).

```python
# app/<domain>/repos.py
class <External>Repo(<External>RepoABC):
    async def fetch(self, token: str, ...) -> dict:
        async with httpx.AsyncClient() as client:
            ...
```

**Вариант Б — отдельный слой `IntegrationsLayer`:**

Подходит, если клиентов много и хочется отделить от БД-репо. См. раздел про кастомные слои.

**Вариант В — pre-built клиент (Minio, Centrifugo):**

Если клиент — не «класс с пустым `__init__`», а сложный объект (требует connection string, async-инициализации):

1. Добавь discriminator в `core_integrations/dep_keys.py` (если нужно различать несколько инстансов).
2. Зарегистрируй в `core_integrations/reg_deps.py` через `injector.register(key=Key, value=instance, inject_into=False)`.
3. Используй через классовую аннотацию: `client: Key`.

### 8.8 Условные реализации (фича включена/выключена)

```python
# repos.py
ENABLE_X = get_settings_value("ENABLE_X")

if ENABLE_X:
    class XRepo(XRepoABC):
        async def do_x(self): ...  # реальная реализация
else:
    class XRepoMock(XRepoABC):
        async def do_x(self): ...  # no-op
```

archtool возьмёт ту реализацию, которая определена в модуле в данный запуск.

### 8.9 Тест с моком

```python
# tests/test_<domain>_service.py
def test_<domain>_logic():
    from archtool.dependency_injector import DependencyInjector
    from archtool.global_types import AppModule

    injector = DependencyInjector(
        modules_list=[AppModule("app.<domain>")],
        project_root=PROJECT_ROOT,
    )

    stub_repo = Stub<Domain>Repo(returns=[...])
    injector.register(key=<Domain>RepoABC, value=stub_repo)

    injector.inject()
    svc = injector.get_dependency(<Domain>ServiceABC)
    # ... assertions ...
```

Ручная регистрация переопределяет авто-обнаружение — `inject()` не будет создавать настоящий `<Domain>Repo`, потому что ключ `<Domain>RepoABC` уже занят моком.

---

## 9. archtool CLI

```bash
archtool init <project-name>       # скаффолд нового проекта (Makefile, Dockerfile, entrypoints/run.py, tests/test_assembly.py)
archtool add-module <name>         # новый домен с заглушками interfaces/services/repos + tests/
archtool validate                  # проверка структуры всех модулей из APPS
archtool graph                     # граф зависимостей в виде дерева
archtool graph --format dot | dot -Tpng -o deps.png   # экспорт в GraphViz
ARCHTOOL_VERBOSE=1 python entrypoints/run.py          # подробный лог сборки DI
```

`archtool validate` бежит по каждому `AppModule` из конфига и проверяет, что `interfaces.py` есть и модуль импортируется. Запускать после `add-module` и перед коммитом.

`archtool graph` — для аудита того, что вышло. Удобно показывать в PR-ревью.

`ARCHTOOL_VERBOSE=1` — единственный способ включить debug-логирование инжектора без правки кода. Альтернатива — `DependencyInjector(..., verbose=True)`. По умолчанию archtool молчит (`NullHandler`), не мусорит в твои логи.

---

## 10. Анти-паттерны (НЕ делать)

1. **`__init__(self, ...)` на DI-классах.** archtool инстанциирует как `Cls()`. Если нужна init-логика — вынеси в фабричный метод и зови вручную, либо используй `injector.register()` с готовым инстансом.

2. **Импорт конкретного класса из чужого модуля.** Только интерфейсы:
   ```python
   # ❌ Нарушение слоя
   from app.users.services import UserService
   # ✅ Через контракт
   from app.users.interfaces import UserServiceABC
   ```

3. **Бизнес-логика в контроллере.** Контроллер — только координация `UnitOfWork`, вызовы репо/сервиса, сериализация, маппинг доменных исключений в HTTP. Если в эндпоинте >20 строк логики — выноси в сервис.

4. **Сырой SQL в контроллере.** Запросы — в репо. Контроллер только зовёт репо-метод.

5. **`HTTPException` из репо или сервиса.** Репо и сервис кидают доменные исключения из `exceptions.py`. Контроллер ловит их и маппит в `HTTPException`. Это единственное правильное направление потока.

6. **DM в реквесте, DTO в респонсе.** DTO — входящий, DM — исходящий. Не путать.

7. **ORM-модель в респонсе.** Всегда `serialize(<Domain>DM, obj)`.

8. **Хранить сессию в `self`.** Сессия — параметр метода (репо/сервис) либо `UnitOfWork(self.session_maker)` (контроллер).

9. **Пустой сервис, который только «прокидывает» вызов в репо.** Если бизнес-логики нет — контроллер зовёт репо напрямую.

10. **Забыть зарегистрировать модуль в `APPS`.** Самая частая ошибка после `add-module`. `archtool validate` ловит.

11. **Создавать `clients.py` без кастомного слоя.** Если у тебя файл `clients.py` с маркером `ABCClient`, в `custom_layers.py` должен быть `IntegrationsLayer` с соответствующим `ComponentPattern`. Иначе archtool их не увидит.

12. **HTTP-контроллер без `router` как поля класса.** `router = APIRouter(prefix=..., tags=[...])` — обязательное поле. Без него `initialize_controllers_api()` не сможет подключить эндпоинты к FastAPI, и роуты не появятся в OpenAPI/Swagger.

13. **Интерфейс HTTP-контроллера без `HttpControllerABC`.** Если контроллер экспоузит HTTP, его абстрактный класс должен наследовать **обе** базы: `(ABCController, HttpControllerABC)`. Только `ABCController` — archtool увидит класс как Application-слой, но `initialize_controllers_api()` пропустит, потому что у него не будет `init_http_routes()` / `reg_route()`. Только `HttpControllerABC` — archtool не подцепит класс в DI-сборку, потому что нет маркера слоя.

14. **`Optional[X] = None` для фильтров вместо `Optional[X | Unset] = UNSET`.** Фильтр с `None` означает «WHERE x IS NULL», не «не фильтровать». Используй `UNSET` + `.not_blank`.

15. **Mutable JSON-поле без `MutableDict.as_mutable(JSON)`.** `dict.update()` на таком поле не зафиксируется в БД.

### Анти-паттерны легаси v0.x (не использовать в новом коде)

16. **`injector._reg_dependency(K, v, use_serialization_function=True, nested_injections_allowed=False)`** — приватный API v0.x, удалён в v2.x в пользу публичного `register(key=K, value=v, inject_into=False)`.

17. **`app_layers = frozenset([...])`** — в v2.x порядок слоёв важен (документировано в исходниках `default_layers`). Используй обычный `list`.

18. **`sys.path.insert(0, ...)` в `bundle_project.py` / `entrypoints/run.py`** — заменено явным `DependencyInjector(..., project_root=BACKEND_ROOT)`. archtool сам находит корень по маркер-файлам, либо ты передаёшь его явно.

19. **Самописный `class PresentationLayer(Layer): ...`** — в v2.x он в `default_layers`, импортируй из `archtool.layers.default_layers`. Старая версия в v0.2.0 имела баг `depends_on = ApplicationLayer or DomainLayer` (Python-выражение `or`, всегда `ApplicationLayer`).

20. **Глобальный `logging.basicConfig(level=DEBUG)` от archtool в логах хост-приложения** — в v0.2.0 archtool делал это в `dependency_injector.py` модульно. В v2.x — `NullHandler` по умолчанию. Если видишь, что archtool заливает твои логи дебагом, значит зависимость старая.

---

## 11. Чек-лист «домен готов»

- [ ] `interfaces.py` с docstring у каждого `@abstractmethod`; перечислены возможные доменные исключения
- [ ] `exceptions.py` с базовым `<Domain>Error` и наследниками (`NotFound`, `AccessDenied`, `ConflictError`, `ValidationError` по необходимости)
- [ ] `dtos.py`: Create / Update / Filter; фильтры через `Unset`/`UNSET`
- [ ] `dms.py`: респонс-модели; никаких приватных полей (`password_hash` и т.п.)
- [ ] `models.py`: миксины подключены, индексы на FK, JSON-поля через `MutableDict.as_mutable(JSON)` если ожидается merge
- [ ] `repos.py`: `get_<domain>_for_owner` для ownership; сессия — параметром; кидает доменные исключения, **не** `HTTPException`
- [ ] `services.py`: создан только если есть нетривиальная логика; кидает доменные исключения, **не** `HTTPException`
- [ ] `controllers.py`: `router = APIRouter(prefix=..., tags=[...])` как поле класса; интерфейс контроллера наследует **обе** базы `(ABCController, HttpControllerABC)`; все методы зарегистрированы в `init_http_routes`; `current_user_id: UUID = Depends(get_current_user_id)`; ownership через репо; try/except на доменных исключениях → `HTTPException`
- [ ] Модуль добавлен в `APPS` в `app/archtool_conf/custom_layers.py`
- [ ] `archtool validate` — зелёный
- [ ] Тест сборки запускается без `TopLevelLayerUsingException`
- [ ] (опционально) `archtool graph` показывает, что новый домен встроен туда, куда задумано

---

## 12. Точка входа: что собирается в `bundle_project`

Для понимания агентом, как всё стартует:

```python
# app/archtool_conf/bundle_project.py
import pathlib

from archtool.dependency_injector import DependencyInjector
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.pool import NullPool

from web_fractal.building_utils import import_all_models, initialize_controllers_api
from web_fractal.db import Base

import app.config as settings
from app.archtool_conf.custom_layers import APPS, app_layers
from app.core_integrations.reg_deps import reg_deps


BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]


def init_deps(injector: DependencyInjector) -> AsyncEngine:
    engine = create_async_engine(
        settings.SQLALCHEMY_DATABASE_URI_ASYNC,
        echo=False,
        poolclass=NullPool,
    )
    session_maker = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False,
    )

    injector.register(key=AsyncEngine, value=engine, inject_into=False)
    injector.register(key=async_sessionmaker, value=session_maker, inject_into=False)
    reg_deps(injector)
    return engine


def bundle(app: FastAPI) -> DependencyInjector:
    # 1. Создаём инжектор с явным project_root — никаких sys.path-хаков
    injector = DependencyInjector(
        modules_list=APPS,
        layers=app_layers,
        project_root=BACKEND_ROOT,
    )

    # 2. Регистрируем async-ресурсы и pre-built клиенты ДО inject()
    init_deps(injector)

    # 3. Импортируем все ORM-модели, чтобы Base.metadata был полным
    import_all_models(Base=Base)

    # 4. Разводим DI (валидация слоёв происходит между Pass 1 и Pass 2)
    injector.inject()

    # 5. Регистрируем FastAPI-роутеры из всех найденных контроллеров
    initialize_controllers_api(injector=injector, app=app)

    return injector
```

**Порядок важен:**

- `init_deps` ДО `inject()` — иначе сторонние инстансы не зарегистрированы.
- `import_all_models` ДО `inject()` — иначе `Base.metadata` неполный.
- `injector.inject()` — между Pass 1 и Pass 2 в v2.x проверяются слои; если есть нарушение — `TopLevelLayerUsingException` падает здесь.

---

## 13. Как агент должен начинать работу с проектом

1. **Прочитать `app/archtool_conf/custom_layers.py`** — увидеть список модулей и кастомные слои.
2. **Прочитать `app/<domain>/interfaces.py`** для каждого релевантного модуля — это спецификация контекстов.
3. **Прочитать `app/<domain>/exceptions.py`** — какие доменные исключения возможны.
4. **Проверить, есть ли в репозитории `AGENTS.md` / `CLAUDE.md` с project-specific блоком** (см. раздел 14) — там могут быть факты, специфичные для этого проекта (кастомные слои, нестандартные модули, особенности конфига).
5. **При запросе «добавь X»:**
   - Это новый домен? → `archtool add-module` + раздел 8.2.
   - Это новый эндпоинт в существующем? → раздел 8.3.
   - Это интеграция? → 8.7.
6. **Перед коммитом:** `archtool validate` + тест сборки.

---

## 14. Project-specific блок (опциональный)

Этот документ — agnostic. Если проект имеет отклонения от стандарта, добавь в конец `AGENTS.md` (или в отдельный файл `PROJECT.md` рядом) короткий блок:

```markdown
## Project-specific facts

- **Доменные модули в текущем проекте:** users, projects, schemas, ...
- **Кастомные слои:** IntegrationsLayer (clients.py + ABCClient)
- **Особенности core_integrations:** регает MinioInternalKey, MinioPubKey, CentrifugoClient через reg_deps()
- **Известные отклонения:** в модуле X пока нет exceptions.py, репо кидает HTTPException — TODO мигрировать
- **Где найти что:**
  - конфиг — app/config.py
  - сборка — app/archtool_conf/bundle_project.py
  - точка входа — entrypoints/run.py
- **Кастомные конвенции:**
  - переменные окружения через `web_fractal.utils.get_settings_value(s)`
  - JWT-аутентификация через `app.users.dependencies.get_current_user_id`
```

Цель project-specific блока — чтобы свежий агент за 60 секунд понял, где что лежит и какие в этом проекте отступления от общего стандарта.

---

## 15. Миграция v0.x → v2.x archtool

Если проект исторически на archtool 0.2.0, делаешь bump до 2.x — пройдись по списку:

| Найти | Заменить на |
|---|---|
| `injector._reg_dependency(K, v, use_serialization_function=True, nested_injections_allowed=False)` | `injector.register(key=K, value=v, inject_into=False)` |
| `injector._reg_dependency(K, v)` (без флагов) | `injector.register(key=K, value=v)` (`inject_into=True` по дефолту) |
| `frozenset([Layer1, Layer2, ...])` | `[Layer1, Layer2, ...]` |
| `sys.path.insert(0, apps_root.as_posix())` в `bundle_project.bundle()` | удалить; добавить `project_root=BACKEND_ROOT` в `DependencyInjector(...)` |
| Свой `class PresentationLayer(Layer): depends_on = ApplicationLayer or DomainLayer` | удалить; импортировать `PresentationLayer` из `archtool.layers.default_layers` |
| `injector._dependencies` | `injector.dependencies` |
| `from typing import List; AppModules = List[AppModule]` | `list[AppModule]` (или импортировать `AppModules` из `archtool.global_types`) |
| Шумные debug-логи archtool в проде | Ничего не делать — `NullHandler` теперь дефолт. Если включал намеренно — переехать на `ARCHTOOL_VERBOSE=1` env |

После миграции — `archtool validate` + тест сборки. Если есть тесты, которые регали моки через `_reg_dependency` — заменить на `register()`.

---

# Приложение: установка скилла в агентов

## Claude Code (project-level)

В корне проекта положи файл `CLAUDE.md` или `AGENTS.md`. Содержимое — этот документ + (опционально) project-specific блок в конце (раздел 14).

Claude Code автоматически подгружает оба файла из корня репозитория в контекст.

```
<repo-root>/
├── AGENTS.md      ← положи сюда
└── app/
    └── ...
```

## Claude.ai (user-level skill)

Анатомия Anthropic Skill — папка с `SKILL.md`, у которого есть frontmatter:

```markdown
---
name: archtool-web_fractal-style
description: Use this skill whenever the user is writing Python code in a project that uses archtool (≥2.0) + web_fractal (FastAPI + SQLAlchemy async). Covers module structure, layer rules, DI patterns (register, inject_into, project_root), web_fractal helpers (UnitOfWork, serialize, apply_filters), DDD domain exceptions, and CLI workflows. Trigger on requests to add a new domain, add an endpoint, integrate a third-party service, or refactor existing code in this style.
---

[вставь содержимое этого документа]
```

Положи в `~/.claude/skills/archtool-web_fractal-style/SKILL.md` (для Claude Code, который читает user-level skills) или загрузи через UI Claude.ai.

Скилл будет автоматически подтягиваться, когда Claude увидит, что задача про archtool-стиль.

## Cursor

`.cursor/rules/archtool.mdc` в корне проекта:

```markdown
---
description: archtool + web_fractal architectural style
globs: app/**/*.py
alwaysApply: true
---

[содержимое документа]
```

`globs` заставит правило применяться только при работе с файлами в `app/`. `alwaysApply: true` — всегда, когда правило подходит по `globs`.

## Generic LLM-агент (без специальных интеграций)

Префикс к системному промпту:

```
Ниже — архитектурный стиль проекта. Следуй ему при написании кода.

[вставь документ]
```

## Версионирование

Документ project-agnostic, поэтому хорошо хранится отдельно от кода. Варианты:

- собственный публичный npm/pypi-пакет (overkill, но самая чистая модель)
- gist / приватный репо `nonliner/archtool-style` с тегами по версиям; в каждом проекте — git submodule или скопированный файл
- одна каноническая копия в репо `archtool-meta`, проекты ссылаются на неё через URL в их `AGENTS.md`

Самый прагматичный вариант на старте — копия в каждом проекте, синхронизация вручную раз в спринт. При обновлении archtool/web_fractal — пройди по разделу 15 (миграция) и обнови документ.

## Что делать при расхождении кода и скилла

Если в реальном коде есть устойчивый паттерн, которого нет в этом документе, — он либо:

- (а) частный случай, который не стоит закреплять как правило;
- (б) пробел в документе, который надо закрыть;
- (в) легаси, которое надо мигрировать (см. раздел 15).

Не используй код как авторитет автоматически. Авторитет — этот документ + дока archtool (`https://0nliner.github.io/archtool/ru/`). При расхождении: либо обнови документ, либо причеши код.
