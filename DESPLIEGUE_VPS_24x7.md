# Despliegue 24/7 en VPS Linux (Docker)

Guia detallada para desplegar **Enteza - RRHH** en un VPS y mantenerla disponible 24/7.

---

## 1) Objetivo

Dejar la aplicacion funcionando de forma continua con:

- reinicio automatico si falla,
- exposicion publica por dominio o IP,
- persistencia de datos de firma,
- actualizacion controlada,
- base para HTTPS en produccion.

---

## 2) Arquitectura recomendada

Servicios:

1. `app` (Streamlit) en contenedor Docker.
2. `nginx` (reverse proxy) en contenedor Docker.

Persistencia local en host:

- `./data` (BD SQLite, solicitudes, firmas, PDFs firmados)
- `./uploads` (si se usa almacenamiento auxiliar)

Flujo:

`Internet -> Nginx:80/443 -> Streamlit:8501`

---

## 3) Requisitos previos

- VPS Linux (Ubuntu/Debian recomendado).
- Usuario con permisos `sudo`.
- Docker Engine instalado.
- Docker Compose v2 (`docker compose`) instalado.
- Repositorio clonado en el VPS.

---

## 4) Preparacion inicial del VPS

Actualiza el sistema:

```bash
sudo apt update && sudo apt upgrade -y
```

Instala utilidades basicas:

```bash
sudo apt install -y git curl ca-certificates
```

---

## 5) Clonar repositorio

```bash
git clone https://github.com/Enteza-Alquisillas/FirmaNominas.git
cd FirmaNominas
```

---

## 6) Configuracion de entorno

Crear/editar `.env.local` en el VPS:

```bash
nano .env.local
```

Variables minimas recomendadas:

```env
ODOO_URL=http://tu-odoo:puerto
ODOO_DB=tu_basededatos
ODOO_USER=tu_usuario
ODOO_PASSWORD=tu_password

# URL publica REAL para enlaces de firma
SIGN_BASE_URL=https://rrhh.tudominio.com
```

> Importante: `SIGN_BASE_URL` debe ser URL publica completa para que los enlaces WhatsApp sean clicables y funcionales.

---

## 7) Estructura persistente

Crear carpetas de persistencia en host:

```bash
mkdir -p data uploads deploy/certs
```

Estas rutas se montan como volumen en Docker y conservan datos entre reinicios.

---

## 8) Build y arranque 24/7

Compilar imagen y levantar servicios:

```bash
docker compose build app
docker compose up -d
```

Verificar estado:

```bash
docker compose ps
docker compose logs -f app
docker compose logs -f nginx
```

La disponibilidad 24/7 la garantiza Docker con `restart: unless-stopped`.

---

## 9) Firewall y puertos

Si usas UFW:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

---

## 10) DNS (si usas dominio)

Configurar registro `A`:

- `rrhh.tudominio.com` -> `IP_PUBLICA_VPS`

Comprobar:

```bash
ping rrhh.tudominio.com
```

---

## 11) HTTPS con Let's Encrypt (produccion)

El nginx de Docker ya tiene mapeados los puertos 80 y 443 y la carpeta `deploy/certs` montada como volumen. El proceso para obtener y configurar el certificado SSL es el siguiente.

### 11.1 Obtener el certificado (primera vez)

Instala certbot en el host del VPS (no en Docker):

```bash
sudo apt install certbot -y
```

Para el nginx un momento para liberar el puerto 80:

```bash
docker compose stop nginx
```

Solicita el certificado en modo standalone:

```bash
sudo certbot certonly --standalone -d rrhh.tudominio.com
```

Introduce tu email cuando lo pida y acepta los terminos. El certificado se guarda en `/etc/letsencrypt/live/rrhh.tudominio.com/`.

Copia los certificados a la carpeta del proyecto:

```bash
sudo cp /etc/letsencrypt/live/rrhh.tudominio.com/fullchain.pem ./deploy/certs/
sudo cp /etc/letsencrypt/live/rrhh.tudominio.com/privkey.pem ./deploy/certs/
sudo chmod 644 ./deploy/certs/*.pem
```

### 11.2 Configurar nginx con HTTPS

Edita `./deploy/nginx/conf.d/app.conf` con este contenido:

