# Demo 3D + portale di assistenza — Servoscala connesso

Tutti i file sono autonomi: doppio clic e si aprono nel browser.
Three.js viene caricato da CDN (serve internet al primo avvio); la dashboard non usa librerie.

| file | cosa contiene |
|---|---|
| `impianto_SV01_3rampe.html` | Palazzina A — 3 rampe, 4 piani, bandelle **gialle** |
| `impianto_SV02_2rampe.html` | Palazzina B — 2 rampe, 3 piani, bandelle **arancio** |
| `impianto_SV03_1rampa.html` | Villa Ginestre — 1 rampa, 2 piani, bandelle **azzurre** |
| `assistenza_flotta.html` | portale di assistenza: i 3 digital twin con 24 mesi di storico |
| `documentario_SV01.html` | documentario automatico di 2 min 41 s, registrabile in video con un clic |
| `servoscala_3d.html` | motore parametrico da cui sono generati i tre file (`?impianto=SV01\|SV02\|SV03`) |

I tre impianti si richiamano fra loro dalla barra in basso, e da lì si apre il portale;
dal portale si torna al twin 3D di ciascun impianto.

---

## I digital twin 3D

Un vano scala di condominio percorso da un servoscala a piattaforma modellato
su un impianto a piattaforma con guida curvilinea a trazione a fune. La geometria è generata dal numero di rampe:
le rampe si alternano fra le due corsie e fra un piano e l'altro c'è un
pianerottolo con inversione a 180°.

