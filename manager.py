"""
MANAGER - il "cervello" del sistema (Data Collector & Manager).

Fa due cose, in parallelo:
  A) ASCOLTA tutti i device (grazie alle wildcard "+") e tiene aggiornata una
     struttura con lo stato di ognuno;
  B) ogni 4 secondi APPLICA cinque regole e, quando serve, invia comandi agli
     attuatori e pubblica notifiche.

LE CINQUE REGOLE (sono quelle della traccia d'esame):
  R1  Mantiene una struttura aggiornata dello stato di ogni servoscala.
  R2  Inattivita': nessuna corsa oltre la soglia -> notifica "benessere".
  R3  Per ogni corsa correla peso e assorbimento -> stima dell'usura.
  R4  Sceglie la modalita' di ricarica (lenta/veloce) in base a uso e batteria.
  R5  Troppe corse o anomalie ripetute -> manutenzione PROGRAMMATA (warning).
  R6  Usura oltre il limite o troppe anomalie -> manutenzione URGENTE (alarm)
      + indicatore di bordo su 'manutenzione_necessaria'.

Tutte le soglie stanno in comune.py, sezione 4.

Avvio:
    py manager.py

Ferma con CTRL+C.
"""

import time
from datetime import datetime

import paho.mqtt.client as mqtt

import comune as C


