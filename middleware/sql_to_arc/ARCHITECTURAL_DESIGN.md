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
- **Multiprocessing Support:** Der Aufruf von `multiprocessing.freeze_support()` stellt sicher, dass die Middleware auch in "eingefrorenen" Umgebungen (wie PyInstaller-Binaries unter Windows) korrekt neue Prozesse starten kann. Unter Linux ist dies primär eine Best-Practice für die Cross-Platform Kompatibilität.

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

## 4. Speicher-Management & Performance-Optimierung

Bei der Verarbeitung von tausenden Investigations (ARC-Containern) kann der RAM-Verbrauch kritisch werden. Die Middleware implementiert hierfür drei Strategien:

### 4.1 Backlog Flow Control (Produzenten-Pause)

Der asynchrone Datenbank-Stream produziert Daten schneller, als der Prozess-Pool sie konvertieren kann.

- **Problem:** Tausende `asyncio.Tasks` würden gleichzeitig im RAM auf ihre Ausführung warten, inklusive aller zugehörigen Datenbank-Zeilen.
- **Lösung:** Eine Drosselung im Haupt-Loop: `if len(running_tasks) >= max_concurrent_tasks: await asyncio.wait(...)`. Der Stream pausiert, bis wieder Kapazität frei ist. Dies limitiert die Anzahl der Datensätze, die sich gleichzeitig im Speicher befinden.

### 4.2 Worker-Side Serialization & GC

Die ARC-Objekte der `arctrl` Bibliothek sind komplex und beanspruchen sowohl Python- als auch .NET-Speicher.

- **Strategie:** Die Konvertierung zum JSON-String erfolgt direkt im Worker-Prozess.
- **Memory Cleanup:** Nach der Serialisierung werden die ARC-Objekte im Worker explizit gelöscht (`del`) und der Garbage Collector (`gc.collect()`) aufgerufen, bevor der Prozess das Ergebnis an den Hauptprozess zurückgibt. Dies verhindert das "Anschwellen" der Worker-Prozesse.

### 4.3 JSON vs. Objekt-Transfer

Zwischen dem Hauptprozess und den Workern werden keine komplexen ARC-Objekte übertragen, sondern lediglich primitive Python-Datentypen (Dicts) als Input und fertige JSON-Strings als Output. Dies minimiert den Overhead der Inter-Prozess-Kommunikation (IPC).

### 4.4 Entkopplung von I/O und CPU (Workload Balancing)

Um die CPU-Auslastung zu maximieren, wird die Anzahl der gleichzeitig aktiven Tasks (`max_concurrent_tasks`) unabhängig von der Anzahl der CPU-Worker (`max_concurrent_arc_builds`) gesteuert.

- **Prinzip:** Während ein Teil der Tasks auf die Netzwerk-Antwort der API wartet (I/O), können die CPU-Worker bereits den nächsten ARC-Build aus der Warteschlange verarbeiten.
- **Konfiguration:** Standardmäßig ist die Task-Kapazität doppelt so groß wie die Anzahl der CPU-Worker (einstellbar via `max_concurrent_tasks`), um Latenzen zu überbrücken, ohne den RAM zu überlasten.

---

## 5. Datenfluss (Step-by-Step)

1. **Producer:** Der Hauptprozess startet den Streaming-Generator.
2. **Throttle:** Der Loop wartet an der `Semaphore` auf einen freien Slot.
3. **Data Fetch:** Eine Untersuchung wird aus der DB gelesen.
4. **Build (CPU):** Der Datensatz wird an den `ProcessPoolExecutor` geschickt. Der Haupt-Loop bleibt währenddessen frei für andere Aufgaben.
5. **Upload (I/O):** Das Ergebnis (JSON) wird asynchron per HTTP an die Middleware-API gesendet.
6. **Release:** Die Semaphore wird freigegeben, der nächste Datensatz fließt nach.

---

## 6. Fehlerbehandlung & Monitoring

- **Gezieltes Exception Handling:** Fehler beim Upload oder beim Build führen nicht zum Abbruch des gesamten Laufs.
- **ProcessingStats:** Jeder Erfolg und Fehler wird mit ID erfasst und am Ende als JSON-LD Report ausgegeben.
- **Tracing:** Die gesamte Kette ist mit OpenTelemetry (Tracing) instrumentiert, um Performance-Engpässe im Prozess-Pool oder Netzwerk zu identifizieren.