| elemento | perché è così |
|---|---|
| telemetria di transito | passando davanti al fine corsa di ogni piano il device aggiorna `piano_corrente` e pubblica: una corsa 0 → 3 produce 0, 1, 2, 3 e non solo 0 e 3 (l'emulatore Python aggiorna invece solo all'arrivo — il codice per allinearlo è nell'appendice A della dispensa) |
| guida curvilinea continua a doppio tubo | 26,0 m (3 rampe) / 16,7 m (2) / 7,3 m (1), senza interruzioni né trasbordi |
| trazione **a fune**, motrice a monte | il motore non è a bordo ma in testa alla guida: da qui la compattezza del carrello |
| pedana auto-livellante | il carrello si inclina con la guida, la piattaforma resta sempre in bolla |
| guida che **anticipa** il filo dei gradini di 70 cm | poiché la pedana resta orizzontale, il suo bordo a monte "vede" gradini più alti: la guida comincia a salire già sul pianerottolo e si rimette in piano 70 cm prima della fine della rampa |
| curve elicoidali sui pianerottoli | i 180° non sono piani: la guida guadagna 42 cm di quota mentre gira |
| solo il calpestio e le bandelle si ribaltano | parapetto e colonnina comandi restano fermi, come negli impianti reali |

Geometria verificata numericamente su tutte e tre le configurazioni: gradini 17,5 × 29 cm,
pendenza rampe **31,1°**, pendenza massima della guida **35,2°** (limite dell'impianto 55°),
franco minimo pedana/gradini **37 mm**, franco pedana/corrimano **69÷74 mm**,
fermate ai piani tutte in bolla con il calpestio **85 mm** sopra il pavimento.

### Comandi

- **Stazioni di chiamata** — premi ST01…ST0n come farebbe un condomino
- **Manovra a uomo presente** — SU / GIÙ a pressione mantenuta, STOP, EMERGENZA
- **Peso a bordo** — 0÷250 kg. Entra in tempo reale nel modello: assorbimento del motore
  (`2,0 + peso × 0,04`, la formula di `servoscala.py`), usura accumulata, corporatura del
  passeggero. Oltre i 120 kg (`LIMITE_PESO`) scatta `E12` e la corsa si interrompe
- **Velocità** — `x1` è il tempo reale (0,10 m/s), `x4` è il default
- **Auto-demo** — parte da sola: sceglie i piani e fa salire e scendere l'impianto

Mouse: trascina = ruota · rotella = zoom · tasto destro = sposta.

### Telemetria a schermo intero

Il pulsante **Telemetria** in basso (o il tasto **T**) apre un pannello a tutto schermo con
i valori in grande: riquadri per piano, batteria, corrente e corse, il payload completo
dell'ultima telemetria campo per campo, sicurezze, manutenzione predittiva, il traffico MQTT
e un grafico degli ultimi 60 secondi.

Le tre colonne si **allargano trascinando le maniglie** verticali che le separano, e il
riquadro del traffico MQTT mostra il messaggio **per intero**, mandato a capo: serve a leggere
i payload, non a intravederli.

Il registro tiene in memoria gli ultimi **400 messaggi** (circa dieci minuti) e si scorre.
Finché sei in cima le righe nuove entrano subito; appena scorri verso il basso per rileggere i
messaggi vecchi il riquadro si **congela**, così il testo che stai leggendo non si sposta di un
pixel. I messaggi che arrivano nel frattempo vengono contati nel pulsante *↑ n nuovi*: lo premi
(o riporti la barra in cima) e il registro riparte.

Il pulsante **Legenda colori** spiega ogni colore della pagina: il colore di ogni tipo di
messaggio MQTT con il suo QoS e il perché, i badge di stato, i tre stati dei pallini di
sicurezza, le barre di livello con il trattino del `LIMITE_PESO`, l'ambra dei valori di soglia
caricati da te, e le due linee del grafico.

Una scheda mostra le **soglie attive** (le sei di `comune.py` più `LIMITE_PESO`). All'apertura
sono i valori predefiniti; il pulsante **Leggi da comune.py** apre il selettore file, tu scegli
`comune.py` — e se vuoi anche `servoscala.py` per il limite di peso — e la demo
li rilegge. I valori diversi da quelli predefiniti restano evidenziati in ambra, così vedi a
colpo d'occhio cosa hai cambiato. **È solo lettura**: il progetto non viene mai scritto e la
modifica vive in memoria fino alla chiusura della pagina o al pulsante *Ripristina*.

È costruito perché **nulla si sposti**: le etichette sono fisse e cambiano solo i valori, i
numeri sono a spaziatura fissa e allineati a destra così le cifre non ballano, e il registro
MQTT ha righe di altezza costante con **il messaggio più recente sempre in cima** — niente
scorrimento automatico da rincorrere. Da lì, `Apri in una finestra` lo stacca in una finestra
separata, comoda su un secondo schermo mentre nella prima resta la scena 3D.

---

## Il documentario

`documentario_SV01.html` mette in scena una sequenza fissa di **2 minuti e 41 secondi**, con la
grafica 3D vera e la regia scritta: titolo, presentazione dell'impianto, salita dal piano terra
al terzo, l'intervento di una costa di sicurezza, l'arrivo, l'attesa che scatti la regola R2 con
il contatore dell'inattività a schermo, e infine la chiamata dal primo piano con la discesa.

Il fuoco è sui messaggi. A ogni messaggio chiave l'immagine **si congela** e il payload viene
ingrandito al centro, con i campi rilevanti evidenziati, il topic, il verso della comunicazione
e il QoS. Sono cinque fermi immagine:

| tempo | messaggio | cosa evidenzia |
|---|---|---|
| 00:36 | `servoscala/SV01/evento` | `tipo`, `codice_errore`, `descrizione` — la costa di sicurezza |
| 01:08 | `servoscala/SV01/corsa` | `peso_kg`, `assorbimento_medio`, i piani, `durata_s` |
| 01:44 | `manager/notifica` | `tipo: benessere` — la regola R2 che scatta |
| 01:57 | `chiamata/ST02/pulsante` | `piano`, `premuto` — il sensore |
| 02:04 | `chiamata/ST02/comando/led` | `valore: in_arrivo` — l'attuatore |

Durante il fermo immagine la simulazione è davvero in pausa, e al risveglio il tempo trascorso
viene restituito al contatore dell'inattività: i secondi del fermo immagine non falsano R2.

**Per ottenere il file video**: premi `● Registra e scarica`. La sequenza parte da sola e alla
fine il browser scarica un `documentario_SV01.webm` (1920×1080, 30 fps). Tutto quello che vedi nel
fotogramma è composto su un unico canvas, sovrimpressioni comprese, quindi finisce nel video; la
barra dei pulsanti in basso è fuori dal fotogramma e non viene registrata. Per convertirlo in MP4:

    ffmpeg -i documentario_SV01.webm -c:v libx264 -crf 20 -pix_fmt yuv420p documentario_SV01.mp4

---

## Il portale di assistenza

`assistenza_flotta.html` mostra cosa può offrire un servizio di manutenzione quando
gli impianti sono connessi: **24 mesi di storico** per ciascun twin, con i soli
indicatori che servono a capire lo stato di un impianto.

- ore di lavoro, corse effettuate, andamento mensile con la stagionalità estiva
- guasti per codice (`E01` emergenza, `E07` anomalia, `E12` sovraccarico) e **MTBF in giorni**
- fermo macchina e **disponibilità mensile** contro lo SLA contrattuale
- **usura stimata** dall'ultimo tagliando, con gli azzeramenti a ogni intervento
- **manutenzioni previste vs realmente eseguite**, ritardo di ogni intervento, puntualità
- indice di salute e raccomandazioni automatiche

I tre impianti raccontano tre situazioni diverse:

| | stato | storia |
|---|---|---|
| **SV01** | operativo | manutenzioni puntuali, un solo guasto in 12 mesi, disponibilità 99,8% |
| **SV02** | manutenzione programmata | un tagliando non eseguito, guasti quadruplicati nei 14 mesi scoperti, disponibilità sotto SLA; situazione in rientro dopo l'intervento di recupero |
| **SV03** | manutenzione urgente | impianto del 2017 poco usato ma con guasti ricorrenti, MTBF 23 giorni, tagliando scaduto da 47 giorni, e le segnalazioni di inattività prolungata della regola R2 |

Lo storico è generato con un seme fisso: gli stessi numeri a ogni apertura.

---

## Documentazione

Il codice Python è spiegato riga per riga in [`../GUIDA_CODICE.md`](../GUIDA_CODICE.md);
topic e payload sono progettati in [`../docs/02_progettazione_topic.md`](../docs/02_progettazione_topic.md).

## Legame con il progetto MQTT

Le demo **non inventano un modello dati**: pubblicano esattamente i payload di
`servoscala.py` e `stazione_chiamata.py`, sugli stessi topic di
`comune.py`, e applicano le regole R2–R6 di `manager.py` con le soglie
di `comune.py`.

    servoscala/SV0n/telemetria          stato, piano_corrente, livello_batteria,
                                        assorbimento_motore, contatore_corse, ...
    servoscala/SV0n/corsa               peso_kg, assorbimento_medio, piano_partenza/arrivo
    servoscala/SV0n/evento              E01 emergenza · E07 errore · E12 sovraccarico
    servoscala/SV0n/comando/ricarica    lenta | veloce            (attuatore)
    servoscala/SV0n/comando/indicatore  operativo | manutenzione_necessaria
    chiamata/ST0n/pulsante              chiamata di piano         (sensore)
    chiamata/ST0n/comando/led           libero | in_arrivo | occupato
    manager/notifica                    benessere · manutenzione programmata/urgente

Il riquadro in basso a destra dei twin è il traffico MQTT in tempo reale: si vede la
catena completa **sensore → manager → attuatore** a ogni chiamata di piano.

Le soglie di `comune.py` sono volutamente compresse per rendere la demo osservabile in
pochi minuti (8 corse, usura 45). Il portale le riporta ai valori di un contratto reale:
tagliando ogni 6 mesi o 2 500 corse, soglia di usura 12 500, SLA di disponibilità 98,5%.

## Estensione: pilotare la scena dal broker reale

Serve un listener WebSocket sul broker — in `mosquitto.conf`:

    listener 9001 127.0.0.1
    protocol websockets

poi in pagina si aggiunge `mqtt.js` e ci si iscrive a `servoscala/+/telemetria`,
usando `piano_corrente` per muovere la piattaforma invece della simulazione interna.
Con più device attivi (`--id SV01 --piani 3`, `--id SV02 --piani 2`, …) il portale
diventa una vera console di flotta.
