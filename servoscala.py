"""
SERVOSCALA - l'emulatore del device principale (Smart Object).

Questo programma FINGE di essere un servoscala reale:
  - SENSORI:  genera stato, peso trasportato, assorbimento motore, batteria,
              contatore corse, eventi diagnostici... e li PUBBLICA via MQTT;
  - ATTUATORI: ASCOLTA i comandi del manager e li applica (modalita' di
              ricarica e indicatore di stato di bordo).

Avvio (un terminale per ogni servoscala della flotta):
    py servoscala.py --id SV01 --edificio "Palazzina A" --piani 4
    py servoscala.py --id SV02 --edificio "Palazzina B" --piani 6

Ferma con CTRL+C.
"""

import argparse
import random
import time

import paho.mqtt.client as mqtt

import comune as C


LIMITE_PESO = 120.0   # kg: oltre questo valore scatta il sovraccarico


class Servoscala:

    def __init__(self, device_id, edificio, piani, intervallo):
        # --- Identita' del device ---
        self.device_id = device_id
        self.edificio = edificio
        self.piani = piani             # piani serviti (0 = piano terra)
        self.intervallo = intervallo   # secondi fra un ciclo di simulazione e il successivo

        # --- Stato interno: e' quello che i "sensori" leggono ---
        self.stato = C.STATO_IDLE
        self.piano_corrente = 0
        self.batteria = round(random.uniform(70, 100), 1)
        self.assorbimento = 0.0        # Ampere; 0 quando e' fermo
        self.corse = 0

        # --- Stato degli attuatori: lo decide il manager ---
        self.ricarica = C.RICARICA_LENTA
        self.indicatore = C.INDICATORE_OPERATIVO

        # --- Client MQTT ---
        # CallbackAPIVersion.VERSION2 = la firma nuova delle callback di paho 2.x.
        # client_id deve essere UNICO sul broker: usiamo l'ID del device.
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=device_id)
        self.client.on_connect = self._on_connect   # non la chiamiamo noi: la chiama paho
        self.client.on_message = self._on_message

    # ------------------------------------------------------------------
    # CALLBACK: funzioni che NON chiamiamo mai noi.
    # Le registriamo e sara' la libreria a invocarle quando succede qualcosa.
    # ------------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Scatta quando il broker risponde alla connessione."""
        if reason_code != 0:
            print(f"[{self.device_id}] Connessione fallita (codice {reason_code}).")
            return
        print(f"[{self.device_id}] Connesso al broker.")
        # Ci si iscrive QUI, non prima: se la connessione cade e paho la
        # ripristina, on_connect riparte e le iscrizioni si rifanno da sole.
        client.subscribe(C.servoscala_cmd_indicatore(self.device_id))
        client.subscribe(C.servoscala_cmd_ricarica(self.device_id))

    def _on_message(self, client, userdata, msg):
        """Scatta a ogni messaggio ricevuto: qui arrivano i comandi del manager."""
        valore = C.leggi(msg).get("valore")

        if msg.topic == C.servoscala_cmd_ricarica(self.device_id):
            self.ricarica = valore
            print(f"[{self.device_id}] >> Comando ricarica: '{valore}'")

        elif msg.topic == C.servoscala_cmd_indicatore(self.device_id):
            self.indicatore = valore
            print(f"[{self.device_id}] >> Comando indicatore: display su '{valore}'")

    # ------------------------------------------------------------------
    # PUBBLICAZIONE
    # ------------------------------------------------------------------
    def _pubblica_telemetria(self):
        """Fotografia completa dello stato del device."""
        C.pubblica(self.client, C.servoscala_telemetria(self.device_id), {
            "device_id": self.device_id,
            "edificio": self.edificio,
            "stato": self.stato,
            "piano_corrente": self.piano_corrente,
            "livello_batteria": round(self.batteria, 1),
            "assorbimento_motore": round(self.assorbimento, 2),
            "contatore_corse": self.corse,
            "modalita_ricarica": self.ricarica,
            "indicatore_stato": self.indicatore,
            "timestamp": C.adesso(),
        }, qos=0)   # flusso continuo: se salta un campione, pazienza

    def _pubblica_evento(self, tipo, codice, descrizione):
        """Anomalia diagnostica: emergenza, sovraccarico o errore."""
        C.pubblica(self.client, C.servoscala_evento(self.device_id), {
            "device_id": self.device_id,
            "tipo": tipo,
            "codice_errore": codice,
            "descrizione": descrizione,
            "timestamp": C.adesso(),
        }, qos=1)   # importante: consegna garantita
        print(f"[{self.device_id}] !! EVENTO: {tipo} ({descrizione})")

    # ------------------------------------------------------------------
    # SIMULAZIONE DEL COMPORTAMENTO FISICO
    # ------------------------------------------------------------------
    def _esegui_corsa(self):
        """Una persona sale a bordo e il servoscala si sposta di piano."""
        # Peso del passeggero: quasi sempre normale, ogni tanto eccessivo.
        if random.random() < 0.12:
            peso = round(random.uniform(120, 150), 1)              # caso anomalo
        else:
            peso = round(max(35.0, random.gauss(75, 12)), 1)       # caso normale

        # Sovraccarico: il device NON parte e segnala l'evento.
        if peso > LIMITE_PESO:
            self._pubblica_evento(C.EVENTO_SOVRACCARICO, "E12",
                                  f"Peso {peso} kg oltre il limite di {LIMITE_PESO} kg")
            return

        # Piano di arrivo, diverso da quello attuale.
        partenza = self.piano_corrente
        arrivo = partenza
        while arrivo == partenza:
            arrivo = random.randint(0, self.piani)

        # Parte: l'assorbimento del motore cresce col peso.
        # E' questa correlazione che il manager usera' per stimare l'usura.
        self.stato = C.STATO_SALITA if arrivo > partenza else C.STATO_DISCESA
        self.assorbimento = round(2.0 + peso * 0.04 + random.uniform(-0.2, 0.2), 2)
        self._pubblica_telemetria()     # si vede lo stato "in movimento"

        durata = abs(arrivo - partenza) * random.uniform(4, 7)
        time.sleep(min(durata, 3))      # accorciato per non rallentare la demo

        # Effetti della corsa.
        self.batteria = max(0.0, self.batteria - random.uniform(0.4, 1.2))
        self.corse += 1
        self.piano_corrente = arrivo

        C.pubblica(self.client, C.servoscala_corsa(self.device_id), {
            "device_id": self.device_id,
            "peso_kg": peso,
            "assorbimento_medio": self.assorbimento,
            "piano_partenza": partenza,
            "piano_arrivo": arrivo,
            "durata_s": round(durata, 1),
            "timestamp": C.adesso(),
        }, qos=1)
        print(f"[{self.device_id}] Corsa #{self.corse}: {peso} kg, "
              f"piano {partenza}->{arrivo}, assorb. {self.assorbimento} A")

        # Torna a riposo.
        self.stato = C.STATO_IDLE
        self.assorbimento = 0.0

    def _ricarica_batteria(self):
        """Quando e' fermo il servoscala ricarica, alla velocita' decisa dal manager."""
        if self.batteria < 100:
            incremento = 0.8 if self.ricarica == C.RICARICA_VELOCE else 0.3
            self.batteria = min(100.0, self.batteria + incremento)

    def _forse_guasto(self):
        """Ogni tanto un guasto raro: 2% errore, 1% emergenza."""
        r = random.random()
        if r < 0.02:
            self._pubblica_evento(C.EVENTO_ERRORE, "E07", "Anomalia generica del sistema")
        elif r < 0.03:
            self._pubblica_evento(C.EVENTO_EMERGENZA, "E01", "Pulsante di emergenza premuto")

    # ------------------------------------------------------------------
    # CICLO PRINCIPALE
    # ------------------------------------------------------------------
    def avvia(self):
        print(f"[{self.device_id}] Avvio in '{self.edificio}', {self.piani} piani. "
              f"(CTRL+C per fermare)")
        self.client.connect(C.BROKER_HOST, C.BROKER_PORT, C.KEEPALIVE)

        # loop_start() apre un THREAD in background che gestisce la rete: cosi'
        # il ciclo qui sotto continua a simulare MENTRE i comandi arrivano.
        # (loop_forever() invece bloccherebbe tutto: va bene solo per chi ascolta e basta.)
        self.client.loop_start()
        time.sleep(0.5)   # un attimo per completare la connessione

        try:
            while True:
                if random.random() < 0.5:
                    self._esegui_corsa()      # 50%: qualcuno lo usa
                else:
                    self._ricarica_batteria() # 50%: e' fermo e ricarica

                self._forse_guasto()
                self._pubblica_telemetria()
                time.sleep(self.intervallo)
        except KeyboardInterrupt:
            print(f"\n[{self.device_id}] Spegnimento.")
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Emulatore di un servoscala (Smart Object MQTT).")
    p.add_argument("--id", default="SV01", help="ID univoco del device")
    p.add_argument("--edificio", default="Palazzina A", help="Dove si trova")
    p.add_argument("--piani", type=int, default=4, help="Numero di piani serviti")
    p.add_argument("--intervallo", type=float, default=3.0, help="Secondi fra un ciclo e il successivo")
    a = p.parse_args()

    Servoscala(a.id, a.edificio, a.piani, a.intervallo).avvia()