```nginx
server {
    listen 80;
    server_name rrhh.tudominio.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name rrhh.tudominio.com;
    client_max_body_size 200M;

    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    location / {
        proxy_pass http://app:8501;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

Arranca nginx de nuevo:

```bash
docker compose up -d nginx
```

Actualiza `SIGN_BASE_URL` en `.env.local`:

```
SIGN_BASE_URL=https://rrhh.tudominio.com
```

Reinicia la app para que lea el nuevo valor:

```bash
docker compose restart app
```

### 11.3 Renovacion automatica del certificado

Let's Encrypt caduca cada 90 dias. Configura un cron en el host para renovar automaticamente sin downtime. Edita el crontab de root:

```bash
sudo crontab -e
```

Añade esta linea (se ejecuta cada lunes a las 3:00):

```bash
0 3 * * 1 certbot renew --quiet --pre-hook "docker compose -f /ruta/al/proyecto/docker-compose.yml stop nginx" --post-hook "cp /etc/letsencrypt/live/rrhh.tudominio.com/fullchain.pem /ruta/al/proyecto/deploy/certs/ && cp /etc/letsencrypt/live/rrhh.tudominio.com/privkey.pem /ruta/al/proyecto/deploy/certs/ && chmod 644 /ruta/al/proyecto/deploy/certs/*.pem && docker compose -f /ruta/al/proyecto/docker-compose.yml up -d nginx"
```

Sustituye `/ruta/al/proyecto` por la ruta real del proyecto en el VPS.

Verifica que el cron funciona correctamente con un simulacro:

```bash
sudo certbot renew --dry-run
```

> Para enlaces de firma en movil y WhatsApp el **HTTPS es obligatorio**. WhatsApp fuerza HTTP a HTTPS en movil y sin certificado valido los enlaces no abren.

---

## 12) Comandos operativos diarios

Estado:

```bash
docker compose ps
```

Logs en vivo:

```bash
docker compose logs -f app
docker compose logs -f nginx
```

Reiniciar servicios:

```bash
docker compose restart app
docker compose restart nginx
```

Parar/arrancar:

```bash
docker compose down
docker compose up -d
```

---

## 13) Flujo de actualizacion (deploy de cambios)

Cada vez que subes cambios a GitHub:

```bash
cd ~/FirmaNominas
git fetch origin
git checkout main
git reset --hard origin/main

docker compose build app
docker compose up -d
docker compose ps
```

Si cambiaste Nginx:

```bash
docker compose restart nginx
```

---

## 14) Backup y recuperacion

## 14.1 Que respaldar

- `data/` (critico)
- `.env.local` (seguro y cifrado fuera del repo)

## 14.2 Backup rapido

```bash
tar -czf backup_rrhh_$(date +%F).tar.gz data .env.local
```

## 14.3 Restauracion

```bash
tar -xzf backup_rrhh_YYYY-MM-DD.tar.gz
docker compose up -d
```

---

## 15) Health checks recomendados

Comprobar salud Streamlit dentro de contenedor:

```bash
docker compose exec app python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health').read().decode())"
```

Debe devolver `ok`.

---

## 16) Problemas frecuentes y solucion

## Error 413 al subir PDF

Sintoma: `AxiosError: Request failed with status code 413`

Causa: limite de upload en proxy.

Verificar:

- `deploy/nginx/conf.d/app.conf` contiene `client_max_body_size 200M;`
- `.streamlit/config.toml` contiene `maxUploadSize = 200`

Aplicar:

```bash
docker compose build app
docker compose up -d
docker compose restart nginx
```

## Error `ContainerConfig` con docker-compose

Causa: uso de `docker-compose` v1 antiguo.

Solucion: usar siempre `docker compose` v2.

## Enlaces WhatsApp no clicables

Verificar `SIGN_BASE_URL` completa:

```env
SIGN_BASE_URL=https://rrhh.tudominio.com
```

## Estado divergente en git pull

Usar:

```bash
git fetch origin
git reset --hard origin/main
```

---

## 17) Seguridad minima obligatoria

1. No subir `.env.local` al repositorio.
2. Rotar credenciales si hubo exposicion.
3. Usar HTTPS en produccion.
4. Limitar acceso SSH (IP allowlist, key auth, sin password si posible).
5. Mantener VPS actualizado (`apt upgrade`).
6. Backups periodicos automáticos.

---

## 18) Migracion a otro VPS

Procedimiento completo para mover la aplicacion a un VPS nuevo sin perdida de datos ni tiempo de inactividad prolongado.

### 18.1 Datos criticos a migrar

| Dato | Ubicacion | Critico |
|------|-----------|---------|
| BD de firmas (SQLite) | `data/signatures.db` | Si — unico registro de auditoría |
| PDFs originales | `data/signature_pdfs/original/` | Si — necesarios para re-firmar |
| PDFs firmados | `data/signature_pdfs/signed/` | Si — evidencia legal |
| Firmas PNG | `data/signature_pdfs/signatures/` | Si — evidencia legal |
| Credenciales | `.env.local` | Si |
| Config nginx | `deploy/nginx/conf.d/app.conf` | Si |
| Certificados SSL | `deploy/certs/` | No — se regeneran en el nuevo VPS |

### 18.2 Preparacion del VPS nuevo

Instala Docker y Docker Compose v2 en el VPS nuevo:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ca-certificates

# Docker Engine
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Verificar
docker --version
docker compose version
```

