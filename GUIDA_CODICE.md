# Guida al codice — Servoscala Connesso

Questo file spiega **ogni impostazione** del progetto: cosa fa, perché è lì e cosa
rispondere se te lo chiedono. Studia in quest'ordine: prima la mappa, poi i quattro
file, poi le domande d'esame in fondo.

---

## 1. La mappa in 30 secondi

Quattro programmi Python, tutti nella cartella principale. Girano
**contemporaneamente**, ognuno nel suo terminale, e non si parlano mai
direttamente: passano tutti dal **broker MQTT** (Mosquitto).

```
                        ┌──────────────────┐
   servoscala.py  ────▶ │                  │ ◀────  stazione_chiamata.py
   (device, N copie)    │  BROKER MQTT     │        (device, N copie)
                        │  Mosquitto :1883 │
   manager.py     ◀───▶ │                  │ ────▶  ascolta.py (opzionale)
   (il cervello)        └──────────────────┘
```

| File | Righe | Cos'è |
|---|---|---|
| `comune.py` | ~180 | Non è un programma: è la scatola delle costanti condivise |
| `servoscala.py` | ~200 | Il device principale. Sensori + attuatori |
| `stazione_chiamata.py` | ~85 | Il device secondario. 1 sensore + 1 attuatore |
| `manager.py` | ~230 | Il backend: raccoglie tutto e applica le 5 regole |
| `ascolta.py` | ~35 | Opzionale, solo per la demo: mostra le notifiche in una finestra pulita |

**La direzione dei dati è la chiave di tutto:**

- I device **pubblicano** ciò che i sensori leggono → il manager li riceve.
- Il manager **pubblica comandi** → i device li ricevono e muovono gli attuatori.

Non c'è mai un device che chiede qualcosa a un altro device.

---

## 2. Come si avvia (5 terminali)

```powershell
cd C:\Users\brigh\Claude\Projects\servoscala

# Terminale 1 — il cervello
py manager.py

# Terminale 2 — le notifiche in bella vista (opzionale ma fa scena)
py ascolta.py

# Terminale 3 e 4 — due servoscala della flotta
py servoscala.py --id SV01 --edificio "Palazzina A" --piani 4
py servoscala.py --id SV02 --edificio "Palazzina B" --piani 6

# Terminale 5 — una stazione di chiamata
py stazione_chiamata.py --id ST01 --piano 0
```

Il broker Mosquitto è già un **servizio Windows**, parte da solo. Per verificarlo:
`Get-Service mosquitto` in PowerShell.

Chiudi tutto con `CTRL+C` in ogni finestra.

---

## 3. `comune.py` — tutte le impostazioni, una per una

### 3.1 Connessione

```python
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883
KEEPALIVE = 60
```

- **`127.0.0.1`** è "questo stesso computer" (localhost). Se domani il broker
  stesse su un altro PC, cambieresti solo questa riga, in un solo file.
- **`1883`** è la porta standard MQTT in chiaro. La 8883 sarebbe MQTT su TLS
  (cifrato). Qui è tutto in locale, quindi non serve.
- **`KEEPALIVE = 60`**: ogni 60 secondi al massimo il client manda un pacchetto
  `PINGREQ` per dire "sono ancora vivo". Se il broker non sente nulla per
  1,5 × keepalive, considera il client morto e chiude la connessione.
  Serve perché una connessione TCP può "morire in silenzio" (cavo staccato) senza
  che nessuno se ne accorga.

### 3.2 I topic

Un **topic** è l'indirizzo di un canale. Chi pubblica scrive su un topic, chi è
interessato si iscrive. Il broker fa lo smistamento.

La convenzione, a livelli separati da `/`:

```
<tipo_device>/<id_device>/<categoria>[/<dettaglio>]
```

| Topic | Chi pubblica | Chi ascolta | QoS |
|---|---|---|---|
| `servoscala/SV01/telemetria` | device | manager | 0 |
| `servoscala/SV01/corsa` | device | manager | 1 |
| `servoscala/SV01/evento` | device | manager | 1 |
| `servoscala/SV01/comando/ricarica` | manager | device | 1 |
| `servoscala/SV01/comando/indicatore` | manager | device | 1 |
| `chiamata/ST01/pulsante` | stazione | manager | 1 |
| `chiamata/ST01/comando/led` | manager | stazione | 1 |
| `manager/notifica` | manager | operatore | 1 |

**Perché costruirli con funzioni** (`servoscala_telemetria("SV01")`) invece di
scrivere le stringhe a mano? Perché se scrivi `"telemetria"` in un file e
`"telemetrie"` in un altro il sistema non dà errore: semplicemente **non arriva
niente e non capisci perché**. Con la funzione l'errore è impossibile.

