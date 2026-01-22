# Architektur-Dokumentation: SQL-to-ARC Middleware

## 1. Übersicht

Die SQL-to-ARC Middleware ist für die Konvertierung von Metadaten aus einer relationalen SQL-Datenbank in das **ARC (Annotated Research Context)** Format verantwortlich. Die Architektur ist auf **hohen Durchsatz**, **speichereffiziente Verarbeitung** und **Stabilität** bei großen Datenmengen ausgelegt.

## 2. Kernkomponenten

Die Middleware besteht aus drei Hauptschichten:

1. **Async IO Loop (Controller):** Orchestriert den Datenfluss, verwaltet Datenbank-Streams und API-Uploads.
2. **Process Pool Executor (Worker):** Parallelisiert die CPU-lastige ARC-Berechnung in separaten Betriebssystem-Prozessen.
3. **Streaming Generator (Data Layer):** Liest Daten in Chunks aus der Datenbank, um den RAM-Verbrauch konstant zu halten.

---

## 3. Detaillierte Architekturkonzepte

### 3.1 Parallelisierung & CPU-Offloading

Da die Generierung von ARCs (via `arctrl`) rechenintensiv ist und Python durch das Global Interpreter Lock (GIL) limitiert wird, nutzt die Middleware einen `ProcessPoolExecutor`.

- **Vorteil:** Jede ARC-Berechnung läuft auf einem eigenen CPU-Kern.
- **Implementierung:** `loop.run_in_executor(executor, build_arc_for_investigation, ...)`

### 3.2 Concurrency & Flow Control (Die Semaphore)

Zusätzlich zum Prozess-Pool wird eine `asyncio.Semaphore` verwendet. Dies adressiert zwei kritische Probleme, die ein reiner Prozess-Pool nicht lösen kann:

1. **Memory Protection:** Ohne Semaphore würde Python für alle (z. B. 10.000) Datensätze gleichzeitig asynchrone Tasks starten und Daten aus der DB im RAM halten. Die Semaphore limitiert die Anzahl der *gleichzeitig aktiven* Workflows.
2. **Network/IO Backpressure:** Die Semaphore begrenzt auch die Anzahl der gleichzeitigen HTTP-Verbindungen zur API, um Timeouts und Rate-Limiting zu vermeiden.

**Diskussionspunkt:** *Warum nicht einfach die Größe des Prozess-Pools limitieren?*
Der Prozess-Pool limitiert nur die CPU-Auslastung. Die Semaphore limitiert den **gesamten Lebenszyklus** (Datenvorbereitung -> Build -> Upload). Sie verhindert, dass der Speicher mit "wartenden" Daten überläuft, bevor diese überhaupt an den Pool übergeben werden.

### 3.3 Speichereffizientes Daten-Streaming

Die Middleware implementiert einen **Lazy-Loading** Ansatz für Datenbank-Entitäten:

- **Chunking:** Über den Generator `stream_investigation_datasets` werden Untersuchungen mit `fetchmany(batch_size)` geladen.
- **Relationales Batching:** Für jeden Chunk (z. B. 100 Untersuchungen) werden die zugehörigen Studies und Assays in einem einzigen Bulk-Query (`WHERE investigation_id = ANY(...)`) nachgeladen.
- **Effekt:** Wir vermeiden das "N+1 Query" Problem (extrem langsam) und gleichzeitig den "Full Table Load" (extrem speicherhungrig).

---

## 4. Datenfluss (Step-by-Step)

1. **Producer:** Der Hauptprozess startet den Streaming-Generator.
2. **Throttle:** Der Loop wartet an der `Semaphore` auf einen freien Slot.
3. **Data Fetch:** Eine Untersuchung wird aus der DB gelesen.
4. **Build (CPU):** Der Datensatz wird an den `ProcessPoolExecutor` geschickt. Der Haupt-Loop bleibt währenddessen frei für andere Aufgaben.
5. **Upload (I/O):** Das Ergebnis (JSON) wird asynchron per HTTP an die Middleware-API gesendet.
6. **Release:** Die Semaphore wird freigegeben, der nächste Datensatz fließt nach.

---

## 5. Fehlerbehandlung & Monitoring

- **Gezieltes Exception Handling:** Fehler beim Upload oder beim Build führen nicht zum Abbruch des gesamten Laufs.
- **ProcessingStats:** Jeder Erfolg und Fehler wird mit ID erfasst und am Ende als JSON-LD Report ausgegeben.
- **Tracing:** Die gesamte Kette ist mit OpenTelemetry (Tracing) instrumentiert, um Performance-Engpässe im Prozess-Pool oder Netzwerk zu identifizieren.

---

## 6. Zusammenfassung der Design-Entscheidungen

| Problem | Lösung | Grund |
| :--- | :--- | :--- |
| GIL / CPU-Limit | `ProcessPoolExecutor` | Echte Parallelität auf mehreren Kernen. |
| Memory Overflow | `asyncio.Semaphore` | Begrenzt die Anzahl der Datensätze im RAM. |
| Datenbank-Last | `fetchmany` + `ANY()` | Optimale Balance zwischen Abfrage-Anzahl und Speicherlast. |
| Skalierbarkeit | Single ARC Processing | Früherer Erfolg/Fehler-Feedback pro Untersuchung statt nur pro Batch. |