---

## 7. Zusammenfassung der Design-Entscheidungen

| Problem | Lösung | Grund |
| :--- | :--- | :--- |
| GIL / CPU-Limit | `ProcessPoolExecutor` | Echte Parallelität auf mehreren Kernen. |
| Niedrige CPU Auslastung | I/O-CPU Entkopplung | `max_concurrent_tasks` erlaubt API-Uploads parallel zu neuen ARC-Builds. |
| Memory Overflow (Backlog) | Producer Throttling | Verhindert, dass zu viele Datensätze gleichzeitig im RAM "warten". |
| Memory Leak (Worker) | `gc.collect()` + JSON Return | Gibt Speicher im Worker sofort nach der Konvertierung frei. |
| Datenbank-Last | `fetchmany` + `ANY()` | Optimale Balance zwischen Abfrage-Anzahl und Speicherlast. |
| Skalierbarkeit | Single ARC Processing | Früherer Erfolg/Fehler-Feedback pro Untersuchung statt nur pro Batch. |

---

## 8. Performance Tuning Guide

Um die Middleware optimal an die vorhandene Hardware und die Datenstruktur der Datenbank anzupassen, können folgende Parameter in der Konfigurationsdatei (`config.yaml`) optimiert werden:

### 8.1 CPU & Parallelisierung

- **`max_concurrent_arc_builds`**: Bestimmt die Anzahl der Worker-Prozesse im `ProcessPoolExecutor`.
  - **Empfehlung**: Setzen Sie diesen Wert auf die Anzahl der verfügbaren CPU-Kerne minus 1 (um Reserven für den Hauptprozess und das Betriebssystem zu lassen).
  - **Effekt**: Höhere CPU-Last, aber schnellere Verarbeitung der ARC-Generierung.

### 8.2 Durchsatz & I/O Balancing

- **`max_concurrent_tasks`**: Limitiert die Anzahl der gleichzeitig aktiven asynchronen Workflows (Datenfetch + Build + Upload).
  - **Faustformel**: `4 * max_concurrent_arc_builds`.
  - **Warum?**: Während z.B. 4 Kerne ARCs berechnen, können die restlichen Tasks auf die Netzwerk-Antwort der API warten (I/O). Ein zu hoher Wert führt zu erhöhtem RAM-Verbrauch; ein zu niedriger Wert lässt die CPU leerlaufen ("Stop-and-Go").
  - **Tuning**: Wenn die CPU-Auslastung trotz Arbeit stark schwankt, erhöhen Sie diesen Wert leicht (z.B. auf `5 * builds`).

### 8.3 Datenbank-Effizienz

- **`db_batch_size`**: Anzahl der Investigations, die pro Datenbank-Chunk geladen werden.
  - **Standard**: 100.
  - **Tuning**: Erhöhen Sie diesen Wert bei sehr vielen kleinen Investigations (wenige Studies/Assays), um die Anzahl der SQL-Roundtrips zu senken. Senken Sie ihn, wenn einzelne Investigations extrem groß sind, um den RAM-Verbrauch des Hauptprozesses zu limitieren.

### 8.4 Stabilität & Timeouts

- **`arc_generation_timeout_minutes`**: Maximalzeit für einen einzelnen `build_arc_for_investigation` Aufruf im Worker.
  - **Tuning**: Erhöhen Sie diesen Wert, falls Sie im Log "Timeout" Fehler bei sehr großen Datensätzen (z.B. Tausende Assays) sehen.

### 8.5 Zusammenfassung: Das optimale Setup finden

1. **CPU-Limit finden**: Erhöhen Sie `max_concurrent_arc_builds` bis die CPU-Kerne ausgelastet sind.
2. **I/O-Löcher füllen**: Erhöhen Sie `max_concurrent_tasks`, wenn die CPU-Last zwischen den Builds auf 0% sinkt (Anzeichen für Warten auf API-Uploads).
3. **RAM-Check**: Überwachen Sie den Speicherverbrauch. Der RAM-Bedarf steigt linear mit `max_concurrent_tasks` und der Größe der Investigations im Batch.
