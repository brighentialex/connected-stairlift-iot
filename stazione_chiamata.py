"""
STAZIONE DI CHIAMATA DI PIANO - il secondo device, molto piu' semplice.

  - SENSORE:   il pulsante di chiamata (quando qualcuno preme, lo segnala);
  - ATTUATORE: un LED multicolore di stato (libero / in arrivo / occupato),
               comandato dal manager.

Ogni stazione e' installata a un piano e ha un ID univoco.

Avvio (un terminale per ogni stazione):
    py stazione_chiamata.py --id ST01 --piano 0
    py stazione_chiamata.py --id ST02 --piano 2

Ferma con CTRL+C.
"""

import argparse
import random
import time

import paho.mqtt.client as mqtt

import comune as C


class StazioneChiamata:

    def __init__(self, device_id, piano, intervallo):
        self.device_id = device_id
        self.piano = piano
        self.intervallo = intervallo
        self.led = C.LED_LIBERO   # stato dell'attuatore, lo comanda il manager

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=device_id)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    # ------------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            print(f"[{self.device_id}] Connessione fallita (codice {reason_code}).")
            return
        print(f"[{self.device_id}] Connesso (piano {self.piano}).")
        client.subscribe(C.chiamata_cmd_led(self.device_id))   # un solo comando da ascoltare

    def _on_message(self, client, userdata, msg):
        """Unico messaggio in arrivo: il manager decide il colore del LED."""
        self.led = C.leggi(msg).get("valore")
        print(f"[{self.device_id}] >> LED ora: '{self.led}'")

    # ------------------------------------------------------------------
    def _premi_pulsante(self):
        """Simula una persona che chiama il servoscala da questo piano."""
        C.pubblica(self.client, C.chiamata_pulsante(self.device_id), {
            "device_id": self.device_id,
            "piano": self.piano,
            "premuto": True,
            "timestamp": C.adesso(),
        }, qos=1)   # una chiamata non si puo' perdere
        print(f"[{self.device_id}] Pulsante premuto al piano {self.piano}.")

    # ------------------------------------------------------------------
    def avvia(self):
        print(f"[{self.device_id}] Avvio stazione al piano {self.piano}. (CTRL+C per fermare)")
        self.client.connect(C.BROKER_HOST, C.BROKER_PORT, C.KEEPALIVE)
        self.client.loop_start()
        time.sleep(0.5)

        try:
            while True:
                if random.random() < 0.4:   # 40%: qualcuno preme
                    self._premi_pulsante()
                time.sleep(self.intervallo)
        except KeyboardInterrupt:
            print(f"\n[{self.device_id}] Spegnimento.")
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Emulatore di una stazione di chiamata di piano (MQTT).")
    p.add_argument("--id", default="ST01", help="ID univoco della stazione")
    p.add_argument("--piano", type=int, default=0, help="Piano dove e' installata")
    p.add_argument("--intervallo", type=float, default=5.0, help="Secondi fra una possibile pressione e la successiva")
    a = p.parse_args()

    StazioneChiamata(a.id, a.piano, a.intervallo).avvia()
