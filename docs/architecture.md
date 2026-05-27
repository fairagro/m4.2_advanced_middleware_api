# Architecture

```mermaid
architecture-beta

    group rdi1(database)[RDI 1]
    service rdi1db(database)[DB] in rdi1
    service sql2arc(server)[sql2arc] in rdi1

    group rdi2(database)[RDI 2]
    service rdi2db(database)[DB] in rdi2
    service csw(server)["CSW / INSPIRE"] in rdi2

    group rdi3(database)[RDI 3]
    service rdi3db(database)[DB] in rdi3
    service web(internet)["Web / schema.org"] in rdi3

    group middleware(cloud)[Middleware]
    service api(server)[API] in middleware
    service db(database)[CouchDB] in middleware
    service git(database)[DataHUB] in middleware
    service harvester(server)[Harvester] in middleware

    service searchhub(server)[SearchHUB]
    service sciwin(server)[SciWIn]

    api:R --> L:db
    db:R --> L:git
    sql2arc:L --> R:rdi1db
    sql2arc:R --> L:api
    csw:L --> R:rdi2db
    web:L --> R:rdi3db
    harvester:T --> B:api
    harvester:L --> R:csw
    harvester:B --> T:web
    searchhub:L --> R:git
    sciwin:L --> B:git
```