### 3.3 Le wildcard `+`

```python
SUB_TELEMETRIA = "servoscala/+/telemetria"
```

Il `+` è un jolly che sostituisce **esattamente un livello** del topic. Il manager
si iscrive quattro volte in tutto e riceve da **qualsiasi numero di device**,
anche quelli accesi dopo, senza sapere in anticipo come si chiamano.

> Esiste anche `#`, che sostituisce **tutti i livelli rimanenti** e va solo alla
> fine: `servoscala/#` prenderebbe tutto, comandi compresi. Qui useremmo `#` solo
> per fare debug, perché il manager riceverebbe anche i comandi che ha mandato lui.

### 3.4 I valori ammessi

Sono 17 stringhe con un nome: `STATO_IDLE = "idle"`, `EVENTO_ERRORE = "errore"`…

Sono normalissime stringhe, ma dando loro un nome:

- se sbagli a scrivere `C.STATO_IDEL` Python ti dà **errore subito**, mentre
  `"idel"` passerebbe inosservato e romperebbe un `if` in silenzio;
- leggendo il file capisci al volo quali sono **tutti** i valori possibili.

### 3.5 Le soglie

| Costante | Valore | Governa |
|---|---|---|
| `SOGLIA_INATTIVITA_S` | 25 s | R2 — dopo quanto scatta l'avviso benessere |
| `SOGLIA_BATTERIA_BASSA` | 35 % | R4 — sotto questo livello ricarica sempre veloce |
| `WARNING_CORSE` | 8 | R5 — corse oltre cui pianificare manutenzione |
| `WARNING_ANOMALIE` | 3 | R5 — anomalie oltre cui pianificare |
| `ALARM_USURA` | 45.0 | R6 — usura oltre cui è urgente |
| `ALARM_ANOMALIE` | 5 | R6 — anomalie oltre cui è urgente |

**I valori sono volutamente piccoli** perché la demo dura pochi minuti: in un
impianto vero l'inattività si misurerebbe in ore e le corse in migliaia. Dillo tu
prima che te lo chiedano — è una scelta di progetto, non un errore.

### 3.6 Le tre funzioni

- `adesso()` → data e ora ISO 8601, es. `2026-08-10T21:40:00`. Formato standard,
  ordinabile come testo.
- `pubblica(client, topic, payload, qos)` → fa `json.dumps` e pubblica. Serve
  perché **MQTT trasporta byte, non oggetti Python**: il dizionario va tradotto
  in testo JSON.
- `leggi(msg)` → l'inverso: da byte a dizionario.

---

## 4. `servoscala.py` — il device

### La struttura

```
__init__          crea lo stato interno e il client MQTT
_on_connect       CALLBACK: sottoscrive i due topic dei comandi
_on_message       CALLBACK: applica il comando ricevuto all'attuatore
_pubblica_telemetria / _pubblica_evento     escono i dati dei sensori
_esegui_corsa / _ricarica_batteria / _forse_guasto    la fisica simulata
avvia             connette e cicla per sempre
```

### Le impostazioni del client

```python
mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=device_id)
```

- **`CallbackAPIVersion.VERSION2`**: paho-mqtt 2.x ha cambiato la firma delle
  callback (è comparso `properties`, che è roba di MQTT 5). Dichiarando VERSION2
  usi la firma nuova. Senza questo parametro la libreria stampa un warning.
- **`client_id`**: deve essere **univoco sul broker**. Usiamo l'ID del device, così
  è unico per costruzione. Se due client si connettono con lo stesso ID, il broker
  **butta fuori il primo** — è una classica causa di device che si disconnettono
  a vicenda senza motivo apparente.

### La probabilità 0.5

```python
if random.random() < 0.5:
    self._esegui_corsa()
else:
    self._ricarica_batteria()
```

`random.random()` dà un numero fra 0 e 1. Confrontarlo con 0.5 significa "50% delle
volte". Stessa logica per `0.12` (12% di passeggeri sovrappeso), `0.02` e `0.03`
(guasti rari), `0.4` nella stazione.

### Il legame peso → assorbimento

```python
self.assorbimento = round(2.0 + peso * 0.04 + random.uniform(-0.2, 0.2), 2)
```

Questa riga è **il cuore della manutenzione predittiva**. Dice: il motore assorbe
2 A a vuoto, più 0,04 A per ogni kg trasportato, più un po' di rumore casuale.
Serve perché il manager (R3) possa dedurre l'usura dagli Ampere.

Con 75 kg → circa 5 A. Con 120 kg → circa 6,8 A.

### Gli argomenti da riga di comando

