It's fork of Frigate [https://github.com/blakeblackshear/frigate] to run it at Rockchip based boards.
For an instance Orange Pi 5
All comercial and external services are removed.

1) Pull the repo
```
git pull https://github.com/a2nt/frigate.git && cd ./frigate
```

2) Run docker image build
```
make build-boards
```

4) Set resulting image name at your docker_compose.yml
```
version: "3.9"
services:
  frigate:
    container_name: frigate
    hostname: 127.0.0.1
    #network_mode: host
    privileged: true
    restart: unless-stopped
    image: ghcr.io/a2nt/frigate:dev-5f84bf40-rk # my local img
    group_add:
      - "110" # render
      - "44"  # video
      - "46"  # plugdev
    shm_size: "378mb"
    devices:
      - /dev/dri/renderD128:/dev/dri/renderD128
      - /dev/dri/card0:/dev/dri/card0
      - /dev/rga
      - /dev/video-dec0:/dev/video-dec0
      - /dev/video-enc0:/dev/video-enc0
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - ./config.yml:/config/config.yml
      - ./storage/frigate:/media/frigate
      - type: tmpfs # Optional: 1GB of memory, reduces SSD/SD Card wear
        target: /tmp/cache
        tmpfs:
          size: 1000000000
    ports:
      - "127.0.0.1:5000:5000" # HTTP
      - "127.0.0.1:8554:8554" # RTSP
      - "127.0.0.1:8555:8555/tcp" # WebRTC over tcp
      - "127.0.0.1:8555:8555/udp" # WebRTC over udp
    environment:
      FFMPEG_RKMPP_PIXFMT: "YUV420P"
      FRIGATE_MQTT_USER: "admin"
      FRIGATE_MQTT_PASSWORD: "admin"
      FRIGATE_RTSP_USER: "admin"
      FRIGATE_RTSP_PASSWORD: "admin"
      I_PROMISE_I_WONT_MAKE_AN_ISSUE_ON_GITHUB: "true"
```

4) Done!
