# Deploy En Linux Con Cloudflare Zero Trust

Esta guía asume un servidor Linux con Docker y Docker Compose Plugin instalado,
y un **Cloudflare Tunnel central ya corriendo en el host** (el mismo patrón que tus
otras apps, ej. pipiseries).

A diferencia de pipiseries, esta app:

- es **un solo servicio** (FastAPI que sirve el frontend en `/` y la API en `/api`),
- **no tiene `.env` ni secretos** (los horarios son datos públicos),
- **no necesita nginx propio** (el mismo servicio ya expone todo bajo el mismo origen).

## 1. Clonar

```bash
git clone https://github.com/juantubello/tren_mitre_martinez_api.git
cd tren_mitre_martinez_api
```

## 2. Levantar

```bash
docker compose up -d --build
```

El contenedor queda escuchando **solo en localhost**, en un puerto fijo:

```txt
127.0.0.1:53354
```

Verificalo:

```bash
docker compose ps
curl -s http://127.0.0.1:53354/api/health   # -> {"status":"ok"}
```

> El bind `127.0.0.1:53354:8000` del `docker-compose.yml` deja la app accesible
> únicamente desde el server, nunca desde la red o la IP pública. El único camino de
> entrada es el Cloudflare Tunnel. Si 53354 choca con otra app, cambiá ese mapeo.

## 3. (Opcional) App en Cloudflare Access

Los horarios son públicos, así que Access no es imprescindible. Si igual querés
protegerlo como el resto de tus apps:

1. Cloudflare Zero Trust → `Access controls > Applications`.
2. Crear app `Self-hosted`.
3. Public hostname: `tren.tudominio.com`.
4. Policy que permita tu(s) email(s).
5. Guardar.

(Esta app **no valida** el JWT `Cf-Access-Jwt-Assertion` en el backend: Access queda
como única puerta y no hay secreto que proteger. Frontend y API son el mismo origen,
así que la cookie de Access cubre todo, incluido `/api`.)

## 4. Tunnel Existente En El Host

Usá el tunnel central del server y agregá un public hostname:

```txt
tren.tudominio.com -> http://127.0.0.1:53354
```

Listo: la app queda en `https://tren.tudominio.com/`.

## 5. Actualizar Deploy

```bash
git pull
docker compose up -d --build
```

## Notas

- La app cachea la fuente (horariostrenes.com.ar) 60 s; los "minutos hasta el tren"
  se recalculan en vivo con hora de Buenos Aires (fijada en el Dockerfile con `TZ`).
- Ver logs: `docker compose logs -f api`
- Apagar: `docker compose down`
