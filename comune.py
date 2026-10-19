"""
COMUNE.PY - tutto cio' che serve a piu' di un programma sta qui.

Contiene quattro cose, in quest'ordine:
  1. CONNESSIONE   -> indirizzo del broker MQTT
  2. TOPIC         -> come si chiamano i canali di comunicazione
  3. VALORI        -> le parole ammesse dentro i messaggi
  4. SOGLIE        -> i numeri che governano le decisioni del manager
  5. FUNZIONI      -> tre utility per data/ora e JSON

Perche' un file unico? Perche' cosi' se cambi una cosa (es. l'indirizzo del
broker) la cambi in UN posto solo e vale per tutti i programmi.
"""

import json
from datetime import datetime


# ===========================================================================
# 1. CONNESSIONE AL BROKER
# ===========================================================================

BROKER_HOST = "127.0.0.1"   # il broker Mosquitto gira sul tuo stesso PC
BROKER_PORT = 1883          # porta standard MQTT (non cifrata)
KEEPALIVE = 60              # secondi: ogni quanto il client dice al broker "sono vivo"


# ===========================================================================
# 2. TOPIC MQTT
#
# Un topic e' l'indirizzo di un canale: chi pubblica scrive su un topic,
# chi e' interessato si iscrive a quel topic. Il broker fa da smistatore:
# i device non si parlano MAI direttamente fra loro.
#
# Convenzione dei nomi, a livelli separati da "/":
#     <tipo_device>/<id_device>/<categoria>[/<dettaglio>]
#
# Le costruiamo con delle funzioni cosi' non c'e' rischio di scrivere
# "telemetria" in due modi diversi in due file diversi.
# ===========================================================================

# --- Il servoscala PUBBLICA su questi (device -> manager) ---

def servoscala_telemetria(device_id):
    """Dati periodici: stato, piano, batteria, assorbimento, n. corse."""
    return f"servoscala/{device_id}/telemetria"


def servoscala_corsa(device_id):
    """Resoconto di una singola corsa: peso trasportato + assorbimento motore."""
    return f"servoscala/{device_id}/corsa"


def servoscala_evento(device_id):
    """Eventi diagnostici: emergenza, sovraccarico, codice di errore."""
    return f"servoscala/{device_id}/evento"


# --- Il servoscala ASCOLTA questi (manager -> device, per gli attuatori) ---

def servoscala_cmd_indicatore(device_id):
    """Comanda il display di bordo: 'operativo' o 'manutenzione_necessaria'."""
    return f"servoscala/{device_id}/comando/indicatore"


def servoscala_cmd_ricarica(device_id):
    """Comanda la modalita' di ricarica batteria: 'lenta' o 'veloce'."""
    return f"servoscala/{device_id}/comando/ricarica"


# --- La stazione di chiamata: uno in uscita, uno in entrata ---

def chiamata_pulsante(device_id):
    """La stazione segnala che qualcuno ha premuto (device -> manager)."""
    return f"chiamata/{device_id}/pulsante"


def chiamata_cmd_led(device_id):
    """Comanda il LED della stazione (manager -> device)."""
    return f"chiamata/{device_id}/comando/led"


# --- Il manager pubblica qui le sue notifiche/allarmi ---
NOTIFICA = "manager/notifica"


# --- SOTTOSCRIZIONI DEL MANAGER, con la WILDCARD "+" ---
#
# In MQTT il carattere "+" e' un jolly che sostituisce UN livello del topic.
# Cosi' il manager si iscrive una volta sola e riceve da TUTTI i device, senza
# sapere in anticipo quanti sono ne' come si chiamano.
#   "servoscala/+/telemetria"  cattura  servoscala/SV01/telemetria,
#                                       servoscala/SV02/telemetria, ecc.
SUB_TELEMETRIA = "servoscala/+/telemetria"
SUB_CORSA = "servoscala/+/corsa"
SUB_EVENTO = "servoscala/+/evento"
SUB_PULSANTE = "chiamata/+/pulsante"


# ===========================================================================
# 3. VALORI AMMESSI NEI MESSAGGI
#
# Sono normalissime stringhe, ma dando loro un nome il codice si legge meglio
# e l'editor ti avvisa se sbagli a scrivere (STATO_IDEL da' errore subito,
# "idel" invece passerebbe inosservato).
# ===========================================================================

# Stato operativo del servoscala
STATO_IDLE = "idle"
STATO_SALITA = "salita"
STATO_DISCESA = "discesa"
STATO_FUORI_SERVIZIO = "fuori_servizio"

# Tipi di evento diagnostico
EVENTO_EMERGENZA = "emergenza"
EVENTO_SOVRACCARICO = "sovraccarico"
EVENTO_ERRORE = "errore"

# Modalita' di ricarica (attuatore del servoscala)
RICARICA_LENTA = "lenta"
RICARICA_VELOCE = "veloce"

# Indicatore di stato a bordo (attuatore del servoscala)
INDICATORE_OPERATIVO = "operativo"
INDICATORE_MANUTENZIONE = "manutenzione_necessaria"

# LED della stazione di chiamata (attuatore della stazione)
LED_LIBERO = "libero"
LED_IN_ARRIVO = "in_arrivo"
LED_OCCUPATO = "occupato"

# Tipi di notifica generati dal manager
NOTIFICA_BENESSERE = "benessere"
NOTIFICA_MANUTENZIONE_PROGRAMMATA = "manutenzione_programmata"
NOTIFICA_MANUTENZIONE_URGENTE = "manutenzione_urgente"


# ===========================================================================
# 4. SOGLIE DELLE DECISIONI DEL MANAGER
#
# Tutti i "numeri magici" stanno qui: cambiando questi valori cambi il
# comportamento del sistema senza toccare la logica.
# I valori sono volutamente piccoli per vedere qualcosa succedere in pochi
# minuti di demo. In un impianto vero sarebbero ore o giorni.
# ===========================================================================

SOGLIA_INATTIVITA_S = 25    # s senza corse -> notifica "benessere"
SOGLIA_BATTERIA_BASSA = 35  # % sotto cui ricaricare comunque veloce

WARNING_CORSE = 8           # corse oltre cui avvisare (manutenzione programmata)
WARNING_ANOMALIE = 3        # anomalie oltre cui avvisare

ALARM_USURA = 45.0          # usura stimata oltre cui allarmare (manutenzione urgente)
ALARM_ANOMALIE = 5          # anomalie oltre cui allarmare


# ===========================================================================
# 5. FUNZIONI DI UTILITA'
# ===========================================================================

def adesso():
    """Data e ora attuali in formato ISO 8601. Es: '2026-08-10T21:40:00'."""
    return datetime.now().isoformat(timespec="seconds")


def pubblica(client, topic, payload, qos=0):
    """
    Pubblica un dizionario Python come messaggio JSON.

    Serve json.dumps perche' MQTT trasporta testo/byte, non oggetti Python.
    QoS 0 = "al massimo una volta" (veloce, puo' perdersi) -> telemetria.
    QoS 1 = "almeno una volta" (consegna garantita)        -> eventi e comandi.
    """
    client.publish(topic, json.dumps(payload), qos=qos)


def leggi(msg):
    """Trasforma il payload di un messaggio MQTT ricevuto in un dizionario."""
    return json.loads(msg.payload.decode("utf-8"))