Clona el repositorio:

```bash
git clone https://github.com/Enteza-Alquisillas/FirmaNominas.git
cd FirmaNominas
```

### 18.3 Transferir los datos desde el VPS antiguo

Ejecuta esto desde el **VPS antiguo** (sustituye `NUEVO_VPS_IP` y `USUARIO`):

```bash
# Comprimir todos los datos criticos
tar -czf migracion_rrhh.tar.gz data/ .env.local deploy/nginx/conf.d/app.conf

# Transferir al VPS nuevo
scp migracion_rrhh.tar.gz USUARIO@NUEVO_VPS_IP:/ruta/al/proyecto/
```

En el **VPS nuevo**, dentro de la carpeta del proyecto:

```bash
tar -xzf migracion_rrhh.tar.gz
rm migracion_rrhh.tar.gz
```

### 18.4 Obtener certificado SSL en el VPS nuevo

Apunta el DNS del dominio a la IP del VPS nuevo antes de este paso.

```bash
sudo apt install certbot -y
sudo certbot certonly --standalone -d rrhh.tudominio.com

sudo cp /etc/letsencrypt/live/rrhh.tudominio.com/fullchain.pem ./deploy/certs/
sudo cp /etc/letsencrypt/live/rrhh.tudominio.com/privkey.pem ./deploy/certs/
sudo chmod 644 ./deploy/certs/*.pem
```

Configura la renovacion automatica (ver seccion 11.3).

### 18.5 Arrancar la aplicacion en el VPS nuevo

```bash
docker compose build app
docker compose up -d
docker compose ps
```

Verifica que los dos contenedores (`nominas-streamlit` y `nominas-nginx`) estan en estado `Up`.

### 18.6 Verificacion antes de cortar el VPS antiguo

Comprueba en el VPS nuevo:

```bash
# Salud de Streamlit
docker compose exec app python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health').read().decode())"
# Debe devolver: ok
```

Abre en el navegador `https://rrhh.tudominio.com` y verifica:

- [ ] La app carga correctamente
- [ ] El campo SIGN_BASE_URL muestra la URL correcta
- [ ] Los datos historicos de firmas son visibles en la seccion 6
- [ ] La conexion con Odoo funciona (prueba conectar en la seccion de config)

### 18.7 Corte definitivo

Una vez verificado que todo funciona en el VPS nuevo:

1. Para los contenedores en el VPS antiguo:

```bash
docker compose down
```

2. Guarda un backup final del VPS antiguo antes de apagarlo:

```bash
tar -czf backup_final_rrhh_$(date +%F).tar.gz data/ .env.local
```

3. Apaga o destruye el VPS antiguo.

> En caso de problemas durante la migracion, el VPS antiguo puede seguir funcionando mientras se resuelven. Solo hay un riesgo: si se firman nominas en el VPS nuevo durante la prueba, esas firmas no estarán en el VPS antiguo. Evitar procesar firmas nuevas hasta que el corte sea definitivo.

---

## 19) Checklist final de salida a produccion

- [ ] `docker compose ps` muestra `app` y `nginx` en `Up`.
- [ ] URL publica abre la app correctamente.
- [ ] Se puede subir PDF y Excel sin 413.
- [ ] Enlace de firma enviado por WhatsApp abre en movil.
- [ ] Firma se incrusta bajo "Recibi".
- [ ] PDF firmado se adjunta en Odoo al empleado correcto.
- [ ] Backup de `data/` funcionando.
- [ ] HTTPS activo.

---

Con esta guia, la aplicacion queda operativa y mantenible 24/7 en VPS.