class Manager:

    def __init__(self):
        self.servoscale = {}   # device_id -> dizionario di stato (questa e' la R1)
        self.stazioni = {}     # device_id -> ultima chiamata ricevuta

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="manager")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    # ==================================================================
    # CONNESSIONE E SOTTOSCRIZIONI
    # ==================================================================
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            print(f"[MANAGER] Connessione fallita (codice {reason_code}).")
            return
        print("[MANAGER] Connesso. Mi iscrivo a tutti i device...")
        # Quattro iscrizioni con "+" al posto dell'ID: bastano queste per
        # ricevere da un numero QUALSIASI di device, anche accesi dopo.
        client.subscribe(C.SUB_TELEMETRIA)
        client.subscribe(C.SUB_CORSA)
        client.subscribe(C.SUB_EVENTO)
        client.subscribe(C.SUB_PULSANTE)

    # ==================================================================
    # R1 - LA STRUTTURA DI STATO
    # ==================================================================
    def _stato(self, device_id):
        """Restituisce lo stato del device; se e' la prima volta, lo crea."""
        if device_id not in self.servoscale:
            self.servoscale[device_id] = {
                # --- dati che arrivano dalla telemetria ---
                "edificio": "?",
                "stato": "?",
                "piano_corrente": 0,
                "batteria": None,
                "corse": 0,
                "ricarica": "?",
                "indicatore": "?",
                "ultimo_aggiornamento": None,
                # --- dati calcolati dal manager ---
                "ultima_corsa": datetime.now(),   # parte da adesso alla prima comparsa
                "usura": 0.0,                     # R3: somma degli assorbimenti
                "anomalie": 0,
                # --- memoria delle decisioni gia' prese (per non ripeterle) ---
                "benessere_notificato": False,
                "ricarica_comandata": None,
                "manutenzione": "nessuno",        # nessuno -> warning -> alarm
            }
        return self.servoscale[device_id]

    # ==================================================================
    # RICEZIONE MESSAGGI - unica callback, smista in base al topic
    # ==================================================================
    def _on_message(self, client, userdata, msg):
        d = C.leggi(msg)
        categoria = msg.topic.split("/")[-1]   # es. "servoscala/SV01/corsa" -> "corsa"

        if categoria == "telemetria":
            s = self._stato(d["device_id"])
            s["edificio"] = d["edificio"]
            s["stato"] = d["stato"]
            s["piano_corrente"] = d["piano_corrente"]
            s["batteria"] = d["livello_batteria"]
            s["corse"] = d["contatore_corse"]
            s["ricarica"] = d["modalita_ricarica"]
            s["indicatore"] = d["indicatore_stato"]
            s["ultimo_aggiornamento"] = d["timestamp"]

        elif categoria == "corsa":
            # R3: peso e assorbimento sono correlati (piu' peso -> piu' Ampere),
            # quindi accumulare gli assorbimenti = stimare l'usura del motore.
            s = self._stato(d["device_id"])
            s["usura"] = round(s["usura"] + d["assorbimento_medio"], 1)
            s["ultima_corsa"] = datetime.now()
            s["benessere_notificato"] = False   # c'e' stata attivita': azzera l'avviso
            print(f"[MANAGER] Corsa da {d['device_id']}: {d['peso_kg']} kg, "
                  f"assorb. {d['assorbimento_medio']} A "
                  f"(piano {d['piano_partenza']}->{d['piano_arrivo']})")

        elif categoria == "evento":
            s = self._stato(d["device_id"])
            s["anomalie"] += 1
            print(f"[MANAGER] EVENTO da {d['device_id']}: {d['tipo']} "
                  f"[{d['codice_errore']}] {d['descrizione']} "
                  f"(anomalie totali: {s['anomalie']})")

        elif categoria == "pulsante":
            self.stazioni[d["device_id"]] = {"piano": d["piano"], "ultima_chiamata": C.adesso()}
            print(f"[MANAGER] Chiamata dalla stazione {d['device_id']} (piano {d['piano']}).")
            # Attuazione immediata: accendiamo il LED 'in arrivo'.
            self._comando(C.chiamata_cmd_led(d["device_id"]), C.LED_IN_ARRIVO)

    # ==================================================================
    # INVIO DI COMANDI E NOTIFICHE
    # ==================================================================
    def _comando(self, topic, valore):
        """Comando a un attuatore. QoS 1: un comando non si puo' perdere."""
        C.pubblica(self.client, topic, {"valore": valore, "timestamp": C.adesso()}, qos=1)

    def _notifica(self, tipo, device_id, messaggio):
        """Notifica per l'operatore, su un unico topic 'manager/notifica'."""
        C.pubblica(self.client, C.NOTIFICA, {
            "tipo": tipo,
            "device_id": device_id,
            "messaggio": messaggio,
            "timestamp": C.adesso(),
        }, qos=1)
        print(f"[MANAGER][NOTIFICA] {tipo.upper()} - {device_id}: {messaggio}")

    # ==================================================================
    # LE REGOLE - girano ogni 4 secondi, su ogni servoscala conosciuto
    # ==================================================================
    def _valuta_regole(self):
        # list(...) perche' i messaggi arrivano da un altro thread e potrebbero
        # aggiungere un device mentre stiamo ciclando.
        for sid, s in list(self.servoscale.items()):

            fermo_da = (datetime.now() - s["ultima_corsa"]).total_seconds()

            # --- R2: BENESSERE ---
            # Un servoscala usato ogni giorno che smette di funzionare puo'
            # voler dire che la persona sta male. Avvisiamo una volta sola.
            if fermo_da > C.SOGLIA_INATTIVITA_S and not s["benessere_notificato"]:
                self._notifica(C.NOTIFICA_BENESSERE, sid,
                               f"Nessuna corsa da {int(fermo_da)} s: da verificare.")
                s["benessere_notificato"] = True

            # --- R4: RICARICA INTELLIGENTE ---
            # Se c'e' stata attivita' da poco siamo in una fascia di uso: teniamo
            # la batteria pronta (veloce). Altrimenti carichiamo piano, che
            # preserva la batteria. Eccezione: batteria troppo bassa -> veloce.
            #   (In un impianto vero il manager imparerebbe le fasce orarie
            #    dallo storico di giorni; qui la demo dura pochi minuti.)
            in_uso = fermo_da < 12
            batteria_scarica = s["batteria"] is not None and s["batteria"] < C.SOGLIA_BATTERIA_BASSA
            desiderata = C.RICARICA_VELOCE if (in_uso or batteria_scarica) else C.RICARICA_LENTA

            if desiderata != s["ricarica_comandata"]:   # comandiamo solo se CAMBIA
                self._comando(C.servoscala_cmd_ricarica(sid), desiderata)
                s["ricarica_comandata"] = desiderata
                print(f"[MANAGER] Ricarica di {sid} impostata su '{desiderata}'.")

            # --- R5 e R6: MANUTENZIONE PREDITTIVA ---
            # Prima decidiamo il livello, poi agiamo solo se e' PEGGIORATO.
            if s["usura"] > C.ALARM_USURA or s["anomalie"] >= C.ALARM_ANOMALIE:
                livello = "alarm"
            elif s["corse"] > C.WARNING_CORSE or s["anomalie"] >= C.WARNING_ANOMALIE:
                livello = "warning"
            else:
                livello = "nessuno"

            gravita = {"nessuno": 0, "warning": 1, "alarm": 2}
            if gravita[livello] > gravita[s["manutenzione"]]:
                if livello == "warning":
                    self._notifica(C.NOTIFICA_MANUTENZIONE_PROGRAMMATA, sid,
                                   f"WARNING: corse={s['corse']}, anomalie={s['anomalie']}. "
                                   f"Pianificare manutenzione.")
                else:
                    self._notifica(C.NOTIFICA_MANUTENZIONE_URGENTE, sid,
                                   f"ALARM: usura={s['usura']}, anomalie={s['anomalie']}. "
                                   f"Manutenzione urgente.")
                    # R6: accendiamo la spia sul display di bordo del device.
                    self._comando(C.servoscala_cmd_indicatore(sid), C.INDICATORE_MANUTENZIONE)
                s["manutenzione"] = livello

    # ==================================================================
    # DASHBOARD TESTUALE
    # ==================================================================
    def _dashboard(self):
        print("\n" + "=" * 78)
        print(f"DASHBOARD MANAGER - {C.adesso()}")
        print("=" * 78)
        if not self.servoscale:
            print("(nessun servoscala ancora rilevato)")
        for sid, s in sorted(self.servoscale.items()):
            batt = f"{s['batteria']}%" if s["batteria"] is not None else "?"
            print(f" {sid} [{s['edificio']}] stato={s['stato']:<13} batt={batt:<6} "
                  f"corse={s['corse']} usura={s['usura']:<5} "
                  f"ricarica={s['ricarica']:<6} display={s['indicatore']:<22} "
                  f"manut={s['manutenzione']}")
        for stid, st in sorted(self.stazioni.items()):
            print(f" {stid} (stazione) piano={st['piano']} ultima_chiamata={st['ultima_chiamata']}")
        print("=" * 78 + "\n")

    # ==================================================================
    # CICLO PRINCIPALE
    # ==================================================================
    def avvia(self):
        print("[MANAGER] Avvio Data Collector & Manager. (CTRL+C per fermare)")
        self.client.connect(C.BROKER_HOST, C.BROKER_PORT, C.KEEPALIVE)

        # loop_start(): la rete gira in un thread a parte, cosi' i messaggi
        # continuano ad arrivare MENTRE il ciclo qui sotto valuta le regole.
        self.client.loop_start()

        try:
            while True:
                time.sleep(4)
                self._valuta_regole()
                self._dashboard()
        except KeyboardInterrupt:
            print("\n[MANAGER] Spegnimento.")
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    Manager().avvia()
