# Guía completa: SSL con Let's Encrypt y renovación automática

Guía reutilizable para cualquier VPS Linux con nginx.  
Cubre tanto nginx instalado directamente en el host como nginx corriendo dentro de Docker.

---

## Índice

1. [Cómo funciona Let's Encrypt](#1-cómo-funciona-lets-encrypt)
2. [Requisitos previos](#2-requisitos-previos)
3. [Instalar Certbot](#3-instalar-certbot)
4. [Obtener el certificado por primera vez](#4-obtener-el-certificado-por-primera-vez)
   - [Opción A: nginx en el host](#41-opción-a-nginx-instalado-directamente-en-el-host)
   - [Opción B: nginx en Docker](#42-opción-b-nginx-corriendo-en-docker)
5. [Renovación automática](#5-renovación-automática)
   - [Opción A: nginx en el host](#51-opción-a-nginx-en-el-host)
   - [Opción B: nginx en Docker](#52-opción-b-nginx-en-docker)
6. [Verificar que la renovación funciona](#6-verificar-que-la-renovación-funciona)
7. [Comprobar fechas de caducidad](#7-comprobar-fechas-de-caducidad)
8. [Recibir alertas si el certificado va a caducar](#8-recibir-alertas-si-el-certificado-va-a-caducar)
9. [Añadir un segundo dominio al mismo VPS](#9-añadir-un-segundo-dominio-al-mismo-vps)
10. [Revocar o eliminar un certificado](#10-revocar-o-eliminar-un-certificado)
11. [Troubleshooting](#11-troubleshooting)
12. [Referencia rápida: comandos habituales](#12-referencia-rápida-comandos-habituales)

---

## 1. Cómo funciona Let's Encrypt

Let's Encrypt emite certificados SSL gratuitos con **90 días de validez**. El proceso de emisión se llama *challenge*: Let's Encrypt comprueba que controlas el dominio antes de emitir el certificado.

El método más común en VPS con nginx es **HTTP-01**: Let's Encrypt hace una petición HTTP al dominio en el puerto 80 y certbot responde con un token. Para ello, el puerto 80 debe estar libre y accesible desde internet en el momento de emitir o renovar.

```
Let's Encrypt ──► GET http://tuvidominio.com/.well-known/acme-challenge/TOKEN
                         │
                    VPS puerto 80
                         │
                    Certbot responde con TOKEN
                         │
              Let's Encrypt verifica ──► emite certificado
```

Los certificados se guardan en el host en:
```
/etc/letsencrypt/live/tudominio.com/
    fullchain.pem   ← certificado + cadena intermedia (esto va a nginx)
    privkey.pem     ← clave privada (esto va a nginx)
    cert.pem        ← solo el certificado (normalmente no se usa directamente)
    chain.pem       ← solo la cadena intermedia
```

---

## 2. Requisitos previos

Antes de empezar, verifica:

- [ ] El VPS tiene **Ubuntu 20.04 / 22.04 / 24.04** o **Debian 11/12** (o similar).
- [ ] El dominio `tudominio.com` apunta a la **IP pública del VPS** con un registro DNS tipo A.
- [ ] El **puerto 80 está accesible** desde internet (no bloqueado por firewall).
- [ ] El **puerto 443 está accesible** desde internet.
- [ ] Tienes acceso SSH con `sudo`.

Verificar que el DNS resuelve correctamente:
```bash
dig +short tudominio.com
# Debe devolver la IP pública del VPS

# O con nslookup:
nslookup tudominio.com
```

Verificar que los puertos están abiertos (desde el propio VPS):
```bash
sudo ss -tlnp | grep -E ':80|:443'
```

---

## 3. Instalar Certbot

### En Ubuntu/Debian (recomendado: snap)

```bash
sudo apt update
sudo apt install -y snapd
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot
```

Verificar instalación:
```bash
certbot --version
# certbot 2.x.x
```

### Alternativa: apt (versión del repositorio del sistema)

```bash
sudo apt update
sudo apt install -y certbot
```

> La versión snap suele ser más reciente. Si tienes problemas con la de apt, usa snap.

---

## 4. Obtener el certificado por primera vez

### 4.1. Opción A: nginx instalado directamente en el host

Si nginx corre directamente en el host (no en Docker), certbot puede usarlo como plugin.

**Con el plugin de nginx** (automático, sin downtime):
```bash
sudo apt install -y python3-certbot-nginx
sudo certbot --nginx -d tudominio.com
```

Certbot modifica la configuración de nginx automáticamente para añadir SSL. Sigue las instrucciones en pantalla:
- Introduce tu email (para alertas de caducidad).
- Acepta los términos.
- Elige si redirigir HTTP a HTTPS (recomendado: sí).

**Con standalone** (para el primer certificado si nginx no está aún configurado):
```bash
# Para nginx para liberar el puerto 80
sudo systemctl stop nginx

sudo certbot certonly --standalone -d tudominio.com

# Arrancar nginx de nuevo
sudo systemctl start nginx
```

---

### 4.2. Opción B: nginx corriendo en Docker

Cuando nginx está dentro de un contenedor Docker, certbot **se instala en el host** (no dentro del contenedor) y el certificado se copia a una carpeta montada como volumen.

#### Paso 1 — Detener el contenedor nginx para liberar el puerto 80

```bash
# Desde la carpeta del proyecto con docker-compose.yml
cd /ruta/al/proyecto
docker compose stop nginx
```

#### Paso 2 — Solicitar el certificado

```bash
sudo certbot certonly --standalone -d tudominio.com
```

Certbot te pedirá:
- Tu email (para alertas de caducidad de Let's Encrypt).
- Aceptar los términos de servicio.

El certificado se guarda en:
```
/etc/letsencrypt/live/tudominio.com/fullchain.pem
/etc/letsencrypt/live/tudominio.com/privkey.pem
```

#### Paso 3 — Copiar los certificados a la carpeta del proyecto

```bash
sudo cp /etc/letsencrypt/live/tudominio.com/fullchain.pem /ruta/al/proyecto/deploy/certs/
sudo cp /etc/letsencrypt/live/tudominio.com/privkey.pem   /ruta/al/proyecto/deploy/certs/
sudo chmod 644 /ruta/al/proyecto/deploy/certs/*.pem
```

#### Paso 4 — Configurar nginx para HTTPS

Edita `deploy/nginx/conf.d/app.conf`:

```nginx
server {
    listen 80;
    server_name tudominio.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name tudominio.com;
    client_max_body_size 200M;

    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    location / {
        proxy_pass         http://app:8501;   # ajusta el nombre del servicio y puerto
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   Upgrade           $http_upgrade;
        proxy_set_header   Connection        "upgrade";
        proxy_read_timeout 86400;
    }
}
```

> `app:8501` es el nombre del servicio en `docker-compose.yml` y su puerto interno. Ajusta según tu proyecto.

#### Paso 5 — Arrancar nginx con la nueva configuración

```bash
docker compose up -d nginx
```

Verifica que HTTPS funciona:
```bash
curl -I https://tudominio.com
# Debe devolver HTTP/2 200 (o 301/302 según tu app)
```

---

## 5. Renovación automática

Let's Encrypt caduca cada **90 días**. Certbot intenta renovar si quedan menos de **30 días**. El cron debe ejecutarse con suficiente frecuencia para garantizar que siempre hay margen.

**Frecuencia recomendada**: dos veces por semana (lunes y jueves a las 3:00).

### 5.1. Opción A: nginx en el host

El plugin de nginx permite renovar **sin downtime**:

```bash
sudo crontab -e
```

Añade:
```
0 3 * * 1,4 certbot renew --quiet --nginx
```

Certbot renueva solo si quedan menos de 30 días. Si el certificado tiene más tiempo, no hace nada.

---

### 5.2. Opción B: nginx en Docker

Con nginx en Docker hay que:
1. Parar nginx antes de renovar (para liberar el puerto 80).
2. Renovar con certbot en modo standalone.
3. Copiar los nuevos certificados a la carpeta del proyecto.
4. Arrancar nginx de nuevo.

Todo esto se hace con los hooks `--pre-hook` y `--post-hook` de certbot.

#### Crear el script de renovación

Crea el archivo `/usr/local/bin/renovar-ssl-NOMBRE.sh` (sustituye NOMBRE por algo descriptivo del proyecto):

```bash
sudo nano /usr/local/bin/renovar-ssl-NOMBRE.sh
```

Contenido del script:
```bash
#!/bin/bash

# ─────────────────────────────────────────────
# Configuración — adaptar a cada proyecto
# ─────────────────────────────────────────────
PROYECTO_DIR="/ruta/al/proyecto"
DOMINIO="tudominio.com"
CERTS_DEST="${PROYECTO_DIR}/deploy/certs"
LOG="/var/log/renovar-ssl-NOMBRE.log"
# ─────────────────────────────────────────────

echo "──────────────────────────────────────────" >> "$LOG"
echo "$(date '+%Y-%m-%d %H:%M:%S') Iniciando renovación para $DOMINIO" >> "$LOG"

# 1. Parar nginx para liberar el puerto 80
cd "$PROYECTO_DIR" || { echo "ERROR: no existe $PROYECTO_DIR" >> "$LOG"; exit 1; }
docker compose stop nginx >> "$LOG" 2>&1

# 2. Renovar el certificado
certbot renew --standalone --cert-name "$DOMINIO" --quiet >> "$LOG" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR en certbot renew (código $EXIT_CODE)" >> "$LOG"
fi

# 3. Copiar certificados renovados al proyecto
cp /etc/letsencrypt/live/"$DOMINIO"/fullchain.pem "$CERTS_DEST/" >> "$LOG" 2>&1
cp /etc/letsencrypt/live/"$DOMINIO"/privkey.pem   "$CERTS_DEST/" >> "$LOG" 2>&1
chmod 644 "$CERTS_DEST"/*.pem >> "$LOG" 2>&1

# 4. Arrancar nginx de nuevo
docker compose up -d nginx >> "$LOG" 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') Renovación completada" >> "$LOG"
```

Dar permisos de ejecución:
```bash
sudo chmod +x /usr/local/bin/renovar-ssl-NOMBRE.sh
```

#### Añadir el cron

```bash
sudo crontab -e
```

Añade (lunes y jueves a las 3:00):
```
0 3 * * 1,4 /usr/local/bin/renovar-ssl-NOMBRE.sh
```

> **Por qué dos veces por semana:** certbot solo actúa si el certificado tiene menos de 30 días restantes. Ejecutarlo dos veces por semana garantiza que si un intento falla (VPS sin internet, error transitorio), habrá otro intento en 3 días.

---

## 6. Verificar que la renovación funciona

### Simulacro sin modificar nada

```bash
sudo certbot renew --dry-run
```

Debe terminar con:
```
Congratulations, all simulated renewals succeeded
```

### Ejecutar el script manualmente (solo opción B — Docker)

```bash
sudo /usr/local/bin/renovar-ssl-NOMBRE.sh
```

Revisar el log:
```bash
cat /var/log/renovar-ssl-NOMBRE.log
```

Verifica que nginx sigue funcionando:
```bash
docker compose ps
curl -I https://tudominio.com
```

### Ver el log del cron

Los cron de root se pueden ver en:
```bash
sudo grep CRON /var/log/syslog | tail -20
# o en sistemas más nuevos:
sudo journalctl -u cron --since "1 week ago" | grep renovar
```

---

## 7. Comprobar fechas de caducidad

### Ver cuándo caduca el certificado actual

```bash
sudo certbot certificates
```

Salida esperada:
```
Found the following certs:
  Certificate Name: tudominio.com
    Domains: tudominio.com
    Expiry Date: 2025-09-15 (VALID: 78 days)
    Certificate Path: /etc/letsencrypt/live/tudominio.com/fullchain.pem
    Private Key Path: /etc/letsencrypt/live/tudominio.com/privkey.pem
```

### Comprobar el certificado que sirve nginx directamente

```bash
echo | openssl s_client -connect tudominio.com:443 -servername tudominio.com 2>/dev/null \
  | openssl x509 -noout -dates
```

Salida:
```
notBefore=Jun 17 00:00:00 2025 GMT
notAfter=Sep 15 23:59:59 2025 GMT
```

> Si `notAfter` es diferente al que muestra `certbot certificates`, significa que el certificado se renovó pero nginx no cargó el nuevo. Ejecuta el script o reinicia nginx.

---

## 8. Recibir alertas si el certificado va a caducar

### Opción A: alertas automáticas de Let's Encrypt por email

Let's Encrypt envía emails al correo que diste en la primera solicitud cuando el certificado tiene 20 y 7 días restantes. No requiere configuración adicional.

Para cambiar el email:
```bash
sudo certbot update_account --email nuevo@correo.com
```

### Opción B: UptimeRobot (monitorización externa gratuita)

[UptimeRobot](https://uptimerobot.com) comprueba tu URL cada 5 minutos y te avisa por email si no responde. El plan gratuito incluye hasta 50 monitores.

Configuración:
1. Crear cuenta en uptimerobot.com
2. Añadir monitor: `HTTPS` → `https://tudominio.com`
3. Configurar alertas por email

Esto detecta tanto caída del servicio como certificado caducado (una web con SSL caducado da error 526 o ERR_CERT_DATE_INVALID).

### Opción C: script de alerta por email desde el cron

Si el VPS tiene `mailutils` instalado:

```bash
sudo apt install -y mailutils
```

Añade al final del script de renovación:
```bash
# Alerta si el certificado caduca en menos de 20 días
DIAS_RESTANTES=$(openssl x509 -enddate -noout \
  -in /etc/letsencrypt/live/"$DOMINIO"/fullchain.pem \
  | sed 's/notAfter=//')
EXPIRY_EPOCH=$(date -d "$DIAS_RESTANTES" +%s)
NOW_EPOCH=$(date +%s)
DIAS=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))

if [ "$DIAS" -lt 20 ]; then
    echo "ALERTA: el certificado SSL de $DOMINIO caduca en $DIAS días." \
      | mail -s "⚠️ SSL caducando pronto: $DOMINIO" tu@correo.com
fi
```

---

## 9. Añadir un segundo dominio al mismo VPS

### Si ya tienes un certificado y quieres añadir otro dominio diferente

Cada dominio tiene su propio certificado. Repite el proceso de la sección 4 para el nuevo dominio.

Para nginx en Docker, crea un script de renovación separado:
```bash
sudo cp /usr/local/bin/renovar-ssl-PROYECTO1.sh /usr/local/bin/renovar-ssl-PROYECTO2.sh
sudo nano /usr/local/bin/renovar-ssl-PROYECTO2.sh
# Cambia PROYECTO_DIR, DOMINIO y LOG
sudo chmod +x /usr/local/bin/renovar-ssl-PROYECTO2.sh
```

Añade la segunda línea al cron:
```
0 3  * * 1,4 /usr/local/bin/renovar-ssl-PROYECTO1.sh
30 3 * * 1,4 /usr/local/bin/renovar-ssl-PROYECTO2.sh
```

> Separa las horas de ejecución (30 minutos de diferencia) para evitar que ambos scripts intenten liberar el puerto 80 al mismo tiempo.

### Si quieres un certificado que cubra varios subdominios a la vez

```bash
sudo certbot certonly --standalone \
  -d dominio.com \
  -d www.dominio.com \
  -d app.dominio.com
```

Todos los dominios deben apuntar al mismo VPS.

---

## 10. Revocar o eliminar un certificado

### Eliminar un certificado que ya no usas

```bash
sudo certbot delete --cert-name tudominio.com
```

### Revocar (si crees que la clave privada se ha comprometido)

```bash
sudo certbot revoke --cert-path /etc/letsencrypt/live/tudominio.com/fullchain.pem
```

---

## 11. Troubleshooting

### Error: puerto 80 en uso al renovar

```
Error: Problem binding to port 80: Could not bind to IPv4 or IPv6.
```

**Causa**: nginx u otro proceso ocupa el puerto 80.

**Solución**: para el servicio antes de renovar. Con Docker:
```bash
cd /ruta/al/proyecto
docker compose stop nginx
sudo certbot renew --standalone --cert-name tudominio.com
docker compose up -d nginx
```

---

### Error: el dominio no resuelve a este VPS

```
Error: DNS problem: NXDOMAIN looking up A for tudominio.com
```

**Causa**: el registro DNS no apunta a la IP del VPS, o la propagación DNS no ha terminado.

**Solución**:
```bash
dig +short tudominio.com
# Compara con la IP del VPS:
curl -s ifconfig.me
```

Si son diferentes, corrige el DNS y espera la propagación (hasta 24h, normalmente menos de 1h con TTL bajo).

---

### El certificado se renovó pero nginx sigue sirviendo el antiguo

**Causa**: los archivos `.pem` en la carpeta del proyecto no se actualizaron, o nginx no se reinició.

**Solución**:
```bash
# Copiar manualmente
sudo cp /etc/letsencrypt/live/tudominio.com/fullchain.pem /ruta/al/proyecto/deploy/certs/
sudo cp /etc/letsencrypt/live/tudominio.com/privkey.pem   /ruta/al/proyecto/deploy/certs/
sudo chmod 644 /ruta/al/proyecto/deploy/certs/*.pem

# Reiniciar nginx
cd /ruta/al/proyecto
docker compose restart nginx
```

Verificar qué certificado sirve nginx ahora:
```bash
echo | openssl s_client -connect tudominio.com:443 2>/dev/null | openssl x509 -noout -dates
```

---

### Error de rate limit de Let's Encrypt

```
Error: too many certificates already issued for tudominio.com
```

**Causa**: Let's Encrypt limita a **5 certificados por dominio cada 7 días**. Suele ocurrir cuando se repite la solicitud por error.

**Solución**: espera hasta que pase el período de 7 días. Mientras, usa el certificado existente (si sigue siendo válido).

Para ver los certificados ya emitidos:
```bash
sudo certbot certificates
```

---

### El cron no se ejecuta

**Verificar que el cron de root está activo**:
```bash
sudo systemctl status cron
# o en algunos sistemas:
sudo systemctl status crond
```

**Ver el crontab actual de root**:
```bash
sudo crontab -l
```

**Ver logs del cron**:
```bash
sudo grep CRON /var/log/syslog | tail -30
```

**Probar que el script funciona manualmente** (siempre antes de dejar el cron):
```bash
sudo /usr/local/bin/renovar-ssl-NOMBRE.sh
cat /var/log/renovar-ssl-NOMBRE.log
```

---

## 12. Referencia rápida: comandos habituales

| Tarea | Comando |
|-------|---------|
| Ver certificados y fechas | `sudo certbot certificates` |
| Simular renovación sin cambios | `sudo certbot renew --dry-run` |
| Renovar manualmente (host) | `sudo certbot renew` |
| Renovar manualmente (Docker) | `sudo /usr/local/bin/renovar-ssl-NOMBRE.sh` |
| Ver fecha del cert en nginx | `echo \| openssl s_client -connect dom:443 2>/dev/null \| openssl x509 -noout -dates` |
| Editar cron de root | `sudo crontab -e` |
| Ver cron de root | `sudo crontab -l` |
| Ver log del script | `cat /var/log/renovar-ssl-NOMBRE.log` |
| Añadir dominio al cert | `sudo certbot certonly --standalone -d nuevo.dom.com` |
| Eliminar certificado | `sudo certbot delete --cert-name dom.com` |

---

## Checklist por proyecto nuevo

Al configurar SSL en un VPS nuevo, sigue este orden:

- [ ] DNS tipo A apuntando a la IP del VPS
- [ ] Puertos 80 y 443 abiertos en el firewall (`ufw allow 80,443/tcp`)
- [ ] Certbot instalado en el host
- [ ] Contenedor nginx parado antes de solicitar el certificado
- [ ] `certbot certonly --standalone -d tudominio.com` ejecutado con éxito
- [ ] Certificados copiados a `deploy/certs/` con permisos 644
- [ ] nginx configurado con `ssl_certificate` y `ssl_certificate_key`
- [ ] Contenedor nginx arrancado y `curl -I https://tudominio.com` devuelve 200
- [ ] Script `/usr/local/bin/renovar-ssl-NOMBRE.sh` creado y probado manualmente
- [ ] Cron añadido en `sudo crontab -e`
- [ ] `sudo certbot renew --dry-run` termina sin errores
- [ ] Monitor en UptimeRobot configurado (opcional pero recomendado)

---

*Guía generada para Enteza · mayo 2026 · válida para Ubuntu 20.04/22.04/24.04 y Debian 11/12*
