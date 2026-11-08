# Modalità team

Per più persone sullo stesso server. Il desktop non cambia: questa modalità si accende solo con `TRADUCO_MODE=team`.

## Avvio con Docker

```bash
TRADUCO_OIDC_CLIENT_SECRET=<segreto del client> \
TRADUCO_SESSION_SECRET=$(openssl rand -hex 32) \
KEYCLOAK_ADMIN_PASSWORD=<password> \
docker compose --profile team up
```

1. Apri Keycloak (http://localhost:8080), crea il realm `traduco` e un client `traduco` (confidenziale, flusso "standard", redirect `http://localhost:8000/api/auth/callback`).
2. Crea i ruoli `reviewer`, `author`, `admin` e assegnali agli utenti; fai comparire i ruoli nel token (il predefinito di `TRADUCO_OIDC_ROLES_CLAIM` è `roles`; il compose usa `realm_access.roles`, dove Keycloak mette i ruoli del realm, e va aggiunto il mapper al token).
3. Apri http://localhost:8000: ti manda al login.

Con un altro provider OIDC imposta `TRADUCO_OIDC_ISSUER`, `TRADUCO_OIDC_CLIENT_ID` e `TRADUCO_OIDC_CLIENT_SECRET`.

## Provarlo senza Keycloak

```bash
cd backend && uv run python ../tools/dev-idp.py          # accesso di prova su http://127.0.0.1:9100
# in un altro terminale, dalla cartella del progetto:
TRADUCO_MODE=team TRADUCO_OIDC_ISSUER=http://127.0.0.1:9100 TRADUCO_OIDC_CLIENT_SECRET=x \
TRADUCO_SESSION_SECRET=$(openssl rand -hex 32) ./start.sh
```

Scegli l'utente da una lista (Carla amministratrice, Anna ed Elena autrici, Bruno revisore), senza password: **solo per sviluppo**. Per essere due persone insieme usa `http://localhost:8000` in una finestra e `http://127.0.0.1:8000` in una finestra privata (i cookie sono per indirizzo).

## Cosa cambia

- **Ruoli**: *autore* scrive e configura, *revisore* corregge e approva (un autore non approva), *amministratore* fa tutto, compreso creare progetti e leggere il registro.
- **Blocchi**: chi modifica una sezione la tiene; gli altri la vedono in sola lettura con il nome di chi la sta modificando. Il blocco scade da solo dopo 45 secondi senza attività.
- **Presenza**: le iniziali delle altre persone nel progetto compaiono in alto.
- **Registro**: `GET /api/audit?project=…&action=…` (amministratore).

## Cosa non è ancora fatto

Blocchi e presenza stanno nella memoria di un solo processo; PostgreSQL e Valkey (coda lavori) non ci sono. Il profilo `team` non è stato provato con Keycloak e vLLM veri.
