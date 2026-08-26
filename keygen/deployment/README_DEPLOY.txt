ISTRUZIONI DI INSTALLAZIONE COMPLETA (Web App + Server API)

Ecco come mettere online tutto il progetto (App 3D + Database).

CONTENUTO DELLO ZIP:
1. Cartella `web_app`: contiene l'editor 3D (l'interfaccia).
2. Cartella `php_server`: contiene gli script per il database (login, utenti, ecc).

PASSO 1: CARICAMENTO FILE
1. Accedi al tuo hosting (via FTP o File Manager).
2. Vai nella cartella pubblica (es. `public_html` o `www`).
3. Carica il **contenuto** della cartella `web_app` (quindi il file `index.html` e la cartella `assets`) direttamente nella `public_html`.
   (Se vuoi metterlo in una sottocartella, es. `virtuprinto.com/app`, crea la cartella `app` e metti lì i file).
4. Carica l'intera cartella `php_server` nella `public_html`.
   Dovresti avere quindi:
   - `public_html/index.html` (l'app)
   - `public_html/assets/...` (i file dell'app)
   - `public_html/php_server/...` (gli script PHP)

PASSO 2: SETUP DATABASE
1. Assicurati di aver disattivato la "Modalità Manutenzione" di WordPress, altrimenti l'app non funzionerà.
2. Visita `https://www.virtuprinto.com/php_server/setup.php` per assicurarti che il database sia pronto.

PASSO 3: GIOCA!
1. Visita `https://www.virtuprinto.com` (o dove hai caricato i file della `web_app`).
2. Dovresti vedere la schermata di Login.
3. Prova a registrarti o usa l'admin (`admin` / `Giuli@`).
