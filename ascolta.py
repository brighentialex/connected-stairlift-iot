"""
ASCOLTA - file OPZIONALE, serve solo a rendere piu' bella la demo.

Si iscrive a 'manager/notifica' e stampa in una finestra dedicata solo le
notifiche e gli allarmi, senza il rumore della telemetria. Tienilo aperto in
un terminale a parte durante la presentazione.

E' anche il subscriber MQTT piu' semplice possibile: 20 righe, buono da
mostrare se il prof chiede "come si scrive un client che ascolta e basta".

Avvio:
    py ascolta.py
"""

import paho.mqtt.client as mqtt

import comune as C


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[NOTIFICHE] In ascolto su '{C.NOTIFICA}'. (CTRL+C per fermare)")
    client.subscribe(C.NOTIFICA)


def on_message(client, userdata, msg):
    d = C.leggi(msg)
    print(f"  >>> [{d['tipo'].upper()}] {d['device_id']} @ {d['timestamp']}")
    print(f"      {d['messaggio']}")


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ascolta-notifiche")
client.on_connect = on_connect
client.on_message = on_message
client.connect(C.BROKER_HOST, C.BROKER_PORT, C.KEEPALIVE)

# loop_forever(): qui NON serve fare altro mentre si ascolta, quindi possiamo
# bloccare il programma. E' la differenza con loop_start() usato negli altri file.
client.loop_forever()
