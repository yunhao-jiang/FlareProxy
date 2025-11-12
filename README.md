# FlareProxy
FlareProxy is a transparent http proxy adapter that seamlessly forwards client requests to FlareSolverr and bypass Cloudflare and DDoS-GUARD protection.

## Build
FlareProxy is shipped as a OCI container image, and can be built using the [Dockerfile](Dockerfile) provided in the repository root.

```bash
docker build -t flareproxy .
```

## Run
To run it replace the FLARESOLVERR_URL env var with the url of your FlareSolverr instance. FlareProxy runs on the port 8080.
```bash
docker run -e FLARESOLVERR_URL=http://localhost:8191/v1 -p 8080:8080 flareproxy
```

## Usage
Set FlareProxy as a proxy in your browser or in your agent. Please notice: use `http` protocol even if you want to fetch https resources because I'm too lazy to deal with SSL connections. FlareProxy will switch automatically to the https protocol to establish the upstream connection.
```bash
curl --proxy 127.0.0.1:8080 http://www.google.com
```
You can use it as a proxy in [changedetection](https://github.com/dgtlmoon/changedetection.io), just navigate to settings -> CAPTCHA&Proxies and add it as an extra proxy in the list. Then you can setup your watch using any fetch method.

<img width="1814" height="810" alt="CleanShot 2025-11-11 at 21 22 46@2x" src="https://github.com/user-attachments/assets/9898510e-502e-4c15-adcd-1820c7d495c9" />

## Docker Compose
Add the snippet to your docker compose stack, i.e.:

```yaml
  flaresolverr:
    image: ghcr.io/flaresolverr/flaresolverr:latest
    container_name: flaresolverr
    environment:
      - LOG_LEVEL=${LOG_LEVEL:-info}
      - LOG_HTML=${LOG_HTML:-false}
      - CAPTCHA_SOLVER=${CAPTCHA_SOLVER:-none}
      - TZ=YOUR_TZ_STRING/HERE #https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
#    ports:
#    - "8191:8191"
    restart: unless-stopped
  flareproxy:
    image: flareproxy
    container_name: flareproxy
    environment:
    - FLARESOLVERR_URL=http://flaresolverr:8191/v1
    - TZ=YOUR_TZ_STRING/HERE #https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
#    ports:
#    - "8080:8080"
    restart: unless-stopped
    depends_on: 
      flaresolverr:
        condition: service_started #this is how to make sure when flaresolverr restarted, the flare proxy will restart as well (and then wait 15s to create session)
```


## Development
1. To run it locally use venv to prepare the development environment:

```bash
python3 -m venv flareproxy
source flareproxy/bin/activate
pip install -r requirements.txt
```
2. Run the proxy using the FLARESOLVERR_URL env var

```bash
FLARESOLVERR_URL=http://localhost:8191/v1 python3 flareproxy.py
```
3. Test it with curl

```bash
curl --proxy 127.0.0.1:8080 http://www.google.com
```

## Related projects
Shoutout to:

- [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr)
- [changedetection](https://github.com/dgtlmoon/changedetection.io)
- [urlwatch](https://github.com/thp/urlwatch)