| Argomento | Default | A cosa serve |
|---|---|---|
| `--id` | SV01 | Identifica il device. **Deve essere diverso per ogni copia** |
| `--edificio` | Palazzina A | Solo descrittivo, finisce nella telemetria |
| `--piani` | 4 | Piani serviti, 0 = piano terra |
| `--intervallo` | 3.0 | Secondi fra un ciclo e il successivo. Abbassalo per una demo più rapida |

---

## 5. `stazione_chiamata.py` — il device semplice

È il servoscala in miniatura: **un sensore** (il pulsante) e **un attuatore** (il
LED). Serve a dimostrare che l'architettura regge più tipi di device diversi senza
cambiare nulla nel manager — è il `+` nelle wildcard che fa il lavoro.

Se hai poco tempo, studia bene `servoscala.py` e questo lo leggi in cinque minuti:
è la stessa identica impalcatura.

---

## 6. `manager.py` — il cervello

### Il flusso

Il manager fa **due cose insieme**, ed è per questo che serve `loop_start()`:

- **in un thread di rete**, `_on_message` scatta a ogni messaggio e aggiorna la
  struttura di stato (questa è la **R1**);
- **nel thread principale**, ogni 4 secondi, `_valuta_regole()` guarda lo stato e
  decide, poi `_dashboard()` stampa.

### La struttura di stato (R1)

`self.servoscale` è un dizionario `device_id → dizionario`. Ogni voce contiene:

- i **dati grezzi** che arrivano dalla telemetria (batteria, stato, corse…);
- i **dati calcolati** dal manager (`usura`, `anomalie`, `ultima_corsa`);
- la **memoria delle decisioni già prese** (`benessere_notificato`,
  `ricarica_comandata`, `manutenzione`).

Quest'ultimo gruppo è la parte furba: **senza di esso il manager ripeterebbe lo
stesso allarme ogni 4 secondi**, riempendo lo schermo. Con esso, agisce solo quando
qualcosa *cambia*.

`_stato(device_id)` crea la voce alla prima comparsa del device: è così che il
sistema **scopre i device da solo**, senza un elenco scritto da nessuna parte.

### Lo smistamento in `_on_message`

```python
categoria = msg.topic.split("/")[-1]
```

C'è **una sola** callback `on_message` per tutti i messaggi in arrivo. Per capire
di che messaggio si tratta guardiamo l'ultimo livello del topic:
`servoscala/SV01/corsa` → `"corsa"`. Poi una catena di `if`.

### Le cinque regole

| | Regola | Ingresso | Uscita |
|---|---|---|---|
| **R1** | Stato aggiornato | tutti i messaggi | il dizionario `servoscale` |
| **R2** | Benessere | secondi dall'ultima corsa | notifica `benessere` |
| **R3** | Stima usura | assorbimento di ogni corsa | il campo `usura` |
| **R4** | Ricarica intelligente | attività recente + batteria | comando `lenta`/`veloce` |
| **R5** | Manutenzione programmata | n. corse, n. anomalie | notifica `warning` |
| **R6** | Manutenzione urgente | usura, n. anomalie | notifica `alarm` + comando indicatore |

**R2 — benessere.** È la regola "sociale" del progetto: un servoscala usato ogni
giorno che smette di funzionare può voler dire che la persona sta male. Il flag
`benessere_notificato` si azzera appena arriva una corsa.

**R3 — usura.** Sommiamo gli Ampere di ogni corsa. Poiché gli Ampere dipendono dal
peso, la somma è una stima di quanto ha faticato il motore: più corse pesanti →
usura più veloce. Non è il numero di corse: **è il lavoro fatto**.

**R4 — ricarica.** Se c'è stata attività da meno di 12 secondi siamo in una fascia
di uso: teniamo la batteria pronta (veloce). Altrimenti carichiamo piano, che è
meglio per la durata della batteria. Eccezione: sotto il 35% ricarica veloce
comunque. *In un impianto reale il manager imparerebbe le fasce orarie dallo
storico di giorni* — dillo, è la domanda ovvia.

**R5/R6 — manutenzione.** Prima calcoliamo il livello (`nessuno`/`warning`/`alarm`),
poi agiamo **solo se è peggiorato**:

```python
gravita = {"nessuno": 0, "warning": 1, "alarm": 2}
if gravita[livello] > gravita[s["manutenzione"]]:
```

Così un allarme non si ripete e non si "torna indietro" da solo: serve un
intervento di manutenzione (che qui non simuliamo) per azzerare.

---

## 7. Le domande che ti farà il prof

### Sulle callback (ci tiene)

**"Cos'è una callback?"**
Una funzione che **non chiami tu**: la registri, e sarà la libreria a invocarla
quando succede l'evento. Qui ne registriamo due:

```python
self.client.on_connect = self._on_connect    # nota: NESSUNA parentesi
self.client.on_message = self._on_message
```

