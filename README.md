It's fork of Frigate [https://github.com/blakeblackshear/frigate] to run it at Rockchip based boards.
For an instance Orange Pi 5
All comercial and external services are removed.

You can get pre-build docker image at: https://github.com/users/a2nt/packages/container/frigate/versions
For example: ghcr.io/a2nt/frigate:dev-rk-15582525-rk

Or you can build the docker image on your own:

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
    image: ghcr.io/a2nt/frigate:dev-rk-15582525-rk # my local img
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

View the documentation at https://docs.frigate.video

## Donations

If you would like to make a donation to support development, please use [Github Sponsors](https://github.com/sponsors/blakeblackshear).

## Screenshots

### Live dashboard
<div>
<img width="800" alt="Live dashboard" src="https://github.com/blakeblackshear/frigate/assets/569905/5e713cb9-9db5-41dc-947a-6937c3bc376e">
</div>

### Streamlined review workflow
<div>
<img width="800" alt="Streamlined review workflow" src="https://github.com/blakeblackshear/frigate/assets/569905/6fed96e8-3b18-40e5-9ddc-31e6f3c9f2ff">
</div>

### Multi-camera scrubbing
<div>
<img width="800" alt="Multi-camera scrubbing" src="https://github.com/blakeblackshear/frigate/assets/569905/d6788a15-0eeb-4427-a8d4-80b93cae3d74">
</div>

### Built-in mask and zone editor
<div>
<img width="800" alt="Multi-camera scrubbing" src="https://github.com/blakeblackshear/frigate/assets/569905/d7885fc3-bfe6-452f-b7d0-d957cb3e31f5">
</div>
