# Renovación automática SSL — rrhh.enteza.es

Instrucciones exactas para configurar la renovación automática del certificado
Let's Encrypt en el VPS de producción de Enteza RRHH.

| Dato | Valor |
|------|-------|
| Dominio | `rrhh.enteza.es` |
| Ruta del proyecto | `/home/enteza/FirmaNominas` |
| Usuario del VPS | `enteza` |
| Script de renovación | `/usr/local/bin/renovar-ssl-rrhh.sh` |
| Log | `/var/log/renovar-ssl-rrhh.log` |

---

## Paso 1 — Crear el script de renovación

```bash
sudo nano /usr/local/bin/renovar-ssl-rrhh.sh
```

Pega este contenido:

```bash
#!/bin/bash

PROYECTO_DIR="/home/enteza/FirmaNominas"
DOMINIO="rrhh.enteza.es"
CERTS_DEST="${PROYECTO_DIR}/deploy/certs"
LOG="/var/log/renovar-ssl-rrhh.log"

echo "──────────────────────────────────────────" >> "$LOG"
echo "$(date '+%Y-%m-%d %H:%M:%S') Iniciando renovación para $DOMINIO" >> "$LOG"

cd "$PROYECTO_DIR" || { echo "ERROR: no existe $PROYECTO_DIR" >> "$LOG"; exit 1; }
docker compose stop nginx >> "$LOG" 2>&1

certbot renew --standalone --cert-name "$DOMINIO" --quiet >> "$LOG" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR en certbot renew (código $EXIT_CODE)" >> "$LOG"
fi

cp /etc/letsencrypt/live/"$DOMINIO"/fullchain.pem "$CERTS_DEST/" >> "$LOG" 2>&1
cp /etc/letsencrypt/live/"$DOMINIO"/privkey.pem   "$CERTS_DEST/" >> "$LOG" 2>&1
chmod 644 "$CERTS_DEST"/*.pem >> "$LOG" 2>&1

docker compose up -d nginx >> "$LOG" 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') Renovación completada" >> "$LOG"
```

Guardar: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## Paso 2 — Dar permisos de ejecución

```bash
sudo chmod +x /usr/local/bin/renovar-ssl-rrhh.sh
```

---

## Paso 3 — Probarlo manualmente

```bash
sudo /usr/local/bin/renovar-ssl-rrhh.sh
```

Verificar que todo fue bien:

```bash
cat /var/log/renovar-ssl-rrhh.log
docker compose -f /home/enteza/FirmaNominas/docker-compose.yml ps
curl -I https://rrhh.enteza.es
```

Resultado esperado en el log:
```
──────────────────────────────────────────
2026-05-16 03:00:01 Iniciando renovación para rrhh.enteza.es
2026-05-16 03:00:xx Renovación completada
```

Resultado esperado en `docker compose ps`: los dos contenedores (`nominas-streamlit` y `nominas-nginx`) en estado `Up`.

Resultado esperado en `curl -I`: `HTTP/2 200` o `HTTP/1.1 301`.

---

## Paso 4 — Añadir el cron (solo si el paso 3 fue bien)

```bash
sudo crontab -e
```

Añadir al final del archivo:

```
0 3 * * 1,4 /usr/local/bin/renovar-ssl-rrhh.sh
```

> Se ejecuta los **lunes y jueves a las 3:00**. Certbot solo renueva si quedan menos de 30 días; si el certificado tiene más tiempo, el script termina en segundos sin tocar nada.

---

## Paso 5 — Verificar que el cron quedó registrado

```bash
sudo crontab -l
```

Debe aparecer la línea añadida en el paso anterior.

---

## Paso 6 — Simulacro final de certbot

```bash
sudo certbot renew --dry-run
```

Debe terminar con:
```
All simulated renewals succeeded
```

Con esto la renovación queda completamente automatizada.

---

## Operativa habitual

### Ver cuándo caduca el certificado actual

```bash
sudo certbot certificates
```

### Ver el log de la última renovación

```bash
cat /var/log/renovar-ssl-rrhh.log
```

### Forzar renovación manual (si hay urgencia)

```bash
sudo certbot renew --standalone --cert-name rrhh.enteza.es --force-renewal
sudo cp /etc/letsencrypt/live/rrhh.enteza.es/fullchain.pem /home/enteza/FirmaNominas/deploy/certs/
sudo cp /etc/letsencrypt/live/rrhh.enteza.es/privkey.pem   /home/enteza/FirmaNominas/deploy/certs/
sudo chmod 644 /home/enteza/FirmaNominas/deploy/certs/*.pem
cd /home/enteza/FirmaNominas && docker compose restart nginx
```

### Comprobar qué certificado está sirviendo nginx ahora mismo

```bash
echo | openssl s_client -connect rrhh.enteza.es:443 -servername rrhh.enteza.es 2>/dev/null \
  | openssl x509 -noout -dates
```

---

## Checklist de instalación completada

- [ ] Script creado en `/usr/local/bin/renovar-ssl-rrhh.sh`
- [ ] Script ejecutable (`chmod +x`)
- [ ] Prueba manual ejecutada sin errores
- [ ] Contenedores funcionando tras la prueba
- [ ] `https://rrhh.enteza.es` responde correctamente tras la prueba
- [ ] Línea añadida en `sudo crontab -e`
- [ ] `sudo crontab -l` muestra la línea
- [ ] `sudo certbot renew --dry-run` termina con éxito