Senza parentesi perché stiamo passando **la funzione stessa**, non il suo
risultato. Con `self._on_connect()` la eseguiremmo subito e assegneremmo `None`.

**"Perché ti iscrivi dentro `on_connect` e non subito dopo `connect()`?"**
Due motivi. Primo: `connect()` **non aspetta** la risposta del broker, quindi
subito dopo la connessione potrebbe non essere ancora stabilita e la `subscribe`
andrebbe persa. Secondo: se la connessione cade e paho la ripristina da solo,
`on_connect` scatta di nuovo e **le sottoscrizioni si rifanno automaticamente**.

**"Chi esegue `on_message`?"**
Il **thread di rete** creato da `loop_start()`, non il thread principale. È per
questo che nel manager scriviamo `list(self.servoscale.items())`: mentre il ciclo
principale itera, il thread di rete potrebbe aggiungere un device nuovo, e
modificare un dizionario mentre lo si sta scorrendo dà errore.

**"Cosa sono i parametri `client, userdata, flags, reason_code, properties`?"**
È la firma imposta da paho 2.x. `client` è il client che ha ricevuto l'evento;
`userdata` è un oggetto tuo che puoi far passare (qui non lo usiamo perché lo
stato ce l'abbiamo già in `self`); `flags` e `properties` sono dettagli del
protocollo; `reason_code` è **0 se è andata bene**, ed è l'unico che controlliamo.

### Su MQTT

**`loop_start()` vs `loop_forever()`**
`loop_forever()` blocca il programma: va bene solo per chi **ascolta e basta**
(`ascolta.py`). `loop_start()` apre un thread in background, così il programma può
continuare a fare altro — simulare corse, valutare regole — **mentre** i messaggi
arrivano. Device e manager usano questo.

**Perché QoS 0 sulla telemetria e QoS 1 su tutto il resto?**

- **QoS 0** = "al massimo una volta", nessuna conferma. La telemetria è un flusso
  continuo: se salta un campione, tre secondi dopo ne arriva un altro. Costa meno.
- **QoS 1** = "almeno una volta", con conferma e rispedizione. Corse, eventi,
  comandi e notifiche **non si possono perdere**. Un comando perso lascerebbe
  l'attuatore nello stato sbagliato.
- **QoS 2** = "esattamente una volta". Non serve: le nostre operazioni sono
  idempotenti (rimandare "ricarica veloce" due volte non fa danni) e QoS 2 costa
  quattro passaggi di rete invece di due.

**Perché MQTT e non HTTP?**
Publish/subscribe invece di request/response: il manager non deve interrogare i
device (*polling*), sono loro a parlare quando hanno qualcosa da dire. È
**disaccoppiato** (device e manager non si conoscono, conoscono solo i topic),
leggero (header di 2 byte contro centinaia) e adatto a device a batteria.
Aggiungere un servoscala non richiede di toccare il manager.

**Cosa succede se il broker si spegne?**
I client perdono la connessione; paho tenta la riconnessione da solo. Alla
riconnessione `on_connect` riparte e rifà le sottoscrizioni. I messaggi pubblicati
in QoS 1 nel frattempo restano in coda nel client.

### Sull'architettura

**"Come aggiungo un terzo tipo di device?"**
Scrivi un nuovo file device sul modello di `stazione_chiamata.py`, aggiungi i suoi
topic in `comune.py` e una sola `subscribe` con `+` nel manager. Gli altri file non
si toccano.

**"Il sistema scala?"**
Il manager non ha un elenco di device: li scopre dai messaggi grazie alle wildcard.
Puoi accendere il decimo servoscala a sistema avviato e comparirà nella dashboard
al ciclo dopo.

**"Cosa manca per andare in produzione?"**
Onestà: autenticazione e TLS sul broker (ora è anonimo in chiaro), persistenza
dello stato su database (ora è tutto in RAM e si perde al riavvio), un *Last Will
and Testament* MQTT per accorgersi che un device è morto, e soglie tarate su dati
reali invece che scelte a mano.

---

## 8. Cosa c'è nella cartella `_extra/` (solo sul PC, non pubblicata su GitHub)

Roba che **non serve più al sistema** ma non è stata cancellata:

- `01_test/` — gli script del primo passo, per verificare che il broker rispondesse.
- `RICOSTRUZIONE.md` — la guida a rifare il progetto con la **vecchia** struttura a
  cartelle. Ora è fuorviante: ignorala.
- `vecchia_struttura_backup/` — i 9 file originali in `common/`, `devices/`,
  `manager/`. Sono lì per confronto, non importarli.

Restano invece al loro posto e ti servono: `docs/` (le dispense con i tuoi
appunti), `images/` (i diagrammi), `demo3d/` (le visualizzazioni 3D per la
presentazione).
