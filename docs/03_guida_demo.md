# Passo 7 — Guida alla demo end-to-end

Come avviare tutto il sistema insieme e mostrare i comportamenti richiesti dalla traccia.

## Prerequisiti
- Broker Mosquitto attivo (è già un servizio di Windows sulla porta 1883).
- Libreria installata: `py -m pip install -r requirements.txt`.

> **Se usi PyCharm**, lancia i programmi dalla scheda **Terminal** in basso, non dal
> pulsante *Run*: la finestra di Run non inoltra `CTRL+C` al processo, quindi non
> riusciresti a fermare un singolo programma. Con il Terminal apri più schede col `+`
> e ogni scheda è un vero PowerShell. In alternativa, nella configurazione di Run
> spunta *Emulate terminal in output console*.

L'**ordine di avvio** conta: il manager deve essersi iscritto prima che i device
comincino a pubblicare, altrimenti i primi messaggi vanno perduti (MQTT non conserva
il passato per chi si iscrive dopo).

## Disposizione dei terminali

Apri più finestre/terminali, tutti nella cartella del progetto. Suggerimento:
una per il manager, una per le notifiche, e una per ciascun device.

**Terminale A — Manager (il cervello + dashboard):**
```powershell
py manager.py
```

**Terminale B — Notifiche (benessere e manutenzione):**
```powershell
py ascolta.py
```

**Terminali C, D — Servoscala (la flotta):**
```powershell
py servoscala.py --id SV01 --edificio "Palazzina A" --piani 4
py servoscala.py --id SV02 --edificio "Palazzina B" --piani 6
```

**Terminale E — Stazione di chiamata:**
```powershell
py stazione_chiamata.py --id ST01 --piano 2
```

Nel Terminale A vedrai la dashboard aggiornarsi; nel Terminale B compariranno
le notifiche man mano che il manager prende decisioni.

## Cosa osservare (scenari da mostrare all'esame)

1. **Raccolta dati e stato (R1).** Nella dashboard del manager compaiono SV01 e
   SV02 con stato, batteria, corse, usura aggiornati in tempo reale.

2. **Supporto a n device.** Avvia un terzo servoscala (`--id SV03`) mentre il
   sistema gira: il manager lo rileva automaticamente, senza modifiche al codice
   (merito dei wildcard `+` nelle sottoscrizioni).

3. **Ricarica intelligente (R4).** Quando un servoscala è attivo (corse recenti),
   il manager imposta la ricarica su `veloce`; nei periodi di inattività torna a
   `lenta`. Lo vedi nella colonna `ricarica` e nei messaggi del device.

4. **Benessere (R2).** La regola segnala un servoscala che non fa corse da più di
   `SOGLIA_INATTIVITA_S` (default 25 s). Attenzione: con l'intervallo predefinito di
   3 s il device fa una corsa ogni ~6 secondi, quindi una pausa di 25 s da sola
   non si presenta quasi mai — l'attesa media è di circa **18 minuti**. Due modi
   per vederla scattare:

   - **Spegni solo il device.** Aspetta che nel Terminale A compaia almeno una corsa,
     poi premi `CTRL+C` **solo nel Terminale C**. Il manager resta vivo, si accorge
     del silenzio e dopo ~25 s pubblica la notifica nel Terminale B. È anche lo
     scenario realistico: l'impianto ha smesso di essere usato.
   - **Allunga il ciclo del device.** Avvialo con `--intervallo 12`: le pause naturali
     superano la soglia e la notifica arriva in circa un minuto.

   Il punto da capire è che la notifica la genera il **manager**, non il device: se
   spegni il manager (o un lanciatore che lo tiene come figlio) la notifica non può
   più arrivare, per definizione.

5. **Manutenzione programmata (R5).** Lascia girare finché le corse superano
   `WARNING_CORSE` (o le anomalie superano `WARNING_ANOMALIE`): arriva l'avviso
   di manutenzione programmata.

6. **Manutenzione urgente (R6).** Quando l'usura stimata supera `ALARM_USURA`
   (o le anomalie raggiungono `ALARM_ANOMALIE`): arriva l'alert urgente E
   l'indicatore di bordo del device passa a `manutenzione_necessaria`
   (colonna `display` nella dashboard).

7. **Attuazione sulla stazione.** Quando premi-virtualmente il pulsante (lo fa
   da sola la stazione), il manager accende il LED `in_arrivo` su quella stazione.

> Suggerimento per accelerare la demo: abbassa le soglie in `comune.py` e usa un
> `--intervallo` piccolo sui device (es. `--intervallo 1`) per far accadere tutto
> più in fretta.

## Mappa rapida dei comportamenti → file

| Comportamento | Dove nel codice |
|---|---|
| Stato di ogni device | `manager.py` → `_stato` + `_on_message` (R1) |
| Notifica benessere | `manager.py` → `_valuta_regole` (R2) |
| Stima usura (peso↔assorbimento) | `manager.py` → `_on_message`, ramo `corsa` (R3) |
| Modalità di ricarica | `manager.py` → `_valuta_regole` (R4) |
| Manutenzione WARNING / ALARM | `manager.py` → `_valuta_regole` (R5, R6), soglie in `comune.py` |
| Topic e valori ammessi | `comune.py` |
