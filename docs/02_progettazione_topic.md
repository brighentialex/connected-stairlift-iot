# Passo 2 — Progettazione dei topic MQTT e dei messaggi

Questo documento definisce **chi pubblica cosa e dove**, e in **che formato**.
È la base su cui costruiremo i device (Passi 3-4) e il manager (Passi 5-6).

## 1. Come sono fatti i topic

Usiamo una gerarchia a livelli separati da `/`:

```
<tipo_device>/<id_device>/<categoria>[/<dettaglio>]
```

- **tipo_device**: `servoscala` oppure `chiamata`
- **id_device**: identificatore univoco, es. `SV01`, `SV02`, `ST01`
- **categoria**: cosa contiene il messaggio (`telemetria`, `corsa`, `evento`, `comando`, `pulsante`)

Questa struttura permette al manager di usare i **wildcard** per ascoltare tutti i
device insieme (vedi sotto), così il sistema supporta *n* device senza modifiche.

## 2. Tabella dei topic

| Topic | Chi pubblica | Chi riceve | Contenuto |
|---|---|---|---|
| `servoscala/<id>/telemetria` | Servoscala | Manager | Stato periodico del device |
| `servoscala/<id>/corsa` | Servoscala | Manager | Resoconto di una corsa (peso + assorbimento) |
| `servoscala/<id>/evento` | Servoscala | Manager | Emergenza / sovraccarico / errore |
| `servoscala/<id>/comando/indicatore` | Manager | Servoscala | Display di bordo: operativo / manutenzione |
| `servoscala/<id>/comando/ricarica` | Manager | Servoscala | Ricarica: lenta / veloce |
| `chiamata/<id>/pulsante` | Stazione | Manager | Pulsante premuto, su quale piano |
| `chiamata/<id>/comando/led` | Manager | Stazione | LED: libero / in_arrivo / occupato |
| `manager/notifica` | Manager | (interfaccia/log) | Benessere, manutenzione programmata/urgente |

## 3. I wildcard del manager

Il manager non conosce in anticipo gli ID dei device. Per riceverli tutti usa il
jolly `+`, che vale **un singolo livello** del topic:

- `servoscala/+/telemetria` → riceve da `SV01`, `SV02`, `SV03`, ...
- `chiamata/+/pulsante` → riceve da tutte le stazioni

(Esiste anche `#`, jolly *multi-livello*, che qui non ci serve.)

## 4. Formato dei messaggi: JSON

Ogni messaggio è un oggetto **JSON**. JSON è un formato testuale leggibile sia
dall'uomo sia dalla macchina, ed è lo standard per scambiare dati strutturati.
Regole che ci diamo:

- ogni messaggio include sempre `device_id` e `timestamp` (data/ora in formato ISO 8601);
- i nomi dei campi sono in italiano, minuscoli, senza spazi.

### Esempi di payload

**Telemetria del servoscala** — `servoscala/SV01/telemetria`
```json
{
  "device_id": "SV01",
  "edificio": "Palazzina A",
  "stato": "idle",
  "piano_corrente": 0,
  "livello_batteria": 87,
  "assorbimento_motore": 0.0,
  "contatore_corse": 154,
  "modalita_ricarica": "lenta",
  "indicatore_stato": "operativo",
  "timestamp": "2026-06-29T21:40:00"
}
```

**Resoconto corsa** — `servoscala/SV01/corsa`
```json
{
  "device_id": "SV01",
  "peso_kg": 78.5,
  "assorbimento_medio": 4.2,
  "piano_partenza": 0,
  "piano_arrivo": 2,
  "durata_s": 19,
  "timestamp": "2026-06-29T21:41:12"
}
```

**Evento diagnostico** — `servoscala/SV01/evento`
```json
{
  "device_id": "SV01",
  "tipo": "sovraccarico",
  "codice_errore": "E12",
  "descrizione": "Peso oltre il limite consentito",
  "timestamp": "2026-06-29T21:42:03"
}
```

**Pulsante stazione** — `chiamata/ST01/pulsante`
```json
{
  "device_id": "ST01",
  "piano": 2,
  "premuto": true,
  "timestamp": "2026-06-29T21:43:00"
}
```

**Comando** (manager → device) — es. `servoscala/SV01/comando/ricarica`

Per i comandi basta un valore semplice, ma per coerenza usiamo comunque JSON:
```json
{ "valore": "veloce", "timestamp": "2026-06-29T21:44:00" }
```

**Notifica del manager** — `manager/notifica`
```json
{
  "tipo": "manutenzione_urgente",
  "device_id": "SV01",
  "messaggio": "Usura stimata oltre il limite",
  "timestamp": "2026-06-29T21:45:00"
}
```

## 5. Qualità del servizio (QoS) — scelta

MQTT offre tre livelli di affidabilità nella consegna:

- **QoS 0** "al massimo una volta" — veloce, può perdere un messaggio.
- **QoS 1** "almeno una volta" — garantisce la consegna, possibili duplicati.
- **QoS 2** "esattamente una volta" — il più sicuro, il più lento.

Scelta del progetto:
- **telemetria** → QoS 0 (è un flusso continuo: se salta un campione, il successivo arriva subito);
- **corsa, evento, comando, notifica** → QoS 1 (sono informazioni importanti che non vogliamo perdere).

I valori ammessi per ogni campo (stati, tipi di evento, ecc.) sono definiti come
costanti in `comune.py`, così li riusiamo senza errori di battitura.
